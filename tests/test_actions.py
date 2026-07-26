"""Действия по рекомендации: підтвердити / відхилити / відкласти.

Проверяем то, что видит менеджер и что остаётся в БД: задача со сроком и
ответственным, категория причины отказа, возврат отложенного в работу и запись
каждого действия в action_log.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import config
from app import create_app
from db.models import ActionLog, DealTask, Recommendation
from services import llm
from services.csv_import import import_deals_csv, import_tasks_csv
from services.detection import recompute_company
from services.prioritization import prioritize_company
from web.deps import get_db

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
NOW = datetime(2026, 7, 25, 12, 0, 0)


@pytest.fixture()
def client(session, company, monkeypatch) -> TestClient:
    monkeypatch.setattr(config, "now_local", lambda: NOW)
    deals_csv = (DATA_DIR / "sample_deals_edge_cases.csv").read_text(encoding="utf-8")
    tasks_csv = (DATA_DIR / "sample_tasks_edge_cases.csv").read_text(encoding="utf-8")
    import_deals_csv(session, company.id, deals_csv, "deals.csv")
    import_tasks_csv(session, company.id, tasks_csv, "tasks.csv")
    recompute_company(session, company.id, now=NOW)
    prioritize_company(session, company.id, now=NOW)
    session.commit()

    app = create_app()
    app.dependency_overrides[get_db] = lambda: session
    return TestClient(app)


@pytest.fixture()
def rec_id(session, company) -> int:
    rec = (
        session.query(Recommendation)
        .filter(Recommendation.status == "pending")
        .order_by(Recommendation.priority_score.desc())
        .first()
    )
    assert rec is not None
    return rec.id


def _actions(session, rec_id: int) -> list[str]:
    return [
        row.action_type
        for row in session.query(ActionLog).filter(ActionLog.recommendation_id == rec_id).all()
    ]


# --- підтвердити -------------------------------------------------------------


def test_confirm_creates_task_with_due_owner_and_reason(client, session, rec_id):
    response = client.post(f"/recommendations/{rec_id}/confirm")
    assert response.status_code == 200

    task = session.query(DealTask).filter(DealTask.recommendation_id == rec_id).one()
    rec = session.get(Recommendation, rec_id)

    assert task.source == "system"
    assert task.status == "open"
    assert task.deal_id == rec.deal_id
    assert task.assignee_user_id is not None
    assert task.assignee_user_id == rec.deal.owner_user_id
    assert task.due_at is not None and task.due_at > NOW
    assert rec.reason_text in task.text, "в задаче должна быть причина из детекции"


def test_confirm_closes_recommendation_and_writes_action_log(client, session, rec_id):
    client.post(f"/recommendations/{rec_id}/confirm")

    rec = session.get(Recommendation, rec_id)
    assert rec.status == "confirmed"
    assert rec.resolved_at == NOW
    assert rec.resolved_by_user_id == rec.deal.owner_user_id

    assert _actions(session, rec_id) == ["recommendation_confirmed", "task_created"]


def test_confirmed_recommendation_leaves_worklist(client, session, rec_id):
    client.post(f"/recommendations/{rec_id}/confirm")
    html = client.get("/").text
    assert f'/recommendations/{rec_id}/card' not in html


def test_confirm_response_removes_row_from_list(client, rec_id):
    response = client.post(f"/recommendations/{rec_id}/confirm")
    assert f'id="rec-row-{rec_id}"' in response.text
    assert 'hx-swap-oob="delete"' in response.text


def test_double_confirm_does_not_duplicate_task(client, session, rec_id):
    client.post(f"/recommendations/{rec_id}/confirm")
    second = client.post(f"/recommendations/{rec_id}/confirm")

    assert second.status_code == 200
    assert "вже опрацьовано" in second.text
    assert session.query(DealTask).filter(DealTask.recommendation_id == rec_id).count() == 1
    assert _actions(session, rec_id) == ["recommendation_confirmed", "task_created"]


def test_confirmed_recommendation_not_recreated_by_detection(client, session, company, rec_id):
    rec = session.get(Recommendation, rec_id)
    deal_id, rule_code = rec.deal_id, rec.rule_code
    client.post(f"/recommendations/{rec_id}/confirm")

    recompute_company(session, company.id, now=NOW)

    same_problem = (
        session.query(Recommendation)
        .filter(Recommendation.deal_id == deal_id, Recommendation.rule_code == rule_code)
        .all()
    )
    assert len(same_problem) == 1, "в течение cooldown правило не поднимает проблему заново"


# --- відхилити ---------------------------------------------------------------


def test_reject_classifies_free_text(client, session, rec_id, monkeypatch):
    monkeypatch.setattr(config, "AI_API_KEY", "test-key")
    prompts: list[str] = []

    def fake_request(instructions: str, prompt: str) -> str:
        prompts.append(prompt)
        return "already_done"

    monkeypatch.setattr(llm, "_request", fake_request)

    response = client.post(
        f"/recommendations/{rec_id}/reject",
        data={"reason_text": "Я вже телефонував клієнту вчора, в CRM просто не записав"},
    )
    assert response.status_code == 200

    rec = session.get(Recommendation, rec_id)
    assert rec.status == "rejected"
    assert rec.rejection_reason_category == "already_done"
    assert rec.resolved_at == NOW
    assert len(prompts) == 1 and "телефонував" in prompts[0]
    assert _actions(session, rec_id) == ["recommendation_rejected"]


def test_reject_falls_back_to_other_on_unknown_category(client, session, rec_id, monkeypatch):
    monkeypatch.setattr(config, "AI_API_KEY", "test-key")
    monkeypatch.setattr(llm, "_request", lambda i, p: "щось своє")

    client.post(f"/recommendations/{rec_id}/reject", data={"reason_text": "не зрозуміло"})
    assert session.get(Recommendation, rec_id).rejection_reason_category == "other"


def test_reject_without_llm_still_works(client, session, rec_id, monkeypatch):
    monkeypatch.setattr(config, "AI_API_KEY", "")

    response = client.post(f"/recommendations/{rec_id}/reject", data={"reason_text": ""})
    assert response.status_code == 200

    rec = session.get(Recommendation, rec_id)
    assert rec.status == "rejected"
    assert rec.rejection_reason_category == "other"
    assert _actions(session, rec_id) == ["recommendation_rejected"]


def test_reject_stores_free_text_in_action_log(client, session, rec_id, monkeypatch):
    monkeypatch.setattr(config, "AI_API_KEY", "")
    client.post(f"/recommendations/{rec_id}/reject", data={"reason_text": "Угода вже програна"})

    entry = session.query(ActionLog).filter(ActionLog.recommendation_id == rec_id).one()
    assert "Угода вже програна" in entry.details_json


# --- відкласти ---------------------------------------------------------------


def test_snooze_sets_deadline_and_hides_from_worklist(client, session, rec_id):
    response = client.post(f"/recommendations/{rec_id}/snooze", data={"preset": "1d"})
    assert response.status_code == 200

    rec = session.get(Recommendation, rec_id)
    assert rec.status == "snoozed"
    assert rec.snoozed_until == NOW + timedelta(hours=24)
    assert rec.resolved_at is None, "решение по проблеме не принято — она вернётся"
    assert _actions(session, rec_id) == ["recommendation_snoozed"]

    assert f'/recommendations/{rec_id}/card' not in client.get("/").text


def test_snoozed_returns_to_worklist_after_deadline(client, session, rec_id):
    client.post(f"/recommendations/{rec_id}/snooze", data={"preset": "4h"})

    rec = session.get(Recommendation, rec_id)
    rec.snoozed_until = NOW - timedelta(minutes=1)
    session.commit()

    html = client.get("/").text
    assert f'/recommendations/{rec_id}/card' in html

    session.refresh(rec)
    assert rec.status == "pending"
    assert rec.snoozed_until is None


def test_snoozed_recommendation_is_not_duplicated_by_detection(client, session, company, rec_id):
    client.post(f"/recommendations/{rec_id}/snooze", data={"preset": "7d"})
    rec = session.get(Recommendation, rec_id)
    deal_id, rule_code = rec.deal_id, rec.rule_code

    recompute_company(session, company.id, now=NOW)

    same_problem = (
        session.query(Recommendation)
        .filter(Recommendation.deal_id == deal_id, Recommendation.rule_code == rule_code)
        .all()
    )
    assert len(same_problem) == 1
    assert same_problem[0].status == "snoozed"


# --- формы -------------------------------------------------------------------


def test_forms_and_footer_are_reachable(client, rec_id):
    reject_form = client.get(f"/recommendations/{rec_id}/reject-form")
    assert reject_form.status_code == 200
    assert 'name="reason_text"' in reject_form.text

    snooze_form = client.get(f"/recommendations/{rec_id}/snooze-form")
    assert snooze_form.status_code == 200
    assert 'value="1d" checked' in snooze_form.text

    footer = client.get(f"/recommendations/{rec_id}/footer")
    assert footer.status_code == 200
    assert f"/recommendations/{rec_id}/confirm" in footer.text


def test_card_has_active_action_buttons(client, rec_id):
    html = client.get(f"/recommendations/{rec_id}/card").text
    assert f'hx-post="/recommendations/{rec_id}/confirm"' in html
    assert f'/recommendations/{rec_id}/snooze-form' in html
    assert f'/recommendations/{rec_id}/reject-form' in html
    assert "disabled" not in html
