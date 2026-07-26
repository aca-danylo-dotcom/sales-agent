"""Действия менеджера по рекомендации: підтвердити / відкласти / відхилити.

Что происходит со сделкой, решает backend: он создаёт задачу, ставит статус и
срок, пишет аудит в action_log. LLM привлекается только для классификации
свободного текста причины отказа (и его отсутствие ничего не ломает —
категория тогда 'other').
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

import config
from db.models import ActionLog, DealTask, Recommendation
from services import llm
from services.prompts import REJECTION_CATEGORIES
from services.tasks import create_task_for_recommendation

# Варианты «Відкласти»: код -> (подпись для кнопки, часов).
SNOOZE_PRESETS: dict[str, tuple[str, int]] = {
    "4h": ("На 4 години", 4),
    "1d": ("На добу", 24),
    "3d": ("На 3 дні", 72),
    "7d": ("На тиждень", 168),
}
DEFAULT_SNOOZE = "1d"

REJECTION_LABELS = REJECTION_CATEGORIES

# Типы записей в action_log (используются отчётом руководителя, Фаза 9).
ACTION_CONFIRMED = "recommendation_confirmed"
ACTION_REJECTED = "recommendation_rejected"
ACTION_SNOOZED = "recommendation_snoozed"
ACTION_TASK_CREATED = "task_created"


def _acting_user_id(rec: Recommendation) -> int | None:
    """Кто выполнил действие. Авторизации в MVP нет — считаем, что владелец сделки."""
    return rec.deal.owner_user_id


def log_action(
    session: Session,
    rec: Recommendation,
    action_type: str,
    details: dict | None = None,
    now: datetime | None = None,
) -> ActionLog:
    """Единая точка записи в action_log: каждое действие по рекомендации попадает в аудит."""
    entry = ActionLog(
        company_id=rec.deal.company_id,
        deal_id=rec.deal_id,
        recommendation_id=rec.id,
        user_id=_acting_user_id(rec),
        action_type=action_type,
        details_json=json.dumps(details or {}, ensure_ascii=False),
        created_at=now or config.now_local(),
    )
    session.add(entry)
    return entry


def confirm_recommendation(
    session: Session,
    rec: Recommendation,
    now: datetime | None = None,
) -> DealTask:
    """Подтверждение: создаём задачу со сроком и ответственным, закрываем рекомендацию."""
    now = now or config.now_local()

    task = create_task_for_recommendation(session, rec, now=now)

    rec.status = "confirmed"
    rec.resolved_at = now
    rec.resolved_by_user_id = _acting_user_id(rec)
    rec.snoozed_until = None

    log_action(
        session,
        rec,
        ACTION_CONFIRMED,
        {"rule_code": rec.rule_code, "recommended_action": rec.recommended_action},
        now=now,
    )
    log_action(
        session,
        rec,
        ACTION_TASK_CREATED,
        {
            "task_id": task.id,
            "due_at": task.due_at.isoformat() if task.due_at else None,
            "assignee_user_id": task.assignee_user_id,
            "text": task.text,
        },
        now=now,
    )
    session.commit()
    return task


def reject_recommendation(
    session: Session,
    rec: Recommendation,
    reason_text: str,
    now: datetime | None = None,
) -> str:
    """Отклонение: свободный текст причины классифицируется в категорию для статистики."""
    now = now or config.now_local()
    reason_text = (reason_text or "").strip()

    category = llm.classify_rejection_reason(reason_text) or "other"

    rec.status = "rejected"
    rec.resolved_at = now
    rec.resolved_by_user_id = _acting_user_id(rec)
    rec.rejection_reason_category = category
    rec.snoozed_until = None

    log_action(
        session,
        rec,
        ACTION_REJECTED,
        {"rule_code": rec.rule_code, "reason_text": reason_text, "category": category},
        now=now,
    )
    session.commit()
    return category


def snooze_recommendation(
    session: Session,
    rec: Recommendation,
    preset: str = DEFAULT_SNOOZE,
    now: datetime | None = None,
) -> datetime:
    """Откладывание: рекомендация уходит из работы до snoozed_until и возвращается сама."""
    now = now or config.now_local()
    label, hours = SNOOZE_PRESETS.get(preset, SNOOZE_PRESETS[DEFAULT_SNOOZE])
    until = now + timedelta(hours=hours)

    rec.status = "snoozed"
    rec.snoozed_until = until
    # resolved_at не ставим: решение по проблеме не принято, она вернётся в работу.
    rec.resolved_by_user_id = _acting_user_id(rec)

    log_action(
        session,
        rec,
        ACTION_SNOOZED,
        {"rule_code": rec.rule_code, "preset": preset, "hours": hours, "until": until.isoformat()},
        now=now,
    )
    session.commit()
    return until
