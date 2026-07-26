"""LLM-обёртка: сборка промптов и graceful fallback. Реальных вызовов нет."""
from __future__ import annotations

import config
from services import llm
from services.prompts import build_draft_prompt, build_explain_prompt

FACTS = {
    "client": "ТОВ «БудПроект»",
    "contact_name": "Олексій",
    "stage": "Предложение отправлено",
    "amount": "450 000 UAH",
    "idle": "6 днів",
    "problem": "КП отправлено 150 ч назад, нет задачи на follow-up",
    "action": "Поставити задачу на наступний крок. Створити задачу з датою.",
    "empty_field": "",
}


def test_prompts_contain_only_filled_facts():
    prompt = build_explain_prompt(FACTS)
    assert "ТОВ «БудПроект»" in prompt
    assert "450 000 UAH" in prompt
    assert "КП отправлено" in prompt
    assert "empty_field" not in prompt


def test_draft_prompt_asks_for_message():
    prompt = build_draft_prompt(FACTS)
    assert "чернетку повідомлення" in prompt
    assert "Олексій" in prompt


def test_returns_none_without_api_key(monkeypatch):
    monkeypatch.setattr(config, "AI_API_KEY", "")
    assert llm.is_configured() is False
    assert llm.explain_recommendation(FACTS) is None
    assert llm.draft_message(FACTS) is None


def test_returns_none_when_provider_fails(monkeypatch):
    monkeypatch.setattr(config, "AI_API_KEY", "test-key")

    def boom(*args, **kwargs):
        raise RuntimeError("kie.ai недоступен")

    monkeypatch.setattr(llm, "_request", boom)
    assert llm.explain_recommendation(FACTS) is None
    assert llm.draft_message(FACTS) is None


def test_returns_text_from_mocked_client(monkeypatch):
    monkeypatch.setattr(config, "AI_API_KEY", "test-key")
    captured: dict[str, str] = {}

    def fake_request(instructions: str, prompt: str) -> str:
        captured["instructions"] = instructions
        captured["prompt"] = prompt
        return "Готовий текст"

    monkeypatch.setattr(llm, "_request", fake_request)
    assert llm.explain_recommendation(FACTS) == "Готовий текст"
    assert "Поясни менеджеру" in captured["prompt"]
    assert "українською" in captured["instructions"]
