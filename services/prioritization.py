"""Rule-based приоритизация pending-рекомендаций.

Не импортирует services.llm — приоритет считается только суммированием сигналов,
уже сохранённых в БД (сумма сделки, простой, этап, просроченные задачи, число
одновременно сработавших правил), без обращений к LLM.
"""
from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy.orm import Session, selectinload

import config
from db.models import Company, Deal, DealTask, Recommendation


def _idle_days(deal: Deal, now: datetime) -> float:
    moment = deal.last_activity_at or deal.created_at
    if moment is None:
        return 0.0
    return max((now - moment).total_seconds() / 3600 / 24, 0.0)


def _has_overdue_task(tasks: list[DealTask], now: datetime) -> bool:
    for task in tasks:
        if task.status == "done":
            continue
        if task.status == "overdue":
            return True
        if task.due_at is not None and task.due_at < now:
            return True
    return False


def prioritize_company(session: Session, company_id: int, now: datetime | None = None) -> None:
    """Считает priority_score + priority_breakdown_json для всех pending-рекомендаций компании.

    Идемпотентно: каждый вызов пересчитывает поверх текущего состояния сделок и рекомендаций.
    """
    now = now or config.now_local()

    company = session.get(Company, company_id)
    if company is None:
        return

    weights = {
        "amount": float(company.weight_amount),
        "idle": float(company.weight_idle),
        "stage": float(company.weight_stage),
        "overdue_task": float(company.weight_overdue_task),
        "multi_rule": float(company.weight_multi_rule),
    }

    recommendations = (
        session.query(Recommendation)
        .join(Deal, Recommendation.deal_id == Deal.id)
        .filter(Deal.company_id == company_id, Recommendation.status == "pending")
        .options(selectinload(Recommendation.deal).selectinload(Deal.stage))
        .all()
    )
    if not recommendations:
        return

    deal_ids = {rec.deal_id for rec in recommendations}

    open_deal_amounts = [
        float(amount)
        for (amount,) in session.query(Deal.amount)
        .filter(Deal.company_id == company_id, Deal.status == "open", Deal.amount.isnot(None))
        .all()
    ]
    max_amount = max(open_deal_amounts, default=0.0)

    open_tasks_by_deal: dict[int, list[DealTask]] = {deal_id: [] for deal_id in deal_ids}
    for task in (
        session.query(DealTask).filter(DealTask.deal_id.in_(deal_ids), DealTask.status != "done").all()
    ):
        open_tasks_by_deal[task.deal_id].append(task)

    concurrent_count: dict[int, int] = {}
    for rec in recommendations:
        concurrent_count[rec.deal_id] = concurrent_count.get(rec.deal_id, 0) + 1

    for rec in recommendations:
        deal = rec.deal
        normalized_amount = (
            float(deal.amount) / max_amount if deal.amount is not None and max_amount > 0 else 0.0
        )
        idle_days = _idle_days(deal, now)
        stage_weight_value = deal.stage.order_index
        overdue_bonus = 1 if _has_overdue_task(open_tasks_by_deal.get(deal.id, []), now) else 0
        multi_rule_bonus = max(concurrent_count[deal.id] - 1, 0)

        score = (
            normalized_amount * weights["amount"]
            + idle_days * weights["idle"]
            + stage_weight_value * weights["stage"]
            + overdue_bonus * weights["overdue_task"]
            + multi_rule_bonus * weights["multi_rule"]
        )

        rec.priority_score = score
        rec.priority_breakdown_json = json.dumps(
            {
                "normalized_amount": normalized_amount,
                "idle_days": idle_days,
                "stage_weight": stage_weight_value,
                "overdue_bonus": overdue_bonus,
                "multi_rule_bonus": multi_rule_bonus,
                "weights": weights,
            },
            ensure_ascii=False,
        )

    session.commit()
