# -*- coding: utf-8 -*-
"""
API v2 — Admin LLM Settings

Управление настройками LLM-моделей по этапам обработки.
Настройки хранятся в Redis (ключ llm_stage_settings).
"""
import json
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from src.api.dependencies import get_current_user
from src.models.auth_models import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/llm", tags=["Admin LLM"])

# ── Available models ──────────────────────────────────────────────

AVAILABLE_MODELS = [
    {
        "id": "deepseek-chat",
        "name": "DeepSeek V3.2",
        "provider": "deepseek",
        "cost_input": 0.28,
        "cost_output": 0.42,
        "description": "Основная модель, быстрая и дешёвая",
    },
    {
        "id": "claude-sonnet-4-6-20250227",
        "name": "Claude Sonnet 4.6",
        "provider": "anthropic",
        "cost_input": 3.00,
        "cost_output": 15.00,
        "description": "Экспертная модель для сложных задач",
    },
    {
        "id": "claude-haiku-4-5-20251001",
        "name": "Claude Haiku 4.5",
        "provider": "anthropic",
        "cost_input": 1.00,
        "cost_output": 5.00,
        "description": "Быстрая модель Anthropic, бюджетная",
    },
    {
        "id": "gpt-5.4",
        "name": "GPT-5.4",
        "provider": "openai",
        "cost_input": 2.50,
        "cost_output": 20.00,
        "description": "Флагман OpenAI, максимальное качество",
    },
    {
        "id": "gpt-5.4-mini",
        "name": "GPT-5.4 Mini",
        "provider": "openai",
        "cost_input": 0.75,
        "cost_output": 4.50,
        "description": "Бюджетная модель OpenAI",
    },
    {
        "id": "gemini-2.5-flash",
        "name": "Gemini 2.5 Flash",
        "provider": "google",
        "cost_input": 0.30,
        "cost_output": 2.50,
        "description": "Быстрая и дешёвая модель Google",
    },
    {
        "id": "gemini-2.5-pro",
        "name": "Gemini 2.5 Pro",
        "provider": "google",
        "cost_input": 1.25,
        "cost_output": 10.00,
        "description": "Мощная модель Google, 1M контекст",
    },
    {
        "id": "qwen3:7b",
        "name": "Qwen 3 7B (Ollama)",
        "provider": "ollama",
        "cost_input": 0.0,
        "cost_output": 0.0,
        "description": "Лучшая локальная модель, бесплатно",
    },
    {
        "id": "llama4:8b",
        "name": "Llama 4 8B (Ollama)",
        "provider": "ollama",
        "cost_input": 0.0,
        "cost_output": 0.0,
        "description": "Meta Llama 4, локальная, бесплатно",
    },
]

# ── LLM Stages (all places where LLM is used) ────────────────────

LLM_STAGES = [
    {
        "id": "document_processing",
        "name": "Обработка документов",
        "description": "Извлечение структурированных данных из текста договора",
        "default_model": "deepseek-chat",
        "default_temperature": 0.1,
        "default_max_tokens": 4096,
    },
    {
        "id": "contract_analysis",
        "name": "Анализ контракта",
        "description": "Анализ разделов контракта, проверка соответствия",
        "default_model": "deepseek-chat",
        "default_temperature": 0.1,
        "default_max_tokens": 4096,
    },
    {
        "id": "risk_assessment",
        "name": "Оценка рисков",
        "description": "Анализ клаузул на финансовые, юридические и операционные риски",
        "default_model": "deepseek-chat",
        "default_temperature": 0.1,
        "default_max_tokens": 4096,
    },
    {
        "id": "recommendation_generation",
        "name": "Генерация рекомендаций",
        "description": "Создание рекомендаций и предложений по исправлению рисков",
        "default_model": "deepseek-chat",
        "default_temperature": 0.2,
        "default_max_tokens": 4096,
    },
    {
        "id": "contract_generation",
        "name": "Генерация контрактов",
        "description": "Создание полного текста договора по параметрам",
        "default_model": "deepseek-chat",
        "default_temperature": 0.3,
        "default_max_tokens": 4096,
    },
    {
        "id": "clause_suggestion",
        "name": "Подсказки клаузул",
        "description": "Контекстные подсказки при редактировании договора",
        "default_model": "deepseek-chat",
        "default_temperature": 0.3,
        "default_max_tokens": 2048,
    },
    {
        "id": "disagreement_analysis",
        "name": "Протокол разногласий",
        "description": "Генерация возражений и протокола разногласий",
        "default_model": "deepseek-chat",
        "default_temperature": 0.2,
        "default_max_tokens": 4096,
    },
    {
        "id": "metadata_analysis",
        "name": "Анализ метаданных",
        "description": "Проверка контрагентов, прогноз споров, сравнение с шаблонами",
        "default_model": "deepseek-chat",
        "default_temperature": 0.1,
        "default_max_tokens": 4096,
    },
]

REDIS_KEY = "llm_stage_settings"


def _get_redis():
    """Get Redis client. Returns None if unavailable."""
    try:
        import redis
        from config.settings import settings
        redis_url = getattr(settings, "redis_url", None) or "redis://localhost:6379/0"
        client = redis.from_url(redis_url, decode_responses=True, socket_connect_timeout=2)
        client.ping()
        return client
    except Exception:
        return None


def _load_settings() -> Dict[str, Any]:
    """Load LLM stage settings from Redis."""
    r = _get_redis()
    if r:
        raw = r.get(REDIS_KEY)
        if raw:
            return json.loads(raw)
    return {}


def _save_settings(data: Dict[str, Any]) -> bool:
    """Save LLM stage settings to Redis."""
    r = _get_redis()
    if r:
        r.set(REDIS_KEY, json.dumps(data, ensure_ascii=False))
        return True
    return False


# ── Schemas ───────────────────────────────────────────────────────

class StageSettingUpdate(BaseModel):
    model: str = Field(..., description="ID модели")
    temperature: float = Field(0.1, ge=0.0, le=2.0)
    max_tokens: int = Field(4096, ge=256, le=16384)
    enabled: bool = Field(True, description="Этап включён")


class StageSettingRead(BaseModel):
    stage_id: str
    stage_name: str
    stage_description: str
    model: str
    temperature: float
    max_tokens: int
    enabled: bool
    is_default: bool = Field(description="Используются настройки по умолчанию")


class LLMSettingsResponse(BaseModel):
    stages: List[StageSettingRead]
    available_models: List[Dict[str, Any]]
    router_mode: str = Field("auto", description="auto | manual")


class RouterModeUpdate(BaseModel):
    mode: str = Field("auto", description="auto — Smart Router решает, manual — используются настройки из админки")


# ── Endpoints ─────────────────────────────────────────────────────

@router.get(
    "/settings",
    response_model=LLMSettingsResponse,
    summary="Получить настройки LLM по этапам",
)
async def get_llm_settings(
    current_user: User = Depends(get_current_user),
):
    """Возвращает текущие настройки LLM для каждого этапа обработки."""
    if current_user.role not in ("admin", "senior_lawyer"):
        raise HTTPException(status_code=403, detail="Только для администраторов")

    saved = _load_settings()
    router_mode = saved.pop("_router_mode", "auto") if "_router_mode" in saved else "auto"

    stages = []
    for stage_def in LLM_STAGES:
        sid = stage_def["id"]
        if sid in saved:
            override = saved[sid]
            stages.append(StageSettingRead(
                stage_id=sid,
                stage_name=stage_def["name"],
                stage_description=stage_def["description"],
                model=override.get("model", stage_def["default_model"]),
                temperature=override.get("temperature", stage_def["default_temperature"]),
                max_tokens=override.get("max_tokens", stage_def["default_max_tokens"]),
                enabled=override.get("enabled", True),
                is_default=False,
            ))
        else:
            stages.append(StageSettingRead(
                stage_id=sid,
                stage_name=stage_def["name"],
                stage_description=stage_def["description"],
                model=stage_def["default_model"],
                temperature=stage_def["default_temperature"],
                max_tokens=stage_def["default_max_tokens"],
                enabled=True,
                is_default=True,
            ))

    return LLMSettingsResponse(
        stages=stages,
        available_models=AVAILABLE_MODELS,
        router_mode=router_mode,
    )


@router.put(
    "/settings/{stage_id}",
    summary="Обновить настройки LLM для этапа",
)
async def update_stage_setting(
    stage_id: str,
    body: StageSettingUpdate,
    current_user: User = Depends(get_current_user),
):
    """Обновляет настройки конкретного этапа."""
    if current_user.role not in ("admin", "senior_lawyer"):
        raise HTTPException(status_code=403, detail="Только для администраторов")

    valid_ids = {s["id"] for s in LLM_STAGES}
    if stage_id not in valid_ids:
        raise HTTPException(status_code=404, detail=f"Этап '{stage_id}' не найден")

    valid_models = {m["id"] for m in AVAILABLE_MODELS}
    if body.model not in valid_models:
        raise HTTPException(status_code=400, detail=f"Модель '{body.model}' не поддерживается")

    saved = _load_settings()
    saved[stage_id] = {
        "model": body.model,
        "temperature": body.temperature,
        "max_tokens": body.max_tokens,
        "enabled": body.enabled,
    }

    if not _save_settings(saved):
        raise HTTPException(status_code=503, detail="Redis недоступен")

    logger.info("LLM settings updated: stage=%s model=%s by=%s", stage_id, body.model, current_user.email)
    return {"ok": True, "stage_id": stage_id}


@router.put(
    "/settings",
    summary="Обновить настройки всех этапов",
)
async def update_all_settings(
    body: Dict[str, StageSettingUpdate],
    current_user: User = Depends(get_current_user),
):
    """Обновляет настройки для нескольких этапов сразу."""
    if current_user.role not in ("admin", "senior_lawyer"):
        raise HTTPException(status_code=403, detail="Только для администраторов")

    valid_ids = {s["id"] for s in LLM_STAGES}
    valid_models = {m["id"] for m in AVAILABLE_MODELS}

    saved = _load_settings()

    for stage_id, setting in body.items():
        if stage_id.startswith("_"):
            continue
        if stage_id not in valid_ids:
            raise HTTPException(status_code=400, detail=f"Этап '{stage_id}' не найден")
        if setting.model not in valid_models:
            raise HTTPException(status_code=400, detail=f"Модель '{setting.model}' не поддерживается")
        saved[stage_id] = {
            "model": setting.model,
            "temperature": setting.temperature,
            "max_tokens": setting.max_tokens,
            "enabled": setting.enabled,
        }

    if not _save_settings(saved):
        raise HTTPException(status_code=503, detail="Redis недоступен")

    logger.info("LLM settings bulk update by=%s stages=%s", current_user.email, list(body.keys()))
    return {"ok": True, "updated": list(body.keys())}


@router.put(
    "/router-mode",
    summary="Переключить режим маршрутизации",
)
async def update_router_mode(
    body: RouterModeUpdate,
    current_user: User = Depends(get_current_user),
):
    """auto = Smart Router решает модель, manual = фиксированные настройки из админки."""
    if current_user.role not in ("admin", "senior_lawyer"):
        raise HTTPException(status_code=403, detail="Только для администраторов")

    if body.mode not in ("auto", "manual"):
        raise HTTPException(status_code=400, detail="Режим должен быть 'auto' или 'manual'")

    saved = _load_settings()
    saved["_router_mode"] = body.mode
    if not _save_settings(saved):
        raise HTTPException(status_code=503, detail="Redis недоступен")

    logger.info("Router mode set to '%s' by=%s", body.mode, current_user.email)
    return {"ok": True, "mode": body.mode}


@router.post(
    "/reset",
    summary="Сброс настроек LLM к значениям по умолчанию",
)
async def reset_settings(
    current_user: User = Depends(get_current_user),
):
    """Удаляет все переопределения, возвращая систему к дефолтам Smart Router."""
    if current_user.role not in ("admin", "senior_lawyer"):
        raise HTTPException(status_code=403, detail="Только для администраторов")

    r = _get_redis()
    if r:
        r.delete(REDIS_KEY)

    logger.info("LLM settings reset to defaults by=%s", current_user.email)
    return {"ok": True, "message": "Настройки сброшены"}
