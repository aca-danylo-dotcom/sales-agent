"""CSV-импорт сделок и задач: валидация, upsert по external_id, diff стадий в историю."""
from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, InvalidOperation

from sqlalchemy.orm import Session

import config
from db.models import Contact, CsvImport, Deal, DealStageHistory, DealTask, PipelineStage, User

DEALS_REQUIRED_COLUMNS = [
    "external_deal_id",
    "title",
    "contact_name",
    "contact_phone",
    "contact_email",
    "company_name",
    "owner_email",
    "stage_name",
    "amount",
    "currency",
    "created_at",
    "last_activity_at",
    "next_contact_date",
    "last_note",
]

TASKS_REQUIRED_COLUMNS = [
    "external_task_id",
    "external_deal_id",
    "text",
    "due_at",
    "status",
    "assignee_email",
]

_DATE_FORMATS = ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d")


@dataclass
class _ImportStats:
    row_count: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def status(self) -> str:
        if not self.errors:
            return "success"
        if self.row_count > len(self.errors):
            return "partial"
        return "failed"


def _parse_datetime(value: str | None) -> datetime | None:
    value = (value or "").strip()
    if not value:
        return None
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    raise ValueError(f"неверный формат даты: {value!r}")


def _parse_amount(value: str | None) -> Decimal | None:
    value = (value or "").strip()
    if not value:
        return None
    try:
        return Decimal(value)
    except InvalidOperation as exc:
        raise ValueError(f"неверная сумма: {value!r}") from exc


def _validate_columns(fieldnames: list[str] | None, required: list[str]) -> str | None:
    if not fieldnames:
        return "пустой файл или отсутствует строка заголовка"
    missing = [c for c in required if c not in fieldnames]
    if missing:
        return f"отсутствуют колонки: {', '.join(missing)}"
    return None


def _log_import(
    session: Session,
    company_id: int,
    uploaded_by: int | None,
    filename: str,
    stats: _ImportStats,
) -> CsvImport:
    csv_import = CsvImport(
        company_id=company_id,
        uploaded_by=uploaded_by,
        filename=filename,
        row_count=stats.row_count,
        status=stats.status,
        error_log="; ".join(stats.errors) if stats.errors else None,
    )
    session.add(csv_import)
    session.commit()
    return csv_import


def import_deals_csv(
    session: Session,
    company_id: int,
    file_content: str,
    filename: str,
    uploaded_by: int | None = None,
) -> CsvImport:
    """Парсит deals.csv, делает upsert Contact/Deal по external_id, пишет diff стадий."""
    reader = csv.DictReader(io.StringIO(file_content))
    stats = _ImportStats()

    column_error = _validate_columns(reader.fieldnames, DEALS_REQUIRED_COLUMNS)
    if column_error:
        stats.errors.append(column_error)
        return _log_import(session, company_id, uploaded_by, filename, stats)

    stages_by_name = {
        s.name: s for s in session.query(PipelineStage).filter_by(company_id=company_id).all()
    }
    users_by_email = {
        u.email: u for u in session.query(User).filter_by(company_id=company_id).all()
    }

    for line_no, row in enumerate(reader, start=2):
        stats.row_count += 1
        try:
            _import_deal_row(session, company_id, row, stages_by_name, users_by_email)
        except ValueError as exc:
            stats.errors.append(f"строка {line_no}: {exc}")

    session.commit()
    return _log_import(session, company_id, uploaded_by, filename, stats)


def _import_deal_row(
    session: Session,
    company_id: int,
    row: dict[str, str],
    stages_by_name: dict[str, PipelineStage],
    users_by_email: dict[str, User],
) -> None:
    external_id = (row.get("external_deal_id") or "").strip()
    if not external_id:
        raise ValueError("пустой external_deal_id")

    title = (row.get("title") or "").strip()
    if not title:
        raise ValueError("пустой title")

    stage_name = (row.get("stage_name") or "").strip()
    stage = stages_by_name.get(stage_name)
    if stage is None:
        known = ", ".join(sorted(stages_by_name)) or "нет этапов"
        raise ValueError(f"неизвестный этап {stage_name!r}, доступны: {known}")

    owner_email = (row.get("owner_email") or "").strip()
    owner = users_by_email.get(owner_email) if owner_email else None

    contact = _upsert_contact(session, company_id, row)

    amount = _parse_amount(row.get("amount"))
    created_at = _parse_datetime(row.get("created_at"))
    last_activity_at = _parse_datetime(row.get("last_activity_at"))
    next_contact_date = _parse_datetime(row.get("next_contact_date"))
    currency = (row.get("currency") or "").strip()
    last_note = (row.get("last_note") or "").strip() or None

    deal = (
        session.query(Deal)
        .filter_by(company_id=company_id, external_id=external_id)
        .one_or_none()
    )

    if deal is None:
        deal = Deal(
            company_id=company_id,
            external_id=external_id,
            title=title,
            contact_id=contact.id if contact else None,
            stage_id=stage.id,
            owner_user_id=owner.id if owner else None,
            amount=amount,
            currency=currency or "USD",
            created_at=created_at,
            last_activity_at=last_activity_at,
            stage_entered_at=created_at or config.now_local(),
            next_contact_date=next_contact_date,
            last_note=last_note,
        )
        session.add(deal)
        session.flush()
        session.add(DealStageHistory(deal_id=deal.id, from_stage_id=None, to_stage_id=stage.id))
        return

    if deal.stage_id != stage.id:
        session.add(
            DealStageHistory(deal_id=deal.id, from_stage_id=deal.stage_id, to_stage_id=stage.id)
        )
        deal.stage_id = stage.id
        deal.stage_entered_at = config.now_local()

    deal.title = title
    if contact is not None:
        deal.contact_id = contact.id
    if owner is not None:
        deal.owner_user_id = owner.id
    deal.amount = amount
    if currency:
        deal.currency = currency
    deal.last_activity_at = last_activity_at
    deal.next_contact_date = next_contact_date
    if last_note is not None:
        deal.last_note = last_note


def _upsert_contact(session: Session, company_id: int, row: dict[str, str]) -> Contact | None:
    name = (row.get("contact_name") or "").strip()
    if not name:
        return None

    email = (row.get("contact_email") or "").strip()
    phone = (row.get("contact_phone") or "").strip()
    company_name = (row.get("company_name") or "").strip() or None
    # В CSV нет отдельного id контакта — используем email, иначе имя+телефон как стабильный ключ.
    external_id = email or f"{name}:{phone}"

    contact = (
        session.query(Contact)
        .filter_by(company_id=company_id, external_id=external_id)
        .one_or_none()
    )
    if contact is None:
        contact = Contact(
            company_id=company_id,
            external_id=external_id,
            name=name,
            phone=phone or None,
            email=email or None,
            company_name=company_name,
        )
        session.add(contact)
        session.flush()
        return contact

    contact.name = name
    if phone:
        contact.phone = phone
    if email:
        contact.email = email
    if company_name:
        contact.company_name = company_name
    return contact


def import_tasks_csv(
    session: Session,
    company_id: int,
    file_content: str,
    filename: str,
    uploaded_by: int | None = None,
) -> CsvImport:
    """Парсит tasks.csv, делает upsert DealTask по (deal_id, external_task_id)."""
    reader = csv.DictReader(io.StringIO(file_content))
    stats = _ImportStats()

    column_error = _validate_columns(reader.fieldnames, TASKS_REQUIRED_COLUMNS)
    if column_error:
        stats.errors.append(column_error)
        return _log_import(session, company_id, uploaded_by, filename, stats)

    deals_by_external_id = {
        d.external_id: d for d in session.query(Deal).filter_by(company_id=company_id).all()
    }
    users_by_email = {
        u.email: u for u in session.query(User).filter_by(company_id=company_id).all()
    }

    for line_no, row in enumerate(reader, start=2):
        stats.row_count += 1
        try:
            _import_task_row(session, row, deals_by_external_id, users_by_email)
        except ValueError as exc:
            stats.errors.append(f"строка {line_no}: {exc}")

    session.commit()
    return _log_import(session, company_id, uploaded_by, filename, stats)


def _import_task_row(
    session: Session,
    row: dict[str, str],
    deals_by_external_id: dict[str, Deal],
    users_by_email: dict[str, User],
) -> None:
    external_id = (row.get("external_task_id") or "").strip()
    if not external_id:
        raise ValueError("пустой external_task_id")

    external_deal_id = (row.get("external_deal_id") or "").strip()
    deal = deals_by_external_id.get(external_deal_id)
    if deal is None:
        raise ValueError(f"неизвестная сделка: {external_deal_id!r}")

    text = (row.get("text") or "").strip()
    if not text:
        raise ValueError("пустой text")

    status = (row.get("status") or "open").strip() or "open"
    if status not in ("open", "done", "overdue"):
        raise ValueError(f"неверный статус задачи: {status!r}")

    due_at = _parse_datetime(row.get("due_at"))

    assignee_email = (row.get("assignee_email") or "").strip()
    assignee = users_by_email.get(assignee_email) if assignee_email else None

    task = (
        session.query(DealTask)
        .filter_by(deal_id=deal.id, external_id=external_id)
        .one_or_none()
    )
    if task is None:
        session.add(
            DealTask(
                deal_id=deal.id,
                external_id=external_id,
                source="crm_import",
                text=text,
                due_at=due_at,
                status=status,
                assignee_user_id=assignee.id if assignee else None,
                completed_at=config.now_local() if status == "done" else None,
            )
        )
        return

    task.text = text
    task.due_at = due_at
    if assignee is not None:
        task.assignee_user_id = assignee.id
    if task.status != status:
        task.status = status
        task.completed_at = config.now_local() if status == "done" else None
