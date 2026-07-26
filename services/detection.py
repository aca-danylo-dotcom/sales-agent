"""Rule-based детекция проблемных сделок.

Не импортирует services.llm — детекция принимает решения только на основе
данных из БД (даты, этап, задачи), без обращений к LLM.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from sqlalchemy.orm import Session, selectinload

import config
from db.models import Deal, DealTask, Recommendation
from db.models import DetectionRule as DetectionRuleRow
from services.recommendation import action_for_rule


@dataclass
class RuleFinding:
    reason_text: str


@dataclass
class RuleContext:
    deal: Deal
    open_tasks: list[DealTask]
    now: datetime
    params: dict


class DetectionRule(Protocol):
    code: str

    def evaluate(self, ctx: RuleContext) -> RuleFinding | None: ...


def _hours_since(moment: datetime | None, now: datetime) -> float | None:
    if moment is None:
        return None
    return (now - moment).total_seconds() / 3600


class NewLeadNoResponse:
    code = "NEW_LEAD_NO_RESPONSE"

    def evaluate(self, ctx: RuleContext) -> RuleFinding | None:
        if ctx.deal.stage.order_index != 0:
            return None
        hours = _hours_since(ctx.deal.last_activity_at or ctx.deal.created_at, ctx.now)
        threshold = ctx.params.get("hours_threshold", 24)
        if hours is None or hours < threshold:
            return None
        return RuleFinding(f"Новый лид без реакции {hours:.0f} ч (порог {threshold} ч)")


class DealStale:
    code = "DEAL_STALE"

    def evaluate(self, ctx: RuleContext) -> RuleFinding | None:
        hours = _hours_since(ctx.deal.last_activity_at, ctx.now)
        threshold = ctx.params.get("days_threshold", 5) * 24
        if hours is None or hours < threshold:
            return None
        return RuleFinding(f"Нет активности по сделке {hours / 24:.1f} дн (порог {threshold / 24:.0f} дн)")


class ProposalNoNextTask:
    code = "PROPOSAL_NO_NEXT_TASK"
    STAGE_NAME = "Предложение отправлено"

    def evaluate(self, ctx: RuleContext) -> RuleFinding | None:
        if ctx.deal.stage.name != self.STAGE_NAME or ctx.open_tasks:
            return None
        hours = _hours_since(ctx.deal.stage_entered_at, ctx.now)
        threshold = ctx.params.get("hours_threshold", 48)
        if hours is None or hours < threshold:
            return None
        return RuleFinding(f"КП отправлено {hours:.0f} ч назад, нет задачи на follow-up (порог {threshold} ч)")


class NextContactOverdue:
    code = "NEXT_CONTACT_OVERDUE"

    def evaluate(self, ctx: RuleContext) -> RuleFinding | None:
        hours = _hours_since(ctx.deal.next_contact_date, ctx.now)
        threshold = ctx.params.get("hours_grace", 4)
        if hours is None or hours < threshold:
            return None
        return RuleFinding(f"Дата следующего контакта просрочена на {hours:.0f} ч (грейс {threshold} ч)")


class StuckOnStage:
    code = "STUCK_ON_STAGE"

    def evaluate(self, ctx: RuleContext) -> RuleFinding | None:
        hours = _hours_since(ctx.deal.stage_entered_at, ctx.now)
        threshold = ctx.params.get("days_threshold", 10) * 24
        if hours is None or hours < threshold:
            return None
        return RuleFinding(
            f"Сделка на этапе «{ctx.deal.stage.name}» {hours / 24:.1f} дн (порог {threshold / 24:.0f} дн)"
        )


class NoNextAction:
    code = "NO_NEXT_ACTION"

    def evaluate(self, ctx: RuleContext) -> RuleFinding | None:
        if ctx.open_tasks:
            return None
        hours = _hours_since(ctx.deal.last_activity_at or ctx.deal.stage_entered_at, ctx.now)
        threshold = ctx.params.get("hours_threshold", 24)
        if hours is None or hours < threshold:
            return None
        return RuleFinding(f"Нет открытой задачи по сделке {hours:.0f} ч (порог {threshold} ч)")


RULES: dict[str, DetectionRule] = {
    rule.code: rule
    for rule in (
        NewLeadNoResponse(),
        DealStale(),
        ProposalNoNextTask(),
        NextContactOverdue(),
        StuckOnStage(),
        NoNextAction(),
    )
}


@dataclass
class DealFinding:
    rule_code: str
    reason_text: str


# Сколько дней после решения по рекомендации (підтвердив/відхилив) то же самое
# правило не поднимает её заново. В Фазе 8 переедет в настройки компании.
RESOLVED_COOLDOWN_DAYS = 7

# Статусы, при которых рекомендация ещё «в работе» и дубль создавать не нужно.
_OPEN_STATUSES = ("pending", "snoozed")


def _in_cooldown(rec: Recommendation, now: datetime) -> bool:
    """Решение по этой проблеме принято недавно — не беспокоим менеджера повторно."""
    if rec.status not in ("confirmed", "rejected"):
        return False
    if rec.resolved_at is None:
        return True
    return (now - rec.resolved_at).total_seconds() < RESOLVED_COOLDOWN_DAYS * 86400


def wake_snoozed(session: Session, company_id: int, now: datetime | None = None) -> int:
    """Возвращает в работу отложенные рекомендации, у которых вышел срок."""
    now = now or config.now_local()
    rows = (
        session.query(Recommendation)
        .join(Deal, Recommendation.deal_id == Deal.id)
        .filter(
            Deal.company_id == company_id,
            Recommendation.status == "snoozed",
            Recommendation.snoozed_until.isnot(None),
            Recommendation.snoozed_until <= now,
        )
        .all()
    )
    for rec in rows:
        rec.status = "pending"
        rec.snoozed_until = None
    if rows:
        session.commit()
    return len(rows)


def evaluate_deal(
    deal: Deal,
    open_tasks: list[DealTask],
    now: datetime,
    rule_rows: list[DetectionRuleRow],
) -> list[DealFinding]:
    """Прогоняет включённые правила по одной сделке. Чистая функция, без обращений к БД."""
    findings: list[DealFinding] = []
    for rule_row in rule_rows:
        if not rule_row.enabled:
            continue
        rule = RULES.get(rule_row.code)
        if rule is None:
            continue
        if rule_row.applies_to_stage_ids:
            allowed_stage_ids = json.loads(rule_row.applies_to_stage_ids)
            if deal.stage_id not in allowed_stage_ids:
                continue
        params = json.loads(rule_row.params_json) if rule_row.params_json else {}
        ctx = RuleContext(deal=deal, open_tasks=open_tasks, now=now, params=params)
        finding = rule.evaluate(ctx)
        if finding is not None:
            findings.append(DealFinding(rule_code=rule_row.code, reason_text=finding.reason_text))
    return findings


def recompute_company(session: Session, company_id: int, now: datetime | None = None) -> None:
    """Применяет включённые правила ко всем открытым сделкам компании.

    Новый детект -> создаёт Recommendation(status='pending').
    Уже pending с тем же (deal_id, rule_code) -> обновляет detected_at/reason_text, не дублирует.
    Отложенная (snoozed) с вышедшим сроком -> возвращается в pending.
    Подтверждённая/отклонённая в пределах RESOLVED_COOLDOWN_DAYS -> новая не создаётся.
    Детект пропал у открытой рекомендации -> status='expired' (сделка вернулась в работу).
    """
    now = now or config.now_local()

    rule_rows = session.query(DetectionRuleRow).filter_by(company_id=company_id, enabled=True).all()
    if not rule_rows:
        return

    deals = (
        session.query(Deal)
        .options(selectinload(Deal.stage))
        .filter_by(company_id=company_id, status="open")
        .all()
    )
    if not deals:
        return
    deal_ids = [d.id for d in deals]

    open_tasks_by_deal: dict[int, list[DealTask]] = {deal_id: [] for deal_id in deal_ids}
    for task in (
        session.query(DealTask)
        .filter(DealTask.deal_id.in_(deal_ids), DealTask.status != "done")
        .all()
    ):
        open_tasks_by_deal[task.deal_id].append(task)

    # Последняя рекомендация по каждому (deal_id, rule_code) — любого статуса:
    # именно она решает, обновлять существующую, ждать окончания cooldown или
    # создавать новую.
    last_by_key: dict[tuple[int, str], Recommendation] = {
        (rec.deal_id, rec.rule_code): rec
        for rec in (
            session.query(Recommendation)
            .filter(Recommendation.deal_id.in_(deal_ids))
            .order_by(Recommendation.id)
            .all()
        )
    }

    seen_keys: set[tuple[int, str]] = set()

    for deal in deals:
        findings = evaluate_deal(deal, open_tasks_by_deal[deal.id], now, rule_rows)
        for finding in findings:
            key = (deal.id, finding.rule_code)
            seen_keys.add(key)
            existing = last_by_key.get(key)

            if existing is not None and existing.status in _OPEN_STATUSES:
                existing.reason_text = finding.reason_text
                existing.detected_at = now
                snoozed_over = existing.snoozed_until is None or existing.snoozed_until <= now
                if existing.status == "snoozed" and snoozed_over:
                    existing.status = "pending"  # срок «Відкласти» вышел — назад в работу
                    existing.snoozed_until = None
                continue

            if existing is not None and _in_cooldown(existing, now):
                continue

            session.add(
                Recommendation(
                    deal_id=deal.id,
                    rule_code=finding.rule_code,
                    recommended_action=action_for_rule(finding.rule_code),
                    reason_text=finding.reason_text,
                    status="pending",
                    detected_at=now,
                )
            )

    for key, rec in last_by_key.items():
        if key not in seen_keys and rec.status in _OPEN_STATUSES:
            rec.status = "expired"
            rec.resolved_at = now
            rec.snoozed_until = None

    session.commit()
