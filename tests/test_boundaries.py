"""LLM не должен участвовать в детекции/приоритизации — только в объяснении и черновиках."""
from __future__ import annotations

from pathlib import Path

SERVICES_DIR = Path(__file__).resolve().parents[1] / "services"

RULE_ENGINE_MODULES = ["detection.py", "prioritization.py"]


def test_rule_engine_modules_do_not_import_llm():
    for filename in RULE_ENGINE_MODULES:
        source = (SERVICES_DIR / filename).read_text(encoding="utf-8")
        import_lines = [
            line.strip()
            for line in source.splitlines()
            if line.strip().startswith("import ") or line.strip().startswith("from ")
        ]
        assert not any("services.llm" in line or "services import llm" in line for line in import_lines), (
            f"{filename} не должен импортировать services.llm"
        )
