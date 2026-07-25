"""In-memory SQLite на тест-сессию + базовые фикстуры компании/пользователей."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from db.base import Base
from db.models import Company, User
from db.seed import seed_company


@pytest.fixture()
def session() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    local_session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)
    db = local_session()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture()
def company(session: Session) -> Company:
    company = Company(name="Test Co")
    session.add(company)
    session.flush()
    seed_company(session, company)

    session.add_all(
        [
            User(company_id=company.id, full_name="Олег Менеджер", email="oleg@demo.local", role="manager"),
            User(company_id=company.id, full_name="Ирина Менеджер", email="irina@demo.local", role="manager"),
        ]
    )
    session.commit()
    return company
