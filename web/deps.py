"""Общие зависимости FastAPI: сессия БД, текущая компания.

Полноценной авторизации в MVP пока нет — используется единственная компания,
создаваемая лениво при первом обращении (задел на мультитенантность уже в схеме).
"""
from __future__ import annotations

from collections.abc import Generator

from sqlalchemy.orm import Session

from db.base import SessionLocal
from db.models import Company
from db.seed import seed_company


def get_db() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def get_current_company(session: Session) -> Company:
    company = session.query(Company).order_by(Company.id).first()
    if company is not None:
        return company

    company = Company(name="Demo Company")
    session.add(company)
    session.flush()
    seed_company(session, company)
    return company
