"""Маппинг rule_code -> рекомендуемое действие.

Полная логика подтверждения/отклонения/переноса рекомендаций (confirm/reject/snooze,
создание задачи, классификация причины отказа через LLM) — Фаза 6 плана. Здесь
только чистая, не завязанная на БД функция, нужная detection.py при создании
Recommendation (поле recommended_action обязательно).
"""
from __future__ import annotations

_ACTION_BY_RULE = {
    "NEW_LEAD_NO_RESPONSE": "contact_lead",
    "DEAL_STALE": "follow_up",
    "PROPOSAL_NO_NEXT_TASK": "create_followup_task",
    "NEXT_CONTACT_OVERDUE": "contact_client",
    "STUCK_ON_STAGE": "review_deal",
    "NO_NEXT_ACTION": "create_followup_task",
}

_DEFAULT_ACTION = "review_deal"


def action_for_rule(rule_code: str) -> str:
    return _ACTION_BY_RULE.get(rule_code, _DEFAULT_ACTION)
