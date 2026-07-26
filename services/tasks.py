"""Создание задачи по подтверждённой рекомендации.

Задача — это то, что менеджер реально должен сделать: текст с причиной, срок и
ответственный. Всё считает backend: срок берётся из типа рекомендованного
действия, ответственный — владелец сделки. LLM здесь не участвует.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy.orm import Session

import config
from db.models import DealTask, Recommendation
from services.recommendation import action_labels

# Сколько часов даётся на действие с момента подтверждения рекомендации.
# В Фазе 8 (Настройки) эти значения станут редактируемыми.
DUE_HOURS_BY_ACTION: dict[str, int] = {
    "contact_lead": 4,
    "contact_client": 4,
    "follow_up": 24,
    "create_followup_task": 24,
    "review_deal": 48,
}
DEFAULT_DUE_HOURS = 24


def due_at_for(recommended_action: str, now: datetime) -> datetime:
    return now + timedelta(hours=DUE_HOURS_BY_ACTION.get(recommended_action, DEFAULT_DUE_HOURS))


def task_text_for(rec: Recommendation) -> str:
    """Текст задачи: что сделать + почему (причина из детекции)."""
    title, text = action_labels(rec.recommended_action)
    reason = (rec.reason_text or "").strip()
    return f"{title}. {text}" + (f" Причина: {reason}" if reason else "")


def create_task_for_recommendation(
    session: Session,
    rec: Recommendation,
    now: datetime | None = None,
) -> DealTask:
    """Создаёт задачу в deal_tasks по рекомендации. Повторный вызов задачу не дублирует."""
    now = now or config.now_local()

    existing = (
        session.query(DealTask)
        .filter(DealTask.recommendation_id == rec.id)
        .order_by(DealTask.id)
        .first()
    )
    if existing is not None:
        return existing

    task = DealTask(
        deal_id=rec.deal_id,
        external_id=None,  # задача создана нами, во внешней CRM её ещё нет
        source="system",
        text=task_text_for(rec),
        due_at=due_at_for(rec.recommended_action, now),
        status="open",
        assignee_user_id=rec.deal.owner_user_id,
        recommendation_id=rec.id,
        created_at=now,
    )
    session.add(task)
    session.flush()
    return task
