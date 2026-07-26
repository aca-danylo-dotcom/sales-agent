"""Экран «Налаштування»: пороги правил, веса приоритизации, этапы, режим работы.

Каждое успешное сохранение сразу пересчитывает детекцию и приоритеты, чтобы
рабочий список отражал новые настройки без ожидания фонового джоба.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from db.models import Company
from services import settings as settings_service
from services.detection import recompute_company
from services.prioritization import prioritize_company
from web.deps import get_current_company, get_db

router = APIRouter(prefix="/settings", tags=["settings"])
templates = Jinja2Templates(directory="web/templates")


def _render(
    request: Request,
    session: Session,
    company: Company,
    errors: list[str] | None = None,
    saved: bool = False,
):
    return templates.TemplateResponse(
        request,
        "settings/index.html",
        {
            "active_nav": "settings",
            "company": company,
            "rules": settings_service.rules_view(session, company.id),
            "stages": settings_service.stages_for_company(session, company.id),
            "weight_specs": settings_service.WEIGHT_SPECS,
            "timezones": settings_service.timezone_options(),
            "errors": errors or [],
            "saved": saved,
        },
    )


async def _save(
    request: Request,
    session: Session,
    saver: Callable[[Session, int, Mapping[str, str]], list[str]],
):
    company = get_current_company(session)
    form = await request.form()
    errors = saver(session, company.id, form)
    if errors:
        # Ничего не сохранено — показываем страницу с текущими значениями и списком ошибок.
        return _render(request, session, company, errors=errors)
    recompute_company(session, company.id)
    prioritize_company(session, company.id)
    return RedirectResponse(url="/settings?saved=1", status_code=303)


@router.get("")
def settings_index(request: Request, session: Session = Depends(get_db)):
    company = get_current_company(session)
    session.commit()
    return _render(request, session, company, saved=request.query_params.get("saved") == "1")


@router.post("/rules")
async def save_rules(request: Request, session: Session = Depends(get_db)):
    return await _save(request, session, settings_service.save_rules)


@router.post("/weights")
async def save_weights(request: Request, session: Session = Depends(get_db)):
    return await _save(request, session, settings_service.save_weights)


@router.post("/stages")
async def save_stages(request: Request, session: Session = Depends(get_db)):
    return await _save(request, session, settings_service.save_stages)


@router.post("/company")
async def save_company(request: Request, session: Session = Depends(get_db)):
    return await _save(request, session, settings_service.save_company)
