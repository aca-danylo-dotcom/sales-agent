"""LLM-клиент (провайдер kie.ai, OpenAI Responses API).

Границы: LLM только объясняет уже найденную backend'ом проблему и готовит
черновик сообщения. Ни детекция, ни приоритизация сюда не обращаются — этот
модуль дёргается лениво, только при открытии карточки рекомендации.

Любая ошибка провайдера гасится здесь и наружу отдаётся None: карточка должна
открываться и без LLM.
"""
from __future__ import annotations

import logging

import config
from services.prompts import (
    DRAFT_INSTRUCTIONS,
    EXPLAIN_INSTRUCTIONS,
    build_draft_prompt,
    build_explain_prompt,
)

log = logging.getLogger(__name__)

# Без браузерного UA Cloudflare kie.ai отдаёт 403 (error 1010). См. память kie-ai-integration.
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)

_client = None


def is_configured() -> bool:
    """Есть ли ключ. Без него карточка рендерится, но без объяснения и черновика."""
    return bool(config.AI_API_KEY)


def _get_client():
    global _client
    if _client is None:
        from openai import OpenAI

        _client = OpenAI(
            api_key=config.AI_API_KEY,
            base_url=config.AI_BASE_URL,
            default_headers={"User-Agent": _USER_AGENT},
        )
    return _client


def _request(instructions: str, prompt: str) -> str | None:
    """Один запрос к модели через стриминг (kie.ai отдаёт только SSE)."""
    with _get_client().responses.stream(
        model=config.AI_MODEL,
        instructions=instructions,
        input=prompt,
        reasoning={"effort": config.AI_REASONING_EFFORT},
    ) as stream:
        for _event in stream:
            pass  # дельты не нужны — забираем финал целиком
        response = stream.get_final_response()
    text = (response.output_text or "").strip()
    return text or None


def _safe_request(instructions: str, prompt: str, what: str) -> str | None:
    if not is_configured():
        log.info("LLM пропущен (%s): AI_API_KEY не задан", what)
        return None
    try:
        return _request(instructions, prompt)
    except Exception:  # noqa: BLE001 — сбой LLM не должен ронять карточку
        log.exception("Сбой LLM (%s)", what)
        return None


def explain_recommendation(facts: dict) -> str | None:
    """Объясняет менеджеру, почему найденная правилами проблема важна сейчас."""
    return _safe_request(EXPLAIN_INSTRUCTIONS, build_explain_prompt(facts), "explain")


def draft_message(facts: dict) -> str | None:
    """Черновик сообщения клиенту по фактам, собранным backend'ом."""
    return _safe_request(DRAFT_INSTRUCTIONS, build_draft_prompt(facts), "draft")
