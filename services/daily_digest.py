"""Ежедневный список менеджера: проекция pending-рекомендаций на владельца сделки.

Дайджест — это снимок «что было на утро»: пункты за дату не пересобираются
заново, отработанные не исчезают из истории дня, а меняют статус. Поэтому
статус пункта считается из статуса рекомендации, а не хранится отдельно.

Ничего не решает сам: детекция и приоритизация уже отработали, здесь только
распределение готовых рекомендаций по людям.
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session, selectinload

import config
from db.models import Company, DailyDigestItem, Deal, Recommendation, User

# Статус рекомендации -> статус пункта в списке дня.
STATUS_BY_RECOMMENDATION = {
    "pending": "pending",
    "snoozed": "snoozed",
    "confirmed": "done",
    "rejected": "dismissed",
    "expired": "dismissed",
}

# Пункты, которые ещё ждут действия менеджера.
OPEN_STATUSES = ("pending", "snoozed")


def company_now(company: Company) -> datetime:
    """Текущее время в часовом поясе компании: день начинается у неё, а не у сервера.

    Считается пересчётом из серверного времени (config.now_local), чтобы всё
    приложение имело один источник «сейчас».
    """
    try:
        tz = ZoneInfo(company.timezone or config.TIMEZONE_NAME)
    except Exception:  # некорректный TZ в данных не должен ронять экран
        tz = config.TIMEZONE
    server_now = config.now_local().replace(tzinfo=config.TIMEZONE)
    return server_now.astimezone(tz).replace(tzinfo=None)


def digest_date_for(now: datetime | None = None) -> datetime:
    """Начало суток — ключ дайджеста (в поле DateTime храним полночь)."""
    now = now or config.now_local()
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


def build_digest(session: Session, company_id: int, now: datetime | None = None) -> int:
    """Собирает список дня по всем менеджерам компании. Возвращает число новых пунктов.

    Идемпотентна: повторный вызов за ту же дату не создаёт дублей, но добавляет
    рекомендации, появившиеся уже после первой сборки.
    """
    digest_date = digest_date_for(now)

    recommendations = (
        session.query(Recommendation)
        .join(Deal, Recommendation.deal_id == Deal.id)
        .filter(
            Deal.company_id == company_id,
            Deal.owner_user_id.isnot(None),
            Recommendation.status.in_(OPEN_STATUSES),
        )
        .all()
    )
    if not recommendations:
        return 0

    existing: set[tuple[int, int]] = {
        (row.user_id, row.recommendation_id)
        for row in session.query(DailyDigestItem).filter(
            DailyDigestItem.company_id == company_id,
            DailyDigestItem.digest_date == digest_date,
        )
    }

    created = 0
    for rec in recommendations:
        key = (rec.deal.owner_user_id, rec.id)
        if key in existing:
            continue
        session.add(
            DailyDigestItem(
                company_id=company_id,
                user_id=rec.deal.owner_user_id,
                recommendation_id=rec.id,
                digest_date=digest_date,
                status=STATUS_BY_RECOMMENDATION.get(rec.status, "pending"),
            )
        )
        existing.add(key)
        created += 1

    session.commit()
    return created


def sync_statuses(session: Session, company_id: int, now: datetime | None = None) -> int:
    """Подтягивает статусы пунктов дня к текущим статусам рекомендаций."""
    digest_date = digest_date_for(now)
    rows = (
        session.query(DailyDigestItem, Recommendation)
        .join(Recommendation, DailyDigestItem.recommendation_id == Recommendation.id)
        .filter(
            DailyDigestItem.company_id == company_id,
            DailyDigestItem.digest_date == digest_date,
        )
        .all()
    )

    changed = 0
    for item, rec in rows:
        status = STATUS_BY_RECOMMENDATION.get(rec.status, "pending")
        if item.status != status:
            item.status = status
            changed += 1
    if changed:
        session.commit()
    return changed


def items_for_user(
    session: Session,
    company_id: int,
    user_id: int,
    now: datetime | None = None,
) -> list[tuple[DailyDigestItem, Recommendation]]:
    """Пункты дня одного менеджера по убыванию приоритета — только его сделки."""
    digest_date = digest_date_for(now)
    return (
        session.query(DailyDigestItem, Recommendation)
        .join(Recommendation, DailyDigestItem.recommendation_id == Recommendation.id)
        .filter(
            DailyDigestItem.company_id == company_id,
            DailyDigestItem.user_id == user_id,
            DailyDigestItem.digest_date == digest_date,
        )
        .options(
            selectinload(Recommendation.deal).selectinload(Deal.contact),
            selectinload(Recommendation.deal).selectinload(Deal.stage),
        )
        .order_by(Recommendation.priority_score.desc(), Recommendation.id)
        .all()
    )


def managers(session: Session, company_id: int) -> list[User]:
    """Активные менеджеры компании — для выбора «чей день» (авторизации в MVP нет)."""
    return (
        session.query(User)
        .filter(User.company_id == company_id, User.is_active.is_(True), User.role == "manager")
        .order_by(User.full_name, User.id)
        .all()
    )
