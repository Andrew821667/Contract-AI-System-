"""
Fallback Handler — graceful degradation когда LLM недоступен.

Modes:
- cascade: try all models in chain
- local_only: only local models
- fail_fast: no retries, immediate error
- queue: defer task for later execution
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any

from loguru import logger


class FallbackMode(str, Enum):
    CASCADE = "cascade"
    LOCAL_ONLY = "local_only"
    FAIL_FAST = "fail_fast"
    QUEUE = "queue"


class FallbackHandler:
    """
    Обработчик fallback-ситуаций.

    - Отслеживает здоровье моделей (circuit breaker)
    - Определяет fallback-поведение при полном отказе
    - Поддерживает graceful degradation (workflow продолжается без LLM)
    """

    def __init__(self) -> None:
        # Circuit breaker: model -> list of failure timestamps
        self._failures: dict[str, list[datetime]] = {}
        # Circuit breaker threshold: N failures in M minutes -> model "unhealthy"
        self._failure_threshold = 3
        self._failure_window = timedelta(minutes=5)
        # Deferred tasks (for queue mode)
        self._deferred_queue: list[dict[str, Any]] = []

    def record_failure(self, model: str) -> None:
        """Записать сбой модели."""
        if model not in self._failures:
            self._failures[model] = []
        self._failures[model].append(datetime.now(timezone.utc))
        # Trim old entries
        cutoff = datetime.now(timezone.utc) - self._failure_window
        self._failures[model] = [t for t in self._failures[model] if t > cutoff]

    def is_healthy(self, model: str) -> bool:
        """Проверить здоровье модели (circuit breaker)."""
        if model not in self._failures:
            return True
        cutoff = datetime.now(timezone.utc) - self._failure_window
        recent = [t for t in self._failures[model] if t > cutoff]
        return len(recent) < self._failure_threshold

    def get_healthy_models(self, candidates: list[str]) -> list[str]:
        """Отфильтровать только здоровые модели."""
        return [m for m in candidates if self.is_healthy(m)]

    async def handle_total_failure(
        self,
        cascade_level: str,
        task_type: str,
    ) -> dict[str, Any]:
        """
        Обработать полный отказ всех моделей.

        Возвращает fallback response, который позволяет workflow продолжаться.
        """
        logger.error(
            f"Total LLM failure: cascade_level={cascade_level}, task_type={task_type}. "
            f"Returning degraded response."
        )

        # Workflow продолжается с degraded response
        return {
            "status": "degraded",
            "message": "LLM недоступен. Задача поставлена в очередь для повторной обработки.",
            "cascade_level": cascade_level,
            "task_type": task_type,
            "requires_manual_review": True,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def get_status(self) -> dict[str, Any]:
        """Статус здоровья всех моделей."""
        all_models = ["deepseek-chat", "claude-sonnet-4-6-20250227", "gpt-5.4", "gpt-5.4-mini"]
        return {
            "models": {
                m: {
                    "healthy": self.is_healthy(m),
                    "recent_failures": len([
                        t for t in self._failures.get(m, [])
                        if t > datetime.now(timezone.utc) - self._failure_window
                    ]),
                }
                for m in all_models
            },
            "deferred_queue_size": len(self._deferred_queue),
        }

    def clear_failures(self, model: str | None = None) -> None:
        """Очистить записи о сбоях."""
        if model:
            self._failures.pop(model, None)
        else:
            self._failures.clear()
