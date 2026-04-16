# -*- coding: utf-8 -*-
"""
Prometheus metrics — HTTP + LLM cascade observability.

Экспозиция: GET /metrics (mount в src/main.py через prometheus-fastapi-instrumentator).
LLM метрики пишутся из CascadeManager.execute_with_fallback.

Если prometheus_client не установлен — метрики заменяются на no-op,
чтобы не ломать код и тесты.
"""
from __future__ import annotations

try:
    from prometheus_client import Counter, Histogram  # type: ignore
    _PROMETHEUS_AVAILABLE = True
except ImportError:  # pragma: no cover — fallback в dev-окружении без пакета
    _PROMETHEUS_AVAILABLE = False

    class _NoopMetric:
        def labels(self, **_kwargs):
            return self

        def observe(self, _value):
            pass

        def inc(self, _amount: float = 1):
            pass

    def Counter(*_args, **_kwargs):  # type: ignore
        return _NoopMetric()

    def Histogram(*_args, **_kwargs):  # type: ignore
        return _NoopMetric()


# ── LLM cascade metrics ──────────────────────────────────────────────────────

llm_call_duration_seconds = Histogram(
    "llm_call_duration_seconds",
    "Длительность одного вызова LLM, секунды.",
    labelnames=("model", "cascade_level", "success"),
    buckets=(0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 20.0, 40.0, 60.0, 120.0),
)

llm_cascade_attempts_total = Counter(
    "llm_cascade_attempts_total",
    "Попытки вызова LLM внутри cascade (включая fallback-ретраи).",
    labelnames=("model", "cascade_level", "success"),
)

llm_cascade_fallbacks_total = Counter(
    "llm_cascade_fallbacks_total",
    "Переключения на fallback-модель (primary упала → перешли на следующую).",
    labelnames=("cascade_level", "from_model", "to_model"),
)

llm_cascade_total_failures_total = Counter(
    "llm_cascade_total_failures_total",
    "Полный отказ cascade — все модели упали, сработал total-failure fallback.",
    labelnames=("cascade_level",),
)
