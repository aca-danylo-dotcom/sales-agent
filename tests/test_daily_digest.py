"""Ежедневный список менеджера: джоб формирует daily_digest_items,
менеджер видит только свои сделки.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import config
from app import create_app
from db.models import DailyDigestItem, Deal, Recommendation, User
from services import daily_digest, scheduler
from services.csv_import import import_deals_csv, import_tasks_csv
from services.detection import recompute_company
from services.prioritization import prioritize_company
from web.deps import get_db

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
NOW = datetime(2026, 7, 25, 12, 0, 0)


@pytest.fixture()
def data(session, company, monkeypatch):
    monkeypatch.setattr(config, "now_local", lambda: NOW)
    deals_csv = (DATA_DIR / "sample_deals_edge_cases.csv").read_text(encoding="utf-8")
    tasks_csv = (DATA_DIR / "sample_tasks_edge_cases.csv").read_text(encoding="utf-8")
    import_deals_csv(session, company.id, deals_csv, "deals.csv")
    import_tasks_csv(session, company.id, tasks_csv, "tasks.csv")
    recompute_company(session, company.id, now=NOW)
    prioritize_company(session, company.id, now=NOW)
    session.commit()
    return company


@pytest.fixture()
def client(session, data) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_db] = lambda: session
    return TestClient(app)


def _user(session, email: str) -> User:
    return session.query(User).filter(User.email == email).one()


def _items(session, user_id: int | None = None) -> list[DailyDigestItem]:
    query = session.query(DailyDigestItem)
    if user_id is not None:
        query = query.filter(DailyDigestItem.user_id == user_id)
    return query.all()


def _open_recommendations(session, company_id: int) -> list[Recommendation]:
    return (
        session.query(Recommendation)
        .join(Deal, Recommendation.deal_id == Deal.id)
        .filter(Deal.company_id == company_id, Recommendation.status == "pending")
        .all()
    )


# --- сборка списка -----------------------------------------------------------


def test_build_creates_item_per_recommendation_for_its_owner(session, data):
    created = daily_digest.build_digest(session, data.id, now=NOW)

    recommendations = {rec.id: rec for rec in _open_recommendations(session, data.id)}
    assert created == len(recommendations) > 0

    for item in _items(session):
        assert item.company_id == data.id
        assert item.digest_date == NOW.replace(hour=0, minute=0, second=0, microsecond=0)
        assert item.status == "pending"
        # ключевое: пункт попал именно владельцу сделки
        assert item.user_id == recommendations[item.recommendation_id].deal.owner_user_id


def test_build_is_idempotent(session, data):
    first = daily_digest.build_digest(session, data.id, now=NOW)
    second = daily_digest.build_digest(session, data.id, now=NOW)

    assert first > 0
    assert second == 0, "повторный прогон за те же сутки не должен дублировать пункты"
    assert len(_items(session)) == first


def test_deal_without_owner_is_not_in_any_digest(session, data):
    rec = _open_recommendations(session, data.id)[0]
    rec.deal.owner_user_id = None
    session.commit()

    daily_digest.build_digest(session, data.id, now=NOW)

    assert all(item.recommendation_id != rec.id for item in _items(session))


def test_both_managers_get_only_their_own_recommendations(session, data):
    daily_digest.build_digest(session, data.id, now=NOW)
    oleg, irina = _user(session, "oleg@demo.local"), _user(session, "irina@demo.local")

    oleg_items = _items(session, oleg.id)
    irina_items = _items(session, irina.id)
    assert oleg_items and irina_items, "оба менеджера должны получить свои пункты"
    assert not {i.recommendation_id for i in oleg_items} & {i.recommendation_id for i in irina_items}


# --- джоб планировщика -------------------------------------------------------


def test_daily_digest_job_builds_items(session, data, monkeypatch):
    monkeypatch.setattr(scheduler, "SessionLocal", lambda: session)

    scheduler.daily_digest_job()

    assert len(_items(session)) == len(_open_recommendations(session, data.id)) > 0


def test_daily_digest_job_waits_for_company_morning(session, data, monkeypatch):
    monkeypatch.setattr(scheduler, "SessionLocal", lambda: session)
    monkeypatch.setattr(config, "now_local", lambda: NOW.replace(hour=6))

    scheduler.daily_digest_job()

    assert _items(session) == [], "до утреннего часа компании список дня не формируется"


# --- экран менеджера ---------------------------------------------------------


def test_screen_shows_only_own_deals(client, session, data):
    oleg, irina = _user(session, "oleg@demo.local"), _user(session, "irina@demo.local")

    html = client.get(f"/my-day?user_id={oleg.id}").text
    oleg_rec_ids = {i.recommendation_id for i in _items(session, oleg.id)}
    irina_rec_ids = {i.recommendation_id for i in _items(session, irina.id)}

    assert oleg_rec_ids and irina_rec_ids
    for rec_id in oleg_rec_ids:
        assert f'id="rec-row-{rec_id}"' in html
    for rec_id in irina_rec_ids:
        assert f'id="rec-row-{rec_id}"' not in html, "чужие сделки на экране менеджера недопустимы"


def test_screen_builds_digest_on_first_open(client, session, data):
    assert _items(session) == []
    assert client.get("/my-day").status_code == 200
    assert _items(session), "экран дособирает список дня, если джоб ещё не отработал"


def test_screen_switches_between_managers(client, session, data):
    irina = _user(session, "irina@demo.local")
    html = client.get(f"/my-day?user_id={irina.id}").text

    assert "Ирина Менеджер" in html
    for rec_id in {i.recommendation_id for i in _items(session, irina.id)}:
        assert f'id="rec-row-{rec_id}"' in html


def test_confirmed_item_stays_in_day_list_as_done(client, session, data):
    oleg = _user(session, "oleg@demo.local")
    client.get(f"/my-day?user_id={oleg.id}")
    rec_id = _items(session, oleg.id)[0].recommendation_id

    client.post(f"/recommendations/{rec_id}/confirm")
    html = client.get(f"/my-day?user_id={oleg.id}").text

    item = next(i for i in _items(session, oleg.id) if i.recommendation_id == rec_id)
    assert item.status == "done"
    assert "Зроблено" in html
    assert f'hx-get="/recommendations/{rec_id}/card"' not in html, "отработанный пункт не кликабелен"


def test_rejected_item_is_marked_dismissed(client, session, data, monkeypatch):
    monkeypatch.setattr(config, "AI_API_KEY", "")
    oleg = _user(session, "oleg@demo.local")
    client.get(f"/my-day?user_id={oleg.id}")
    rec_id = _items(session, oleg.id)[0].recommendation_id

    client.post(f"/recommendations/{rec_id}/reject", data={"reason_text": "Клієнт відмовився"})
    client.get(f"/my-day?user_id={oleg.id}")

    item = next(i for i in _items(session, oleg.id) if i.recommendation_id == rec_id)
    assert item.status == "dismissed"


def test_screen_survives_company_without_managers(client, session, data):
    for user in session.query(User).all():
        user.is_active = False
    session.commit()

    response = client.get("/my-day")
    assert response.status_code == 200
    assert "Ще немає жодного менеджера" in response.text


def test_action_returns_to_the_screen_it_came_from(client, session, data):
    oleg = _user(session, "oleg@demo.local")
    client.get(f"/my-day?user_id={oleg.id}")
    rec_id = _items(session, oleg.id)[0].recommendation_id

    response = client.post(
        f"/recommendations/{rec_id}/confirm",
        headers={"HX-Current-URL": f"http://testserver/my-day?user_id={oleg.id}"},
    )
    assert f'href="/my-day?user_id={oleg.id}"' in response.text
