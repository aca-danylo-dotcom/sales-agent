from __future__ import annotations

from decimal import Decimal

from db.models import Contact, Deal, DealStageHistory, DealTask
from services.csv_import import import_deals_csv, import_tasks_csv

DEALS_HEADER = (
    "external_deal_id,title,contact_name,contact_phone,contact_email,company_name,"
    "owner_email,stage_name,amount,currency,created_at,last_activity_at,"
    "next_contact_date,last_note\n"
)

TASKS_HEADER = "external_task_id,external_deal_id,text,due_at,status,assignee_email\n"


def _deal_row(
    external_id="D-1",
    title="Тестовая сделка",
    stage="Новый лид",
    owner="oleg@demo.local",
    amount="10000",
    note="Первый контакт",
):
    return (
        f"{external_id},{title},Иван Иванов,+380501112233,ivan@ex.ua,ExampleCo,"
        f"{owner},{stage},{amount},USD,2026-07-01,2026-07-01,2026-07-05,{note}\n"
    )


def test_import_deals_creates_deal_and_contact(session, company):
    content = DEALS_HEADER + _deal_row()
    result = import_deals_csv(session, company.id, content, "deals.csv")

    assert result.status == "success"
    assert result.row_count == 1

    deal = session.query(Deal).filter_by(company_id=company.id, external_id="D-1").one()
    assert deal.title == "Тестовая сделка"
    assert deal.amount == Decimal("10000")
    assert deal.stage.name == "Новый лид"
    assert deal.owner.email == "oleg@demo.local"

    contact = session.query(Contact).filter_by(company_id=company.id).one()
    assert contact.name == "Иван Иванов"
    assert deal.contact_id == contact.id

    # первичная загрузка тоже пишет запись в историю (from_stage_id=None)
    history = session.query(DealStageHistory).filter_by(deal_id=deal.id).all()
    assert len(history) == 1
    assert history[0].from_stage_id is None
    assert history[0].to_stage_id == deal.stage_id


def test_reimport_with_new_stage_writes_history_without_duplicating_deal(session, company):
    content_v1 = DEALS_HEADER + _deal_row(stage="Новый лид")
    import_deals_csv(session, company.id, content_v1, "deals.csv")

    content_v2 = DEALS_HEADER + _deal_row(stage="В работе")
    import_deals_csv(session, company.id, content_v2, "deals.csv")

    deals = session.query(Deal).filter_by(company_id=company.id, external_id="D-1").all()
    assert len(deals) == 1  # upsert, не дубль
    assert deals[0].stage.name == "В работе"

    history = (
        session.query(DealStageHistory)
        .filter_by(deal_id=deals[0].id)
        .order_by(DealStageHistory.id)
        .all()
    )
    assert len(history) == 2
    assert history[1].to_stage_id == deals[0].stage_id

    contacts = session.query(Contact).filter_by(company_id=company.id).all()
    assert len(contacts) == 1  # контакт тоже не задублировался


def test_reimport_same_stage_does_not_duplicate_history(session, company):
    content = DEALS_HEADER + _deal_row()
    import_deals_csv(session, company.id, content, "deals.csv")
    import_deals_csv(session, company.id, content, "deals.csv")

    deal = session.query(Deal).filter_by(company_id=company.id, external_id="D-1").one()
    history = session.query(DealStageHistory).filter_by(deal_id=deal.id).all()
    assert len(history) == 1


def test_unknown_stage_reports_row_error_without_crashing(session, company):
    content = DEALS_HEADER + _deal_row(external_id="D-2", stage="Несуществующий этап")
    result = import_deals_csv(session, company.id, content, "deals.csv")

    assert result.status == "failed"
    assert result.row_count == 1
    assert "Несуществующий этап" in result.error_log

    assert session.query(Deal).filter_by(company_id=company.id, external_id="D-2").one_or_none() is None


def test_missing_required_column_fails_whole_import(session, company):
    bad_content = "external_deal_id,title\nD-1,Тест\n"
    result = import_deals_csv(session, company.id, bad_content, "deals.csv")

    assert result.status == "failed"
    assert result.row_count == 0
    assert "отсутствуют колонки" in result.error_log


def test_import_tasks_links_to_existing_deal(session, company):
    import_deals_csv(session, company.id, DEALS_HEADER + _deal_row(), "deals.csv")

    tasks_content = TASKS_HEADER + "T-1,D-1,Перезвонить клиенту,2026-07-10,open,oleg@demo.local\n"
    result = import_tasks_csv(session, company.id, tasks_content, "tasks.csv")

    assert result.status == "success"
    deal = session.query(Deal).filter_by(company_id=company.id, external_id="D-1").one()
    task = session.query(DealTask).filter_by(deal_id=deal.id, external_id="T-1").one()
    assert task.text == "Перезвонить клиенту"
    assert task.status == "open"
    assert task.assignee_user_id is not None


def test_reimport_tasks_upserts_by_external_id(session, company):
    import_deals_csv(session, company.id, DEALS_HEADER + _deal_row(), "deals.csv")

    v1 = TASKS_HEADER + "T-1,D-1,Перезвонить клиенту,2026-07-10,open,oleg@demo.local\n"
    import_tasks_csv(session, company.id, v1, "tasks.csv")

    v2 = TASKS_HEADER + "T-1,D-1,Перезвонить клиенту (уточнено),2026-07-12,done,oleg@demo.local\n"
    import_tasks_csv(session, company.id, v2, "tasks.csv")

    deal = session.query(Deal).filter_by(company_id=company.id, external_id="D-1").one()
    tasks = session.query(DealTask).filter_by(deal_id=deal.id).all()
    assert len(tasks) == 1  # upsert, не дубль
    assert tasks[0].status == "done"
    assert tasks[0].completed_at is not None


def test_task_with_unknown_deal_reports_error(session, company):
    content = TASKS_HEADER + "T-1,D-999,Что-то,2026-07-10,open,oleg@demo.local\n"
    result = import_tasks_csv(session, company.id, content, "tasks.csv")

    assert result.status == "failed"
    assert "D-999" in result.error_log
