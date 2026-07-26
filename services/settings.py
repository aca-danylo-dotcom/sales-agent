"""Настройки компании: пороги правил, веса приоритизации, этапы, режим работы.

Здесь только чтение/валидация/запись — сам пересчёт запускает роутер после
успешного сохранения (детекция и приоритизация остаются единственным местом,
где принимаются решения по сделкам).

Формы приходят с динамическими именами полей, поэтому вместо pydantic-схем —
явные спецификации параметров: они же описывают, что рисовать на экране.
"""
from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from zoneinfo import ZoneInfo, available_timezones

from sqlalchemy.orm import Session

from db.models import Company, DetectionRule, PipelineStage
from db.seed import DEFAULT_RULES
from services.detection import RULES


@dataclass(frozen=True)
class ParamSpec:
    """Один редактируемый параметр правила детекции."""

    key: str
    label: str
    unit: str
    kind: str = "number"  # number | stage
    minimum: float = 0
    maximum: float = 10000
    default: float | str = 0


# Порядок правил на экране — как в сиде, чтобы список не «прыгал» между заходами.
RULE_ORDER = [code for code, _name, _params in DEFAULT_RULES]

RULE_SPECS: dict[str, tuple[ParamSpec, ...]] = {
    "NEW_LEAD_NO_RESPONSE": (
        ParamSpec("hours_threshold", "Без реакції довше", "год", minimum=1, maximum=720, default=24),
    ),
    "DEAL_STALE": (
        ParamSpec("days_threshold", "Без активності довше", "дн", minimum=1, maximum=365, default=5),
    ),
    "PROPOSAL_NO_NEXT_TASK": (
        ParamSpec("hours_threshold", "Після КП минуло", "год", minimum=1, maximum=720, default=48),
        ParamSpec(
            "stage_name",
            "Етап «КП відправлено»",
            "",
            kind="stage",
            default="Предложение отправлено",
        ),
    ),
    "NEXT_CONTACT_OVERDUE": (
        ParamSpec("hours_grace", "Пільговий час після дати контакту", "год", minimum=0, maximum=168, default=4),
    ),
    "STUCK_ON_STAGE": (
        ParamSpec("days_threshold", "На одному етапі довше", "дн", minimum=1, maximum=365, default=10),
    ),
    "NO_NEXT_ACTION": (
        ParamSpec("hours_threshold", "Без відкритої задачі довше", "год", minimum=1, maximum=720, default=24),
    ),
}

WEIGHT_SPECS: tuple[tuple[str, str, str], ...] = (
    ("weight_amount", "Сума угоди", "внесок найбільшої угоди в бали"),
    ("weight_idle", "День простою", "балів за кожен день без активності"),
    ("weight_stage", "Етап воронки", "балів за кожен крок углиб воронки"),
    ("weight_overdue_task", "Прострочена задача", "разовий бонус"),
    ("weight_multi_rule", "Кілька правил разом", "балів за кожне додаткове правило"),
)

MAX_WEIGHT = 1000.0
MIN_COOLDOWN_DAYS, MAX_COOLDOWN_DAYS = 0, 365


# --- чтение -------------------------------------------------------------------


def rules_for_company(session: Session, company_id: int) -> list[DetectionRule]:
    """Правила компании в порядке сида; неизвестные коды идут в конец."""
    rows = session.query(DetectionRule).filter_by(company_id=company_id).all()
    order = {code: index for index, code in enumerate(RULE_ORDER)}
    return sorted(rows, key=lambda row: (order.get(row.code, len(order)), row.code))


def stages_for_company(session: Session, company_id: int) -> list[PipelineStage]:
    return (
        session.query(PipelineStage)
        .filter_by(company_id=company_id)
        .order_by(PipelineStage.order_index, PipelineStage.id)
        .all()
    )


def rule_params(rule: DetectionRule) -> dict:
    return json.loads(rule.params_json) if rule.params_json else {}


def rules_view(session: Session, company_id: int) -> list[dict]:
    """Данные правил для шаблона: строка БД + описания параметров с текущими значениями."""
    view: list[dict] = []
    for rule in rules_for_company(session, company_id):
        params = rule_params(rule)
        specs = RULE_SPECS.get(rule.code, ())
        view.append(
            {
                "row": rule,
                "known": rule.code in RULES,
                "stage_ids": json.loads(rule.applies_to_stage_ids) if rule.applies_to_stage_ids else [],
                "params": [
                    {"spec": spec, "value": params.get(spec.key, spec.default)} for spec in specs
                ],
            }
        )
    return view


# --- валидация ----------------------------------------------------------------


def _number(raw: str | None, label: str, minimum: float, maximum: float, errors: list[str]) -> float | None:
    text = (raw or "").strip().replace(",", ".")
    if not text:
        errors.append(f"«{label}»: значення не заповнене")
        return None
    try:
        value = float(text)
    except ValueError:
        errors.append(f"«{label}»: потрібне число, а не «{text}»")
        return None
    if value < minimum or value > maximum:
        errors.append(f"«{label}»: допустимий діапазон {minimum:g}–{maximum:g}, отримано {value:g}")
        return None
    return value


def _as_int(value: float) -> int | float:
    """Целые пороги храним целыми — так они и выглядят в reason_text рекомендации."""
    return int(value) if float(value).is_integer() else value


# --- запись -------------------------------------------------------------------


def save_rules(session: Session, company_id: int, form: Mapping[str, str]) -> list[str]:
    """Сохраняет вкл/выкл, пороги и ограничение по этапам. При любой ошибке не пишет ничего."""
    errors: list[str] = []
    rules = rules_for_company(session, company_id)
    stage_ids = {stage.id for stage in stages_for_company(session, company_id)}
    stage_names = {stage.name for stage in stages_for_company(session, company_id)}

    planned: list[tuple[DetectionRule, bool, dict, str | None]] = []
    for rule in rules:
        enabled = f"enabled__{rule.code}" in form
        params = rule_params(rule)

        for spec in RULE_SPECS.get(rule.code, ()):
            raw = form.get(f"param__{rule.code}__{spec.key}")
            label = f"{rule.name} — {spec.label}"
            if spec.kind == "stage":
                name = (raw or "").strip()
                if not name:
                    errors.append(f"«{label}»: етап не обрано")
                    continue
                if stage_names and name not in stage_names:
                    errors.append(f"«{label}»: етапу «{name}» немає у воронці")
                    continue
                params[spec.key] = name
                continue

            value = _number(raw, label, spec.minimum, spec.maximum, errors)
            if value is not None:
                params[spec.key] = _as_int(value)

        selected = [int(value) for value in form.getlist(f"stages__{rule.code}")] if hasattr(form, "getlist") else []
        unknown = [value for value in selected if value not in stage_ids]
        if unknown:
            errors.append(f"«{rule.name}»: обрано неіснуючий етап")
        applies_to = json.dumps(selected, ensure_ascii=False) if selected else None

        planned.append((rule, enabled, params, applies_to))

    if errors:
        return errors

    for rule, enabled, params, applies_to in planned:
        rule.enabled = enabled
        rule.params_json = json.dumps(params, ensure_ascii=False)
        rule.applies_to_stage_ids = applies_to
    session.commit()
    return []


def save_weights(session: Session, company_id: int, form: Mapping[str, str]) -> list[str]:
    company = session.get(Company, company_id)
    if company is None:
        return ["Компанію не знайдено"]

    errors: list[str] = []
    values: dict[str, float] = {}
    for field, label, _hint in WEIGHT_SPECS:
        value = _number(form.get(field), label, 0, MAX_WEIGHT, errors)
        if value is not None:
            values[field] = value

    if errors:
        return errors

    for field, value in values.items():
        setattr(company, field, value)
    session.commit()
    return []


def save_stages(session: Session, company_id: int, form: Mapping[str, str]) -> list[str]:
    """Переименование этапов. Имя этапа — ключ маппинга CSV, поэтому пустые и дубли запрещены."""
    stages = stages_for_company(session, company_id)
    errors: list[str] = []
    renames: dict[int, str] = {}

    for stage in stages:
        name = (form.get(f"stage_name__{stage.id}") or "").strip()
        if not name:
            errors.append(f"Етап #{stage.order_index}: назва не може бути порожньою")
            continue
        renames[stage.id] = name

    if len(set(renames.values())) != len(renames):
        errors.append("Назви етапів мають бути унікальними")
    if errors:
        return errors

    # Правило PROPOSAL_NO_NEXT_TASK ссылается на этап по имени — переименование
    # этапа должно ехать вместе с ним, иначе правило молча перестанет срабатывать.
    old_names = {stage.id: stage.name for stage in stages}
    renamed = {old_names[stage_id]: name for stage_id, name in renames.items() if old_names[stage_id] != name}
    if renamed:
        for rule in rules_for_company(session, company_id):
            params = rule_params(rule)
            current = params.get("stage_name")
            if current in renamed:
                params["stage_name"] = renamed[current]
                rule.params_json = json.dumps(params, ensure_ascii=False)

    for stage in stages:
        stage.name = renames[stage.id]
    session.commit()
    return []


def save_company(session: Session, company_id: int, form: Mapping[str, str]) -> list[str]:
    company = session.get(Company, company_id)
    if company is None:
        return ["Компанію не знайдено"]

    errors: list[str] = []

    name = (form.get("name") or "").strip()
    if not name:
        errors.append("Назва компанії не може бути порожньою")

    timezone = (form.get("timezone") or "").strip()
    try:
        ZoneInfo(timezone)
    except Exception:
        errors.append(f"Невідомий часовий пояс «{timezone}»")

    digest_hour = _number(form.get("digest_hour"), "Час формування списку дня", 0, 23, errors)
    cooldown = _number(
        form.get("resolved_cooldown_days"),
        "Пауза після рішення",
        MIN_COOLDOWN_DAYS,
        MAX_COOLDOWN_DAYS,
        errors,
    )

    if errors:
        return errors

    company.name = name
    company.timezone = timezone
    company.digest_hour = int(digest_hour)
    company.resolved_cooldown_days = int(cooldown)
    session.commit()
    return []


def timezone_options() -> list[str]:
    """Короткий список поясов для выпадающего списка (полный — тысячи значений)."""
    common = [
        "Europe/Kiev",
        "Europe/Kyiv",
        "Europe/Warsaw",
        "Europe/Berlin",
        "Europe/London",
        "Europe/Lisbon",
        "Asia/Tbilisi",
        "Asia/Dubai",
        "America/New_York",
        "UTC",
    ]
    known = available_timezones()
    return [name for name in common if name in known]
