"""Экран «Мій день»: список дня одного менеджера — только его сделки.

Дайджест собирает фоновый джоб (services/scheduler.py) утром по локальному
времени компании; экран лишь дособирает его при открытии, чтобы менеджер видел
актуальный список даже до первого срабатывания джоба.

Авторизации в MVP нет, поэтому «чей день» выбирается явно ссылками вверху
экрана (роли появятся в Фазе 10).
"""
from __future__ import annotations

import json
from dataclasses import dataclass

from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from db.models import User
from services import daily_digest
from services.detection import wake_snoozed
from services.recommendation import rule_label
from services.uk_format import format_amount as _format_amount
from services.uk_format import format_date_uk as _format_date_uk
from services.uk_format import idle_label as _idle_label
from web.deps import get_current_company, get_db
from web.routers.worklist import tier_for_rank

router = APIRouter(prefix="/my-day", tags=["my-day"])
templates = Jinja2Templates(directory="web/templates")

STATUS_LABELS = {
    "pending": "В роботі",
    "snoozed": "Відкладено",
    "done": "Зроблено",
    "dismissed": "Знято",
}


@dataclass
class DayItem:
    rec_id: int
    tier: str
    status: str
    status_label: str
    actionable: bool
    title: str
    description: str
    idle_label: str
    idle_high: bool
    amount_label: str


@router.get("")
def my_day(request: Request, user_id: int | None = None, session: Session = Depends(get_db)):
    company = get_current_company(session)
    session.commit()

    now = daily_digest.company_now(company)
    managers = daily_digest.managers(session, company.id)

    current: User | None = None
    if user_id is not None:
        current = next((m for m in managers if m.id == user_id), None)
    if current is None and managers:
        current = managers[0]

    items: list[DayItem] = []
    counters = {"total": 0, "open": 0, "done": 0, "dismissed": 0}

    if current is not None:
        # Отложенные с вышедшим сроком возвращаются в работу до сборки списка.
        wake_snoozed(session, company.id, now)
        daily_digest.build_digest(session, company.id, now=now)
        daily_digest.sync_statuses(session, company.id, now=now)

        rows = daily_digest.items_for_user(session, company.id, current.id, now=now)
        open_total = sum(1 for item, _ in rows if item.status in daily_digest.OPEN_STATUSES)
        open_rank = 0

        for item, rec in rows:
            deal = rec.deal
            breakdown = json.loads(rec.priority_breakdown_json) if rec.priority_breakdown_json else {}
            idle_days = float(breakdown.get("idle_days", 0.0))
            actionable = item.status in daily_digest.OPEN_STATUSES
            if actionable:
                open_rank += 1
                tier = tier_for_rank(open_rank, open_total)
            else:
                tier = "done"

            client = (deal.contact.company_name or deal.contact.name) if deal.contact else None
            items.append(
                DayItem(
                    rec_id=rec.id,
                    tier=tier,
                    status=item.status,
                    status_label=STATUS_LABELS.get(item.status, item.status),
                    actionable=actionable,
                    title=client or deal.title,
                    description=f"{rule_label(rec.rule_code)} · {deal.stage.name}",
                    idle_label=_idle_label(idle_days),
                    idle_high=idle_days >= 5,
                    amount_label=_format_amount(
                        float(deal.amount) if deal.amount is not None else None, deal.currency
                    ),
                )
            )

        counters["total"] = len(items)
        counters["open"] = open_total
        counters["done"] = sum(1 for i in items if i.status == "done")
        counters["dismissed"] = sum(1 for i in items if i.status == "dismissed")

    return templates.TemplateResponse(
        request,
        "myday/index.html",
        {
            "active_nav": "my-day",
            "company": company,
            "managers": managers,
            "current": current,
            "items": items,
            "counters": counters,
            "today_label": _format_date_uk(now),
        },
    )
