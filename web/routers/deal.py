"""Карточка рекомендации: факты сделки, единственное действие, LLM-блок.

Карточка отдаётся htmx-фрагментом в правую панель рабочего списка. LLM-блок
(объяснение + черновик) грузится вторым запросом — карточка с фактами и
действием видна сразу и не зависит от доступности модели.
"""
from __future__ import annotations

import json
import math

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, selectinload

import config
from db.models import Deal, MessageDraft, Recommendation
from services import llm
from services.recommendation import collect_facts, facts_fingerprint
from web.deps import get_current_company, get_db

router = APIRouter(prefix="/recommendations", tags=["recommendation"])
templates = Jinja2Templates(directory="web/templates")


def _load(session: Session, rec_id: int) -> Recommendation:
    company = get_current_company(session)
    session.commit()
    rec = (
        session.query(Recommendation)
        .join(Deal, Recommendation.deal_id == Deal.id)
        .filter(Recommendation.id == rec_id, Deal.company_id == company.id)
        .options(
            selectinload(Recommendation.deal).selectinload(Deal.contact),
            selectinload(Recommendation.deal).selectinload(Deal.stage),
            selectinload(Recommendation.deal).selectinload(Deal.owner),
        )
        .first()
    )
    if rec is None:
        raise HTTPException(status_code=404, detail="Рекомендацію не знайдено")
    return rec


def _priority_tier(session: Session, rec: Recommendation) -> str:
    """Тот же presentation-only порядок, что и в рабочем списке: треть — высокий."""
    scores = [
        row[0]
        for row in session.query(Recommendation.id)
        .join(Deal, Recommendation.deal_id == Deal.id)
        .filter(Deal.company_id == rec.deal.company_id, Recommendation.status == "pending")
        .order_by(Recommendation.priority_score.desc(), Recommendation.id)
        .all()
    ]
    total = len(scores)
    if rec.id not in scores or total == 0:
        return "low"
    rank = scores.index(rec.id) + 1
    if rank <= math.ceil(total / 3):
        return "high"
    if rank <= math.ceil(total * 2 / 3):
        return "mid"
    return "low"


@router.get("/{rec_id}/card")
def recommendation_card(rec_id: int, request: Request, session: Session = Depends(get_db)):
    rec = _load(session, rec_id)
    facts = collect_facts(session, rec)
    breakdown = json.loads(rec.priority_breakdown_json) if rec.priority_breakdown_json else {}

    return templates.TemplateResponse(
        request,
        "deal/card.html",
        {
            "rec": rec,
            "facts": facts,
            "tier": _priority_tier(session, rec),
            "overdue": bool(breakdown.get("overdue_bonus")),
        },
    )


@router.get("/{rec_id}/llm")
def recommendation_llm(
    rec_id: int,
    request: Request,
    refresh: int = 0,
    session: Session = Depends(get_db),
):
    """Ленивая генерация объяснения и черновика с кэшем в message_drafts."""
    rec = _load(session, rec_id)
    fingerprint = facts_fingerprint(rec)

    draft = (
        session.query(MessageDraft)
        .filter(MessageDraft.recommendation_id == rec.id)
        .order_by(MessageDraft.id.desc())
        .first()
    )
    cached = (
        draft is not None
        and not refresh
        and draft.source_fingerprint == fingerprint
        and (draft.generated_text or draft.explanation_text)
    )

    if not cached:
        facts = collect_facts(session, rec)
        explanation = llm.explain_recommendation(facts)
        message = llm.draft_message(facts)
        if explanation or message:
            if draft is None:
                draft = MessageDraft(recommendation_id=rec.id, generated_text="", model_used="")
                session.add(draft)
            draft.generated_text = message or ""
            draft.explanation_text = explanation
            draft.model_used = config.AI_MODEL
            draft.source_fingerprint = fingerprint
            draft.edited_text = None
            session.commit()
        else:
            draft = None

    text = (draft.edited_text or draft.generated_text) if draft else None
    return templates.TemplateResponse(
        request,
        "deal/llm_block.html",
        {
            "rec": rec,
            "explanation": draft.explanation_text if draft else None,
            "draft_text": text or None,
            "llm_configured": llm.is_configured(),
            "from_cache": bool(cached),
        },
    )
