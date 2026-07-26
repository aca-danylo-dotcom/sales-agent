"""Экран «Рабочий список»: pending-рекомендации компании по убыванию приоритета.

Read-only (Фаза 4): карточка рекомендации, LLM-черновик и confirm/reject/snooze —
Фазы 5-6, здесь только отображение уже посчитанных детекцией и приоритизацией данных.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass

from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, selectinload

import config
from db.models import Deal, Recommendation
from services.recommendation import rule_label
from services.uk_format import format_amount as _format_amount
from services.uk_format import format_date_uk as _format_date_uk
from services.uk_format import idle_label as _idle_label
from web.deps import get_current_company, get_db

router = APIRouter(tags=["worklist"])
templates = Jinja2Templates(directory="web/templates")


@dataclass
class WorklistItem:
    rec_id: int
    rank: int
    tier: str
    title: str
    description: str
    idle_label: str
    idle_high: bool
    amount_value: float
    amount_label: str


def _tier_for_rank(rank: int, total: int) -> str:
    if total == 0:
        return "low"
    if rank <= math.ceil(total / 3):
        return "high"
    if rank <= math.ceil(total * 2 / 3):
        return "mid"
    return "low"


@router.get("/")
def worklist_index(request: Request, session: Session = Depends(get_db)):
    company = get_current_company(session)
    session.commit()

    now = config.now_local()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    recommendations = (
        session.query(Recommendation)
        .join(Deal, Recommendation.deal_id == Deal.id)
        .filter(Deal.company_id == company.id, Recommendation.status == "pending")
        .options(
            selectinload(Recommendation.deal).selectinload(Deal.contact),
            selectinload(Recommendation.deal).selectinload(Deal.stage),
        )
        .order_by(Recommendation.priority_score.desc(), Recommendation.id)
        .all()
    )

    total = len(recommendations)
    items: list[WorklistItem] = []
    overdue_count = 0
    no_response_count = 0
    amount_at_risk: dict[str, float] = {}
    counted_deal_ids: set[int] = set()

    for index, rec in enumerate(recommendations, start=1):
        deal = rec.deal
        breakdown = json.loads(rec.priority_breakdown_json) if rec.priority_breakdown_json else {}
        idle_days = float(breakdown.get("idle_days", 0.0))
        if breakdown.get("overdue_bonus"):
            overdue_count += 1
        if rec.rule_code == "NEW_LEAD_NO_RESPONSE":
            no_response_count += 1

        amount = float(deal.amount) if deal.amount is not None else None
        if amount is not None and deal.id not in counted_deal_ids:
            currency = deal.currency or ""
            amount_at_risk[currency] = amount_at_risk.get(currency, 0.0) + amount
        counted_deal_ids.add(deal.id)

        client = (deal.contact.company_name or deal.contact.name) if deal.contact else None
        items.append(
            WorklistItem(
                rec_id=rec.id,
                rank=index,
                tier=_tier_for_rank(index, total),
                title=client or deal.title,
                description=f"{rule_label(rec.rule_code)} · {deal.stage.name}",
                idle_label=_idle_label(idle_days),
                idle_high=idle_days >= 5,
                amount_value=amount or 0.0,
                amount_label=_format_amount(amount, deal.currency),
            )
        )

    reactivated_today = (
        session.query(Recommendation)
        .join(Deal, Recommendation.deal_id == Deal.id)
        .filter(
            Deal.company_id == company.id,
            Recommendation.status == "expired",
            Recommendation.resolved_at >= today_start,
        )
        .count()
    )

    amount_at_risk_label = (
        " + ".join(_format_amount(value, currency) for currency, value in sorted(amount_at_risk.items()))
        or "—"
    )

    return templates.TemplateResponse(
        request,
        "worklist/index.html",
        {
            "active_nav": "worklist",
            "company": company,
            "items": items,
            "total": total,
            "deals_count": len(counted_deal_ids),
            "overdue_count": overdue_count,
            "no_response_count": no_response_count,
            "amount_at_risk_label": amount_at_risk_label,
            "reactivated_today": reactivated_today,
            "today_label": _format_date_uk(now),
        },
    )
