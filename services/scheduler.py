"""Фоновые джобы (APScheduler, синхронный BackgroundScheduler).

Джобы не обращаются к LLM: это только пересчёт данных и раскладка уже готовых
рекомендаций по людям. Запускается из lifespan приложения (app.py), в тестах
не поднимается.
"""
from __future__ import annotations

import logging

from apscheduler.schedulers.background import BackgroundScheduler

import config
from db.base import SessionLocal
from db.models import Company
from services import daily_digest

logger = logging.getLogger(__name__)

# С какого часа локального времени компании список дня считается сформированным.
DIGEST_HOUR = 8

_scheduler: BackgroundScheduler | None = None


def daily_digest_job() -> None:
    """Раз в сутки формирует daily_digest_items из текущих pending-рекомендаций.

    Запускается ежечасно и работает по локальному времени каждой компании:
    собирает список, когда у компании уже наступило утро. Повторные вызовы за
    те же сутки безопасны (build_digest идемпотентна) и добавляют в список дня
    рекомендации, появившиеся после первой сборки.
    """
    session = SessionLocal()
    try:
        for company in session.query(Company).order_by(Company.id).all():
            now = daily_digest.company_now(company)
            if now.hour < DIGEST_HOUR:
                continue
            created = daily_digest.build_digest(session, company.id, now=now)
            daily_digest.sync_statuses(session, company.id, now=now)
            if created:
                logger.info("daily_digest: компания %s, новых пунктов %s", company.id, created)
    except Exception:  # джоб не должен ронять планировщик
        logger.exception("daily_digest_job упал")
        session.rollback()
    finally:
        session.close()


def create_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone=config.TIMEZONE_NAME)
    scheduler.add_job(
        daily_digest_job,
        trigger="cron",
        minute=5,
        id="daily_digest",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    return scheduler


def start_scheduler() -> BackgroundScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = create_scheduler()
        _scheduler.start()
        logger.info("Планировщик запущен")
    return _scheduler


def shutdown_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
