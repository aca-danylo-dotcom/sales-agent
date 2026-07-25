"""Чтение настроек из .env. Все секреты и меняющиеся значения — здесь."""
from __future__ import annotations

import os
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


# --- Время ---
# У каждой компании свой часовой пояс (companies.timezone), но для дефолтного
# планировщика и логов используем один глобальный TZ из .env.
TIMEZONE_NAME: str = os.getenv("TIMEZONE", "Europe/Kiev")
TIMEZONE = ZoneInfo(TIMEZONE_NAME)


def now_local() -> datetime:
    """Текущее время в часовом поясе из .env как наивный datetime (стенное время)."""
    return datetime.now(TIMEZONE).replace(tzinfo=None)


def today_local() -> date:
    return now_local().date()


# --- База данных ---
DB_PATH: Path = BASE_DIR / os.getenv("DB_FILE", "sales_agent.db")

# --- LLM (провайдер kie.ai, формат OpenAI Responses API) ---
AI_API_KEY: str = os.getenv("AI_API_KEY", "")
AI_BASE_URL: str = os.getenv("AI_BASE_URL", "https://api.kie.ai/codex/v1")
AI_MODEL: str = os.getenv("AI_MODEL", "gpt-5-5")
AI_REASONING_EFFORT: str = os.getenv("AI_REASONING_EFFORT", "low")

# --- Веб ---
SECRET_KEY: str = os.getenv("SECRET_KEY", "change-me-in-production")
HOST: str = os.getenv("HOST", "127.0.0.1")
PORT: int = int(os.getenv("PORT", "8000"))
