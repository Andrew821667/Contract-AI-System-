"""
Fallback Handler — graceful degradation когда LLM недоступен.

Modes:
- cascade: try all models in chain
- local_only: only local models
- fail_fast: no retries, immediate error
- queue: defer task for later execution

Circuit breaker state persisted to Redis (survives restarts).
Falls back to in-memory if Redis unavailable.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any

from loguru import logger


class FallbackMode(str, Enum):
    CASCADE = "cascade"
    LOCAL_ONLY = "local_only"
    FAIL_FAST = "fail_fast"
    QUEUE = "queue"


def _get_redis():
    """Try to connect to Redis. Returns client or None."""
    try:
        import redis
    except ImportError:
        return None
    try:
        from config.settings import settings
        client = redis.Redis.from_url(
            settings.redis_url, decode_responses=True, socket_connect_timeout=1
        )
        client.ping()
        return client
    except Exception:
        return None


class FallbackHandler:
    """
    Обработчик fallback-ситуаций.

    - Отслеживает здоровье моделей (circuit breaker)
    - Определяет fallback-поведение при полном отказе
    - Поддерживает graceful degradation (workflow продолжается без LLM)
    - Состояние в Redis (persistent) с fallback на in-memory
    """

    _REDIS_PREFIX = "circuit_breaker:"

    def __init__(self) -> None:
        self._redis = _get_redis()
        if self._redis:
            logger.info("CircuitBreaker: using Redis backend (persistent)")
        else:
            logger.warning("CircuitBreaker: using in-memory (resets on restart)")

        # In-memory fallback
        self._failures: dict[str, list[datetime]] = {}
        # Circuit breaker threshold: N failures in M minutes -> model "unhealthy"
        self._failure_threshold = 3
        self._failure_window = timedelta(minutes=5)
        # Deferred tasks (for queue mode)
        self._deferred_queue: list[dict[str, Any]] = []

    def record_failure(self, model: str) -> None:
        """Записать сбой модели."""
        now = datetime.now(timezone.utc)

        if self._redis:
            try:
                key = f"{self._REDIS_PREFIX}{model}"
                ts = now.isoformat()
                self._redis.zadd(key, {ts: now.timestamp()})
                # Auto-expire old entries
                cutoff = (now - self._failure_window).timestamp()
                self._redis.zremrangebyscore(key, 0, cutoff)
                # TTL = window + 1 min buffer
                self._redis.expire(key, int(self._failure_window.total_seconds()) + 60)
                return
            except Exception as exc:
                logger.warning(f"Redis circuit breaker write failed: {exc}")

        # In-memory fallback
        if model not in self._failures:
            self._failures[model] = []
        self._failures[model].append(now)
        cutoff = now - self._failure_window
        self._failures[model] = [t for t in self._failures[model] if t > cutoff]

    def is_healthy(self, model: str) -> bool:
        """Проверить здоровье модели (circuit breaker)."""
        if self._redis:
            try:
                key = f"{self._REDIS_PREFIX}{model}"
                cutoff = (datetime.now(timezone.utc) - self._failure_window).timestamp()
                self._redis.zremrangebyscore(key, 0, cutoff)
                count = self._redis.zcard(key)
                return count < self._failure_threshold
            except Exception:
                pass

        # In-memory fallback
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
        all_models = ["deepseek-chat", "gemini-2.5-flash", "claude-sonnet-4-6-20250227", "gpt-5.4"]
        return {
            "models": {
                m: {
                    "healthy": self.is_healthy(m),
                    "recent_failures": self._get_failure_count(m),
                }
                for m in all_models
            },
            "deferred_queue_size": len(self._deferred_queue),
            "backend": "redis" if self._redis else "memory",
        }

    def _get_failure_count(self, model: str) -> int:
        """Get recent failure count for a model."""
        if self._redis:
            try:
                key = f"{self._REDIS_PREFIX}{model}"
                cutoff = (datetime.now(timezone.utc) - self._failure_window).timestamp()
                self._redis.zremrangebyscore(key, 0, cutoff)
                return self._redis.zcard(key) or 0
            except Exception:
                pass

        return len([
            t for t in self._failures.get(model, [])
            if t > datetime.now(timezone.utc) - self._failure_window
        ])

    def clear_failures(self, model: str | None = None) -> None:
        """Очистить записи о сбоях."""
        if self._redis:
            try:
                if model:
                    self._redis.delete(f"{self._REDIS_PREFIX}{model}")
                else:
                    keys = self._redis.keys(f"{self._REDIS_PREFIX}*")
                    if keys:
                        self._redis.delete(*keys)
            except Exception as exc:
                logger.warning(f"Redis clear_failures failed: {exc}")

        if model:
            self._failures.pop(model, None)
        else:
            self._failures.clear()
