"""Экран «Подключение»: загрузка CSV, список пользователей, статус этапов."""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from db.models import CsvImport, PipelineStage, User
from services.csv_import import import_deals_csv, import_tasks_csv
from services.detection import recompute_company
from services.prioritization import prioritize_company
from web.deps import get_current_company, get_db

router = APIRouter(prefix="/connect", tags=["connect"])
templates = Jinja2Templates(directory="web/templates")


def _read_upload(file: UploadFile) -> str:
    raw = file.file.read()
    return raw.decode("utf-8-sig")


@router.get("")
def connect_index(request: Request, session: Session = Depends(get_db)):
    company = get_current_company(session)
    session.commit()

    stages = (
        session.query(PipelineStage)
        .filter_by(company_id=company.id)
        .order_by(PipelineStage.order_index)
        .all()
    )
    users = session.query(User).filter_by(company_id=company.id).order_by(User.full_name).all()
    imports = (
        session.query(CsvImport)
        .filter_by(company_id=company.id)
        .order_by(CsvImport.imported_at.desc())
        .limit(10)
        .all()
    )

    return templates.TemplateResponse(
        request,
        "connect/index.html",
        {
            "active_nav": "connect",
            "company": company,
            "stages": stages,
            "users": users,
            "imports": imports,
        },
    )


@router.post("/upload-deals")
def upload_deals(
    request: Request,
    file: UploadFile = File(...),
    session: Session = Depends(get_db),
):
    company = get_current_company(session)
    content = _read_upload(file)
    import_deals_csv(session, company.id, content, file.filename or "deals.csv")
    recompute_company(session, company.id)
    prioritize_company(session, company.id)
    return RedirectResponse(url="/connect", status_code=303)


@router.post("/upload-tasks")
def upload_tasks(
    request: Request,
    file: UploadFile = File(...),
    session: Session = Depends(get_db),
):
    company = get_current_company(session)
    content = _read_upload(file)
    import_tasks_csv(session, company.id, content, file.filename or "tasks.csv")
    recompute_company(session, company.id)
    prioritize_company(session, company.id)
    return RedirectResponse(url="/connect", status_code=303)


@router.post("/users")
def add_user(
    request: Request,
    full_name: str = Form(...),
    email: str = Form(...),
    role: str = Form(...),
    session: Session = Depends(get_db),
):
    company = get_current_company(session)
    session.add(
        User(
            company_id=company.id,
            full_name=full_name.strip(),
            email=email.strip(),
            role=role,
        )
    )
    session.commit()
    return RedirectResponse(url="/connect", status_code=303)
