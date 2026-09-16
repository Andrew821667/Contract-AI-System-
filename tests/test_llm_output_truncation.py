# -*- coding: utf-8 -*-
"""Обрыв ответа по max_tokens: повтор с удвоенным лимитом, без live LLM."""
import json
from types import SimpleNamespace

from src.services import llm_gateway as gateway_module
from src.services.llm_gateway import LLMGateway, LLMOutputTruncated


def _gateway(monkeypatch) -> LLMGateway:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key-not-real")
    gw = LLMGateway(provider="deepseek", model="deepseek-flash")
    gw.use_rate_limiter = False
    gw.cache_enabled = False
    return gw


def test_truncated_json_is_retried_with_a_larger_limit(monkeypatch):
    gw = _gateway(monkeypatch)
    monkeypatch.setattr(gateway_module, "wait_exponential", lambda **kwargs: lambda *a, **k: 0)
    calls = []

    def fake_api_call(prompt, system_prompt, temperature, max_tokens, **kwargs):
        calls.append(max_tokens)
        if len(calls) == 1:
            gw._last_finish_reason = "length"
            return '{"changes": [{"clause": "5", "text": "обор'
        gw._last_finish_reason = "stop"
        return json.dumps({"changes": [{"clause": "5", "text": "полный"}]})

    monkeypatch.setattr(gw, "_make_api_call", fake_api_call)

    result = gw.call("prompt", response_format="json", max_tokens=4000, retry_attempts=3)

    assert result == {"changes": [{"clause": "5", "text": "полный"}]}
    assert calls == [4000, 8000]


def test_truncation_error_carries_the_limit(monkeypatch):
    gw = _gateway(monkeypatch)

    def fake_api_call(prompt, system_prompt, temperature, max_tokens, **kwargs):
        gw._last_finish_reason = "length"
        return '{"a": "b'

    monkeypatch.setattr(gw, "_make_api_call", fake_api_call)
    try:
        gw._call_once("p", response_format="json", max_tokens=1000)
    except LLMOutputTruncated as exc:
        assert exc.max_tokens == 1000
    else:
        raise AssertionError("ожидали LLMOutputTruncated")


def test_invalid_json_without_truncation_is_not_treated_as_truncated(monkeypatch):
    gw = _gateway(monkeypatch)

    def fake_api_call(prompt, system_prompt, temperature, max_tokens, **kwargs):
        gw._last_finish_reason = "stop"
        return "просто текст без JSON"

    monkeypatch.setattr(gw, "_make_api_call", fake_api_call)
    try:
        gw._call_once("p", response_format="json", max_tokens=1000)
    except LLMOutputTruncated:
        raise AssertionError("не обрыв, а мусор — это другая ошибка")
    except ValueError:
        pass
