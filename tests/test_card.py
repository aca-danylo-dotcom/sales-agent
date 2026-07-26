"""Карточка рекомендации: единственное действие, ленивый LLM-блок, кэш и fallback."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import config
from app import create_app
from db.models import MessageDraft, Recommendation
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


def test_card_shows_single_action_and_lazy_llm_block(client, rec_id):
    response = client.get(f"/recommendations/{rec_id}/card")
    assert response.status_code == 200
    html = response.text
    assert html.count("Рекомендована дія") == 1
    assert "Що знайшли правила" in html
    assert "Сума угоди" in html
    assert f"/recommendations/{rec_id}/llm" in html


def test_card_404_for_unknown_recommendation(client):
    assert client.get("/recommendations/999999/card").status_code == 404


def test_llm_block_without_api_key(client, rec_id, session, monkeypatch):
    monkeypatch.setattr(config, "AI_API_KEY", "")
    response = client.get(f"/recommendations/{rec_id}/llm")
    assert response.status_code == 200
    assert "AI_API_KEY" in response.text
    assert session.query(MessageDraft).count() == 0


def test_llm_block_survives_provider_failure(client, rec_id, session, monkeypatch):
    monkeypatch.setattr(config, "AI_API_KEY", "test-key")

    def boom(*args, **kwargs):
        raise RuntimeError("kie.ai недоступен")

    monkeypatch.setattr(llm, "_request", boom)
    response = client.get(f"/recommendations/{rec_id}/llm")
    assert response.status_code == 200
    assert "Не вдалося отримати відповідь" in response.text
    assert session.query(MessageDraft).count() == 0


def test_llm_result_is_cached_and_refreshable(client, rec_id, session, monkeypatch):
    monkeypatch.setattr(config, "AI_API_KEY", "test-key")
    calls: list[str] = []

    def fake_request(instructions: str, prompt: str) -> str:
        calls.append(prompt)
        return "Пояснення" if "Поясни менеджеру" in prompt else "Текст чернетки"

    monkeypatch.setattr(llm, "_request", fake_request)

    first = client.get(f"/recommendations/{rec_id}/llm")
    assert first.status_code == 200
    assert "Текст чернетки" in first.text
    assert len(calls) == 2  # explain + draft

    second = client.get(f"/recommendations/{rec_id}/llm")
    assert "Текст чернетки" in second.text
    assert len(calls) == 2, "повторное открытие карточки не должно дёргать LLM"

    refreshed = client.get(f"/recommendations/{rec_id}/llm?refresh=1")
    assert refreshed.status_code == 200
    assert len(calls) == 4
    assert session.query(MessageDraft).count() == 1


def test_stale_fingerprint_triggers_regeneration(client, rec_id, session, monkeypatch):
    monkeypatch.setattr(config, "AI_API_KEY", "test-key")
    calls: list[str] = []
    monkeypatch.setattr(llm, "_request", lambda i, p: (calls.append(p), "Текст")[1])

    client.get(f"/recommendations/{rec_id}/llm")
    assert len(calls) == 2

    rec = session.get(Recommendation, rec_id)
    rec.reason_text = "Изменившаяся причина"
    session.commit()

    client.get(f"/recommendations/{rec_id}/llm")
    assert len(calls) == 4, "смена reason_text должна инвалидировать кэш"
