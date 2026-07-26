"""Экран «Налаштування»: смена порогов/весов/этапов и её влияние на рабочий список.

Главный критерий фазы: смена порога и пересчёт воспроизводимо меняют состав worklist.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import config
from app import create_app
from db.models import Deal, Recommendation
from services import settings as settings_service
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
    return TestClient(app, follow_redirects=False)


def _worklist(session, company_id: int) -> set[tuple[str, str]]:
    """Состав рабочего списка: пары (external_id сделки, код правила)."""
    rows = (
        session.query(Recommendation)
        .join(Deal, Recommendation.deal_id == Deal.id)
        .filter(Deal.company_id == company_id, Recommendation.status == "pending")
        .all()
    )
    return {(rec.deal.external_id, rec.rule_code) for rec in rows}


def _rules_form(session, company_id: int, *, params=None, disabled=()) -> dict[str, str]:
    """Форма правил целиком (как её шлёт браузер) с точечными подменами."""
    form: dict[str, str] = {}
    for rule in settings_service.rules_for_company(session, company_id):
        if rule.enabled and rule.code not in disabled:
            form[f"enabled__{rule.code}"] = "on"
        current = settings_service.rule_params(rule)
        for spec in settings_service.RULE_SPECS.get(rule.code, ()):
            value = current.get(spec.key, spec.default)
            if params and spec.key in params.get(rule.code, {}):
                value = params[rule.code][spec.key]
            form[f"param__{rule.code}__{spec.key}"] = str(value)
    return form


def _stages_form(session, company_id: int, renames=None) -> dict[str, str]:
    renames = renames or {}
    return {
        f"stage_name__{stage.id}": renames.get(stage.name, stage.name)
        for stage in settings_service.stages_for_company(session, company_id)
    }


def _rule(session, company_id: int, code: str):
    return next(r for r in settings_service.rules_for_company(session, company_id) if r.code == code)


# --- экран --------------------------------------------------------------------


def test_settings_page_renders(client, session, data):
    response = client.get("/settings")

    assert response.status_code == 200
    assert "Правила детекції" in response.text
    assert "Ваги пріоритету" in response.text
    assert "Сделка зависла без активности" in response.text
    assert 'name="param__DEAL_STALE__days_threshold"' in response.text


# --- критерий фазы: порог -> состав worklist ----------------------------------


def test_threshold_change_changes_worklist_and_is_reversible(client, session, data):
    before = _worklist(session, data.id)
    assert ("E-2", "DEAL_STALE") in before
    assert ("E-8", "DEAL_STALE") in before

    # Порог «зависшей сделки» 5 -> 8 дней: E-2 (6 дн) и E-8 (7 дн) больше не проблемные.
    response = client.post(
        "/settings/rules",
        data=_rules_form(session, data.id, params={"DEAL_STALE": {"days_threshold": 8}}),
    )
    assert response.status_code == 303

    raised = _worklist(session, data.id)
    assert ("E-2", "DEAL_STALE") not in raised
    assert ("E-8", "DEAL_STALE") not in raised
    # остальные правила не затронуты
    assert ("E-8", "NEXT_CONTACT_OVERDUE") in raised
    assert before - raised == {("E-2", "DEAL_STALE"), ("E-8", "DEAL_STALE")}

    # Возврат порога воспроизводит исходный состав списка.
    client.post(
        "/settings/rules",
        data=_rules_form(session, data.id, params={"DEAL_STALE": {"days_threshold": 5}}),
    )
    assert _worklist(session, data.id) == before


def test_threshold_change_is_visible_on_worklist_page(client, session, data):
    assert "ТестКо2" in client.get("/").text  # E-2 висит в списке из-за DEAL_STALE

    client.post(
        "/settings/rules",
        data=_rules_form(session, data.id, params={"DEAL_STALE": {"days_threshold": 8}}),
    )

    assert "ТестКо2" not in client.get("/").text


def test_disabled_rule_clears_its_recommendations(client, session, data):
    client.post("/settings/rules", data=_rules_form(session, data.id, disabled=("DEAL_STALE",)))

    assert not _rule(session, data.id, "DEAL_STALE").enabled
    assert not [pair for pair in _worklist(session, data.id) if pair[1] == "DEAL_STALE"]
    assert ("E-1", "NEW_LEAD_NO_RESPONSE") in _worklist(session, data.id)


def test_invalid_threshold_saves_nothing(client, session, data):
    before = _worklist(session, data.id)

    response = client.post(
        "/settings/rules",
        data=_rules_form(
            session,
            data.id,
            params={"DEAL_STALE": {"days_threshold": "abc"}, "NO_NEXT_ACTION": {"hours_threshold": 999999}},
        ),
    )

    assert response.status_code == 200
    assert "Нічого не збережено" in response.text
    assert settings_service.rule_params(_rule(session, data.id, "DEAL_STALE"))["days_threshold"] == 5
    assert _worklist(session, data.id) == before


def test_rule_can_be_limited_to_stages(client, session, data):
    stages = settings_service.stages_for_company(session, data.id)
    negotiation = next(stage for stage in stages if stage.name == "Переговоры")

    form = _rules_form(session, data.id)
    form["stages__DEAL_STALE"] = str(negotiation.id)
    response = client.post("/settings/rules", data=form)

    assert response.status_code == 303
    # E-2 и E-8 стоят на «В работе» — правило туда больше не смотрит
    assert not [pair for pair in _worklist(session, data.id) if pair[1] == "DEAL_STALE"]


# --- веса ---------------------------------------------------------------------


def test_weights_change_priority_score(client, session, data):
    scores_before = {rec.id: rec.priority_score for rec in session.query(Recommendation).all()}

    response = client.post(
        "/settings/weights",
        data={"weight_amount": 0, "weight_idle": 5, "weight_stage": 8, "weight_overdue_task": 15, "weight_multi_rule": 12},
    )

    assert response.status_code == 303
    assert session.get(type(data), data.id).weight_amount == 0
    scores_after = {rec.id: rec.priority_score for rec in session.query(Recommendation).all()}
    assert scores_after != scores_before


def test_negative_weight_saves_nothing(client, session, data):
    response = client.post(
        "/settings/weights",
        data={"weight_amount": -5, "weight_idle": 5, "weight_stage": 8, "weight_overdue_task": 15, "weight_multi_rule": 12},
    )

    assert response.status_code == 200
    assert session.get(type(data), data.id).weight_amount == 30


# --- этапы --------------------------------------------------------------------


def test_stage_rename_follows_into_rule_params(client, session, data):
    response = client.post(
        "/settings/stages",
        data=_stages_form(session, data.id, {"Предложение отправлено": "КП надіслано"}),
    )

    assert response.status_code == 303
    params = settings_service.rule_params(_rule(session, data.id, "PROPOSAL_NO_NEXT_TASK"))
    assert params["stage_name"] == "КП надіслано"
    # правило продолжает работать после переименования этапа
    assert ("E-3", "PROPOSAL_NO_NEXT_TASK") in _worklist(session, data.id)


def test_duplicate_stage_names_rejected(client, session, data):
    response = client.post(
        "/settings/stages",
        data=_stages_form(session, data.id, {"В работе": "Новый лид"}),
    )

    assert response.status_code == 200
    assert "унікальними" in response.text
    names = [stage.name for stage in settings_service.stages_for_company(session, data.id)]
    assert names.count("Новый лид") == 1


# --- режим работы -------------------------------------------------------------


def test_company_settings_saved(client, session, data):
    response = client.post(
        "/settings/company",
        data={
            "name": "ТестКо",
            "timezone": "Europe/Warsaw",
            "digest_hour": 10,
            "resolved_cooldown_days": 3,
        },
    )

    assert response.status_code == 303
    company = session.get(type(data), data.id)
    assert (company.name, company.timezone, company.digest_hour, company.resolved_cooldown_days) == (
        "ТестКо",
        "Europe/Warsaw",
        10,
        3,
    )


def test_unknown_timezone_saves_nothing(client, session, data):
    response = client.post(
        "/settings/company",
        data={"name": "ТестКо", "timezone": "Europe/Atlantis", "digest_hour": 8, "resolved_cooldown_days": 7},
    )

    assert response.status_code == 200
    assert "Atlantis" in response.text
    assert session.get(type(data), data.id).name != "ТестКо"


def test_cooldown_setting_controls_repeat_recommendations(client, session, data):
    rec = (
        session.query(Recommendation)
        .join(Deal, Recommendation.deal_id == Deal.id)
        .filter(Deal.company_id == data.id, Recommendation.rule_code == "DEAL_STALE")
        .first()
    )
    rec.status = "confirmed"
    rec.resolved_at = NOW
    session.commit()

    # Пауза 7 дней (дефолт) — правило не поднимает ту же проблему заново.
    recompute_company(session, data.id, now=NOW)
    assert (
        session.query(Recommendation)
        .filter_by(deal_id=rec.deal_id, rule_code="DEAL_STALE", status="pending")
        .count()
        == 0
    )

    client.post(
        "/settings/company",
        data={
            "name": data.name,
            "timezone": data.timezone,
            "digest_hour": data.digest_hour,
            "resolved_cooldown_days": 0,
        },
    )

    assert (
        session.query(Recommendation)
        .filter_by(deal_id=rec.deal_id, rule_code="DEAL_STALE", status="pending")
        .count()
        == 1
    )
