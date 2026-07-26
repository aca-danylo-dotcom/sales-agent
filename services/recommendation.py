"""Маппинг rule_code -> рекомендуемое действие и сбор фактов по рекомендации.

Полная логика подтверждения/отклонения/переноса рекомендаций (confirm/reject/snooze,
создание задачи, классификация причины отказа через LLM) — Фаза 6 плана. Здесь
чистая функция маппинга, нужная detection.py при создании Recommendation
(поле recommended_action обязательно), и сбор фактов для карточки: всё, что
показывается менеджеру и уходит в промпт LLM, считает backend, а не модель.
"""
from __future__ import annotations

import hashlib

from sqlalchemy.orm import Session

import config
from db.models import DealStageHistory, DealTask, PipelineStage, Recommendation
from services.uk_format import format_amount, format_datetime_uk, idle_label

_ACTION_BY_RULE = {
    "NEW_LEAD_NO_RESPONSE": "contact_lead",
    "DEAL_STALE": "follow_up",
    "PROPOSAL_NO_NEXT_TASK": "create_followup_task",
    "NEXT_CONTACT_OVERDUE": "contact_client",
    "STUCK_ON_STAGE": "review_deal",
    "NO_NEXT_ACTION": "create_followup_task",
}

_DEFAULT_ACTION = "review_deal"

# Ровно одно действие на рекомендацию: заголовок + что конкретно сделать.
ACTION_LABELS: dict[str, tuple[str, str]] = {
    "contact_lead": (
        "Зв'язатися з лідом",
        "Написати або зателефонувати ліду сьогодні та зафіксувати відповідь у CRM.",
    ),
    "follow_up": (
        "Нагадати про себе",
        "Надіслати клієнту follow-up і домовитися про конкретний наступний крок.",
    ),
    "create_followup_task": (
        "Поставити задачу на наступний крок",
        "Створити задачу з конкретною датою наступного контакту по цій угоді.",
    ),
    "contact_client": (
        "Виконати прострочений контакт",
        "Зв'язатися з клієнтом і перенести дату наступного контакту на реальну.",
    ),
    "review_deal": (
        "Переглянути угоду",
        "Перевірити стан угоди та вирішити: рухати далі чи закривати як програну.",
    ),
}

RULE_LABELS = {
    "NEW_LEAD_NO_RESPONSE": "Новий лід без відповіді",
    "DEAL_STALE": "Немає активності по угоді",
    "PROPOSAL_NO_NEXT_TASK": "КП відправлено, немає наступного кроку",
    "NEXT_CONTACT_OVERDUE": "Прострочена дата наступного контакту",
    "STUCK_ON_STAGE": "Угода зависла на етапі",
    "NO_NEXT_ACTION": "Немає відкритої задачі по угоді",
}


def action_for_rule(rule_code: str) -> str:
    return _ACTION_BY_RULE.get(rule_code, _DEFAULT_ACTION)


def action_labels(recommended_action: str) -> tuple[str, str]:
    return ACTION_LABELS.get(recommended_action, ACTION_LABELS[_DEFAULT_ACTION])


def rule_label(rule_code: str) -> str:
    return RULE_LABELS.get(rule_code, rule_code)


def facts_fingerprint(rec: Recommendation) -> str:
    """Отпечаток входных данных: сменился rule_code или reason_text — кэш устарел."""
    raw = f"{rec.rule_code}|{rec.reason_text or ''}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _days_since(moment, now) -> float | None:
    if moment is None:
        return None
    return (now - moment).total_seconds() / 86400


def collect_facts(session: Session, rec: Recommendation) -> dict:
    """Факты по сделке для карточки и промптов. Пустые поля не заполняются."""
    deal = rec.deal
    now = config.now_local()
    action_title, action_text = action_labels(rec.recommended_action)

    facts: dict[str, str] = {}
    contact = deal.contact
    if contact is not None:
        if contact.company_name:
            facts["client"] = contact.company_name
        if contact.name:
            facts["contact_name"] = contact.name
    facts.setdefault("client", deal.title)
    facts["deal_title"] = deal.title
    facts["stage"] = deal.stage.name if deal.stage else ""
    if deal.amount is not None:
        facts["amount"] = format_amount(float(deal.amount), deal.currency)
    if deal.owner is not None:
        facts["owner"] = deal.owner.full_name

    idle_days = _days_since(deal.last_activity_at or deal.created_at, now)
    if idle_days is not None:
        facts["idle"] = idle_label(idle_days)
        facts["idle_days"] = f"{idle_days:.1f}"
    stage_days = _days_since(deal.stage_entered_at, now)
    if stage_days is not None:
        facts["stage_age"] = idle_label(stage_days)
    if deal.next_contact_date is not None:
        overdue = deal.next_contact_date < now
        facts["next_contact"] = format_datetime_uk(deal.next_contact_date) + (
            " (прострочено)" if overdue else ""
        )
    if deal.last_note:
        facts["last_note"] = deal.last_note

    open_tasks = (
        session.query(DealTask)
        .filter(DealTask.deal_id == deal.id, DealTask.status.in_(("open", "overdue")))
        .order_by(DealTask.due_at)
        .all()
    )
    if open_tasks:
        facts["open_tasks"] = "; ".join(
            task.text + (f" (до {format_datetime_uk(task.due_at)})" if task.due_at else "")
            for task in open_tasks
        )
    else:
        facts["open_tasks"] = "немає відкритих задач"

    history = (
        session.query(DealStageHistory)
        .filter(DealStageHistory.deal_id == deal.id)
        .order_by(DealStageHistory.changed_at.desc())
        .limit(5)
        .all()
    )
    if history:
        stage_names = {
            row.id: row.name
            for row in session.query(PipelineStage).filter(
                PipelineStage.company_id == deal.company_id
            )
        }
        facts["stage_history"] = "; ".join(
            f"{format_datetime_uk(item.changed_at)}: "
            f"{stage_names.get(item.from_stage_id, '—')} → {stage_names.get(item.to_stage_id, '—')}"
            for item in reversed(history)
        )

    facts["problem"] = rec.reason_text or rule_label(rec.rule_code)
    facts["rule_label"] = rule_label(rec.rule_code)
    facts["action"] = f"{action_title}. {action_text}"
    facts["action_title"] = action_title
    facts["action_text"] = action_text
    return facts
