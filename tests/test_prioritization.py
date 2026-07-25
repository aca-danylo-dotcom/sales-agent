from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from db.models import Deal, DealTask, PipelineStage, Recommendation
from services.csv_import import import_deals_csv, import_tasks_csv
from services.detection import recompute_company
from services.prioritization import prioritize_company

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
NOW = datetime(2026, 7, 25, 12, 0, 0)

# Ожидаемые баллы посчитаны вручную по дефолтным весам компании (seed):
# weight_amount=30, weight_idle=5, weight_stage=8, weight_overdue_task=15, weight_multi_rule=12.
EXPECTED_SCORES = {
    ("E-1", "NEW_LEAD_NO_RESPONSE"): 16.0,
    ("E-2", "DEAL_STALE"): 50.0,
    ("E-3", "PROPOSAL_NO_NEXT_TASK"): 36.5,
    ("E-4", "NEXT_CONTACT_OVERDUE"): 17.41666667,
    ("E-5", "STUCK_ON_STAGE"): 50.5,
    ("E-6", "NO_NEXT_ACTION"): 25.2,
    ("E-8", "DEAL_STALE"): 85.0,
    ("E-8", "NEXT_CONTACT_OVERDUE"): 85.0,
}

# По убыванию приоритета: E-8 (наложение 2 правил + самая простаивающая и дорогая сделка)
# выше E-5 (дороже и позднее по этапу, но меньше простаивает) выше остальных.
EXPECTED_ORDER = ["E-8", "E-5", "E-2", "E-3", "E-6", "E-4", "E-1"]


def _load_edge_case_dataset(session, company):
    deals_csv = (DATA_DIR / "sample_deals_edge_cases.csv").read_text(encoding="utf-8")
    tasks_csv = (DATA_DIR / "sample_tasks_edge_cases.csv").read_text(encoding="utf-8")
    deals_result = import_deals_csv(session, company.id, deals_csv, "sample_deals_edge_cases.csv")
    tasks_result = import_tasks_csv(session, company.id, tasks_csv, "sample_tasks_edge_cases.csv")
    assert deals_result.status == "success"
    assert tasks_result.status == "success"


def _pending_recommendations(session, company):
    return (
        session.query(Recommendation, Deal)
        .join(Deal, Recommendation.deal_id == Deal.id)
        .filter(Deal.company_id == company.id, Recommendation.status == "pending")
        .all()
    )


def test_priority_score_matches_expected_breakdown(session, company):
    _load_edge_case_dataset(session, company)
    recompute_company(session, company.id, now=NOW)
    prioritize_company(session, company.id, now=NOW)

    actual = {
        (deal.external_id, rec.rule_code): float(rec.priority_score)
        for rec, deal in _pending_recommendations(session, company)
    }

    assert actual.keys() == EXPECTED_SCORES.keys()
    for key, expected_score in EXPECTED_SCORES.items():
        assert actual[key] == pytest.approx(expected_score, abs=0.001)


def test_priority_order_reflects_amount_idle_stage_and_multi_rule_bonus(session, company):
    _load_edge_case_dataset(session, company)
    recompute_company(session, company.id, now=NOW)
    prioritize_company(session, company.id, now=NOW)

    best_score_by_deal: dict[str, float] = {}
    for rec, deal in _pending_recommendations(session, company):
        score = float(rec.priority_score)
        best_score_by_deal[deal.external_id] = max(best_score_by_deal.get(deal.external_id, score), score)

    ordered = sorted(best_score_by_deal, key=lambda ext_id: best_score_by_deal[ext_id], reverse=True)
    assert ordered == EXPECTED_ORDER


def test_prioritize_is_idempotent(session, company):
    _load_edge_case_dataset(session, company)
    recompute_company(session, company.id, now=NOW)

    prioritize_company(session, company.id, now=NOW)
    first = {
        rec.id: float(rec.priority_score)
        for rec in session.query(Recommendation).filter_by(status="pending").all()
    }

    prioritize_company(session, company.id, now=NOW)
    second = {
        rec.id: float(rec.priority_score)
        for rec in session.query(Recommendation).filter_by(status="pending").all()
    }

    assert first == second


def test_priority_breakdown_includes_overdue_bonus(session, company):
    stage = session.query(PipelineStage).filter_by(company_id=company.id, order_index=1).one()
    deal = Deal(
        company_id=company.id,
        external_id="OD-1",
        title="Сделка с просроченной задачей",
        stage_id=stage.id,
        amount=10000,
        currency="USD",
        status="open",
        last_activity_at=NOW,
    )
    session.add(deal)
    session.flush()

    session.add(
        DealTask(
            deal_id=deal.id,
            source="crm_import",
            text="Просроченная задача",
            due_at=datetime(2026, 7, 20, 12, 0, 0),
            status="open",
        )
    )
    session.add(
        Recommendation(
            deal_id=deal.id,
            rule_code="DEAL_STALE",
            recommended_action="follow_up",
            reason_text="test",
            status="pending",
            detected_at=NOW,
        )
    )
    session.commit()

    prioritize_company(session, company.id, now=NOW)

    rec = session.query(Recommendation).filter_by(deal_id=deal.id).one()
    breakdown = json.loads(rec.priority_breakdown_json)
    assert breakdown["overdue_bonus"] == 1
