"""Форматирование чисел и дат по-украински для UI и для фактов, уходящих в LLM."""
from __future__ import annotations

from datetime import datetime

MONTHS_UK = [
    "січня", "лютого", "березня", "квітня", "травня", "червня",
    "липня", "серпня", "вересня", "жовтня", "листопада", "грудня",
]


def plural_uk(number: int, one: str, few: str, many: str) -> str:
    if number % 100 in (11, 12, 13, 14):
        return many
    if number % 10 == 1:
        return one
    if number % 10 in (2, 3, 4):
        return few
    return many


def idle_label(idle_days: float) -> str:
    if idle_days < 1:
        hours = int(idle_days * 24)
        return f"{hours} {plural_uk(hours, 'година', 'години', 'годин')}"
    days = int(idle_days)
    return f"{days} {plural_uk(days, 'день', 'дні', 'днів')}"


def format_date_uk(moment: datetime) -> str:
    return f"{moment.day} {MONTHS_UK[moment.month - 1]} {moment.year}"


def format_datetime_uk(moment: datetime) -> str:
    return f"{format_date_uk(moment)}, {moment:%H:%M}"


def format_amount(amount: float | None, currency: str | None = None) -> str:
    if amount is None:
        return "—"
    return f"{amount:,.0f}".replace(",", " ") + f" {currency or ''}".rstrip()
