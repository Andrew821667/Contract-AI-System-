# -*- coding: utf-8 -*-
from types import SimpleNamespace

import pytest

from config.settings import settings
from src.services.llm_gateway import LLMGateway
from src.services.risk_analyzer import RiskAnalyzer


def _make_clauses(count: int):
    return [
        {
            "id": f"clause-{idx}",
            "number": idx + 1,
            "xpath": f"/contract/clause[{idx + 1}]",
            "title": f"{idx + 1}. Пункт договора",
            "text": "Текст пункта договора для анализа.",
            "type": "general",
        }
        for idx in range(count)
    ]


class _LocalSuccessLLM:
    provider = "ollama"

    def __init__(self):
        self.batch_sizes = []

    def is_local_provider(self):
        return True

    def call(self, *args, **kwargs):
        prompt = kwargs.get("prompt", "")
        batch_size = prompt.count("ПУНКТ ")
        self.batch_sizes.append(batch_size)
        return {
            "analyses": [
                {"risks": [], "required_fields": []}
                for _ in range(batch_size)
            ]
        }


class _LocalFailLLM:
    provider = "ollama"

    def is_local_provider(self):
        return True

    def call(self, *args, **kwargs):
        raise TimeoutError("Local model timed out")


def test_local_llm_uses_small_sequential_batches_and_reports_progress():
    llm = _LocalSuccessLLM()
    analyzer = RiskAnalyzer(llm)
    progress_events = []

    analyses = analyzer.analyze_clauses_batch(
        _make_clauses(7),
        batch_size=10,
        parallel=True,
        progress_callback=lambda completed, total: progress_events.append((completed, total)),
    )

    assert len(analyses) == 7
    assert llm.batch_sizes == [settings.llm_local_batch_size, settings.llm_local_batch_size, 1]
    assert progress_events == [(1, 3), (2, 3), (3, 3)]
    assert all(item.get("analysis_status") == "ok" for item in analyses)


def test_local_llm_raises_when_all_batches_fall_back():
    analyzer = RiskAnalyzer(_LocalFailLLM())

    with pytest.raises(RuntimeError, match="Локальная LLM не вернула ни одного валидного результата"):
        analyzer.analyze_clauses_batch(
            _make_clauses(4),
            batch_size=10,
            parallel=True,
        )


def test_ollama_openai_compatible_calls_use_local_timeout():
    completions = SimpleNamespace()

    def _create(**kwargs):
        completions.kwargs = kwargs
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="ok"))]
        )

    gateway = LLMGateway.__new__(LLMGateway)
    gateway.provider = "ollama"
    gateway.model = "qwen3:7b"
    gateway._client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=_create)))
    gateway.total_input_tokens = 0
    gateway.total_output_tokens = 0

    result = gateway._call_openai_compatible(
        prompt="Тест",
        system_prompt=None,
        temperature=0.0,
        max_tokens=100,
    )

    assert result == "ok"
    assert completions.kwargs["timeout"] == settings.llm_local_timeout
