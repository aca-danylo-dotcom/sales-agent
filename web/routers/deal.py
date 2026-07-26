"""Карточка рекомендации: факты сделки, единственное действие, LLM-блок и действия.

Карточка отдаётся htmx-фрагментом в правую панель рабочего списка. LLM-блок
(объяснение + черновик) грузится вторым запросом — карточка с фактами и
действием видна сразу и не зависит от доступности модели.

Confirm/reject/snooze тоже htmx-запросы из карточки: решение принимает backend
(services/actions.py), сюда возвращается только отрисовка результата.
"""
from __future__ import annotations

import json
import math
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, selectinload

import config
from db.models import Deal, MessageDraft, Recommendation
from services import llm
from services.actions import (
    DEFAULT_SNOOZE,
    REJECTION_LABELS,
    SNOOZE_PRESETS,
    confirm_recommendation,
    reject_recommendation,
    snooze_recommendation,
)
from services.recommendation import collect_facts, facts_fingerprint
from services.uk_format import format_datetime_uk
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


_STATUS_TITLES = {
    "confirmed": "Рекомендацію підтверджено",
    "rejected": "Рекомендацію позначено як неактуальну",
    "snoozed": "Рекомендацію відкладено",
    "expired": "Рекомендація більше не актуальна",
}


def _back_url(request: Request) -> str:
    """Экран, с которого пришёл htmx-запрос (рабочий список или «Мій день»)."""
    current = request.headers.get("HX-Current-URL")
    if not current:
        return "/"
    parts = urlsplit(current)
    path = parts.path or "/"
    return f"{path}?{parts.query}" if parts.query else path


def _resolved(request: Request, session: Session, rec: Recommendation, message: str):
    """Панель «дію виконано» + oob-удаление строки из рабочего списка."""
    facts = collect_facts(session, rec)
    return templates.TemplateResponse(
        request,
        "deal/resolved.html",
        {
            "rec": rec,
            "facts": facts,
            "title": _STATUS_TITLES.get(rec.status, "Дію виконано"),
            "message": message,
            "back_url": _back_url(request),
        },
    )


def _already_resolved_message(rec: Recommendation) -> str:
    return "Цю рекомендацію вже опрацьовано раніше. Оновіть робочий список."


@router.get("/{rec_id}/footer")
def recommendation_footer(rec_id: int, request: Request, session: Session = Depends(get_db)):
    """Возврат к обычным кнопкам действий (отмена формы отказа/відкладення)."""
    rec = _load(session, rec_id)
    return templates.TemplateResponse(request, "deal/footer.html", {"rec": rec})


@router.get("/{rec_id}/reject-form")
def recommendation_reject_form(rec_id: int, request: Request, session: Session = Depends(get_db)):
    rec = _load(session, rec_id)
    return templates.TemplateResponse(request, "deal/reject_form.html", {"rec": rec})


@router.get("/{rec_id}/snooze-form")
def recommendation_snooze_form(rec_id: int, request: Request, session: Session = Depends(get_db)):
    rec = _load(session, rec_id)
    return templates.TemplateResponse(
        request,
        "deal/snooze_form.html",
        {"rec": rec, "presets": SNOOZE_PRESETS, "default_preset": DEFAULT_SNOOZE},
    )


@router.post("/{rec_id}/confirm")
def recommendation_confirm(rec_id: int, request: Request, session: Session = Depends(get_db)):
    """Підтвердити: создаём задачу со сроком и ответственным, пишем аудит."""
    rec = _load(session, rec_id)
    if rec.status not in ("pending", "snoozed"):
        return _resolved(request, session, rec, _already_resolved_message(rec))

    task = confirm_recommendation(session, rec)
    assignee = rec.deal.owner.full_name if rec.deal.owner else "не призначений"
    due = format_datetime_uk(task.due_at) if task.due_at else "без терміну"
    return _resolved(
        request,
        session,
        rec,
        f"Створено завдання: {task.text} Термін: {due}. Відповідальний: {assignee}.",
    )


@router.post("/{rec_id}/reject")
def recommendation_reject(
    rec_id: int,
    request: Request,
    reason_text: str = Form(""),
    session: Session = Depends(get_db),
):
    """Неактуально: свободный текст причины классифицируется в категорию для статистики."""
    rec = _load(session, rec_id)
    if rec.status not in ("pending", "snoozed"):
        return _resolved(request, session, rec, _already_resolved_message(rec))

    category = reject_recommendation(session, rec, reason_text)
    label = REJECTION_LABELS.get(category, category)
    return _resolved(
        request,
        session,
        rec,
        f"Причина збережена як «{label}». Правило не підніматиме цю угоду найближчим часом.",
    )


@router.post("/{rec_id}/snooze")
def recommendation_snooze(
    rec_id: int,
    request: Request,
    preset: str = Form(DEFAULT_SNOOZE),
    session: Session = Depends(get_db),
):
    """Відкласти: рекомендация уходит из работы до срока и возвращается сама."""
    rec = _load(session, rec_id)
    if rec.status not in ("pending", "snoozed"):
        return _resolved(request, session, rec, _already_resolved_message(rec))

    until = snooze_recommendation(session, rec, preset)
    return _resolved(
        request,
        session,
        rec,
        f"Повернеться в робочий список {format_datetime_uk(until)}.",
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
