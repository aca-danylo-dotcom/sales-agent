"""Дефолтные detection_rules и pipeline_stages для новой компании."""
from __future__ import annotations

import json

from sqlalchemy.orm import Session

from db.models import Company, DetectionRule, PipelineStage

DEFAULT_STAGES = [
    ("Новый лид", 0, False, False),
    ("В работе", 1, False, False),
    ("Предложение отправлено", 2, False, False),
    ("Переговоры", 3, False, False),
    ("Выиграна", 4, True, False),
    ("Проиграна", 5, False, True),
]

# Пороги — в часах, если не указано иное. Правятся на экране "Настройки" без деплоя.
DEFAULT_RULES = [
    ("NEW_LEAD_NO_RESPONSE", "Новый лид без ответа", {"hours_threshold": 24}),
    ("DEAL_STALE", "Сделка зависла без активности", {"days_threshold": 5}),
    (
        "PROPOSAL_NO_NEXT_TASK",
        "Предложение отправлено, нет следующей задачи",
        # stage_name — тоже параметр: этап можно переименовать в настройках, правило не должно ломаться.
        {"hours_threshold": 48, "stage_name": "Предложение отправлено"},
    ),
    ("NEXT_CONTACT_OVERDUE", "Просрочена дата следующего контакта", {"hours_grace": 4}),
    ("STUCK_ON_STAGE", "Сделка застряла на этапе дольше нормы", {"days_threshold": 10}),
    ("NO_NEXT_ACTION", "Нет открытой задачи по сделке", {"hours_threshold": 24}),
]


def seed_company(session: Session, company: Company) -> None:
    """Создаёт дефолтные этапы и правила детекции для новой компании."""
    for name, order_index, is_won, is_lost in DEFAULT_STAGES:
        session.add(
            PipelineStage(
                company_id=company.id,
                name=name,
                order_index=order_index,
                is_closed_won=is_won,
                is_closed_lost=is_lost,
            )
        )

    for code, name, params in DEFAULT_RULES:
        session.add(
            DetectionRule(
                company_id=company.id,
                code=code,
                name=name,
                enabled=True,
                params_json=json.dumps(params, ensure_ascii=False),
            )
        )

    session.commit()
