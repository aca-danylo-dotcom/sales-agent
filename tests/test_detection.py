from __future__ import annotations

from datetime import datetime
from pathlib import Path

from db.models import Deal, Recommendation
from services.csv_import import import_deals_csv, import_tasks_csv
from services.detection import recompute_company

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
NOW = datetime(2026, 7, 25, 12, 0, 0)

EXPECTED_RULES = {
    "E-1": {"NEW_LEAD_NO_RESPONSE"},
    "E-2": {"DEAL_STALE"},
    "E-3": {"PROPOSAL_NO_NEXT_TASK"},
    "E-4": {"NEXT_CONTACT_OVERDUE"},
    "E-5": {"STUCK_ON_STAGE"},
    "E-6": {"NO_NEXT_ACTION"},
    "E-7": set(),
    "E-8": {"DEAL_STALE", "NEXT_CONTACT_OVERDUE"},
}


def _load_edge_case_dataset(session, company):
    deals_csv = (DATA_DIR / "sample_deals_edge_cases.csv").read_text(encoding="utf-8")
    tasks_csv = (DATA_DIR / "sample_tasks_edge_cases.csv").read_text(encoding="utf-8")
    deals_result = import_deals_csv(session, company.id, deals_csv, "sample_deals_edge_cases.csv")
    tasks_result = import_tasks_csv(session, company.id, tasks_csv, "sample_tasks_edge_cases.csv")
    assert deals_result.status == "success"
    assert tasks_result.status == "success"


def _pending_rule_codes_by_external_id(session, company) -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    for deal in session.query(Deal).filter_by(company_id=company.id).all():
        codes = {
            rec.rule_code
            for rec in session.query(Recommendation).filter_by(deal_id=deal.id, status="pending").all()
        }
        result[deal.external_id] = codes
    return result


def test_edge_case_dataset_triggers_exactly_expected_rules(session, company):
    _load_edge_case_dataset(session, company)

    recompute_company(session, company.id, now=NOW)

    actual = _pending_rule_codes_by_external_id(session, company)
    assert actual == EXPECTED_RULES


def test_recompute_is_idempotent(session, company):
    _load_edge_case_dataset(session, company)

    recompute_company(session, company.id, now=NOW)
    first_ids = {rec.id for rec in session.query(Recommendation).filter_by(status="pending").all()}

    recompute_company(session, company.id, now=NOW)
    second_ids = {rec.id for rec in session.query(Recommendation).filter_by(status="pending").all()}

    assert first_ids == second_ids  # повторный прогон не плодит дубли


def test_resolved_condition_expires_pending_recommendation(session, company):
    _load_edge_case_dataset(session, company)
    recompute_company(session, company.id, now=NOW)

    deal = session.query(Deal).filter_by(company_id=company.id, external_id="E-4").one()
    rec = session.query(Recommendation).filter_by(deal_id=deal.id, rule_code="NEXT_CONTACT_OVERDUE").one()
    assert rec.status == "pending"

    deal.next_contact_date = datetime(2026, 7, 27, 12, 0, 0)  # перенесли на будущее
    session.commit()

    recompute_company(session, company.id, now=NOW)

    session.refresh(rec)
    assert rec.status == "expired"
    assert rec.resolved_at == NOW
