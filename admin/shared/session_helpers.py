# -*- coding: utf-8 -*-
"""
Общие функции для работы с session_state и конфигурацией
"""
import os
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

import streamlit as st

# Путь к корню проекта
PROJECT_ROOT = Path(__file__).parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def init_session_state():
    """Инициализирует общие ключи session_state."""
    defaults = {
        "processing_history": [],
        "generated_contracts": [],
        "disagreement_protocols": [],
        "current_analysis_result": None,
        "current_document_text": None,
        "accepted_recommendations": [],
        "accepted_recommendation_keys": [],
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def get_processing_history() -> List[Dict[str, Any]]:
    """Возвращает историю обработок из session_state."""
    init_session_state()
    return st.session_state.get("processing_history", [])


def add_to_history(entry: Dict[str, Any]):
    """Добавляет запись в историю обработок."""
    init_session_state()
    entry.setdefault("timestamp", datetime.now().isoformat())
    st.session_state["processing_history"].insert(0, entry)
    # Лимит 100 записей
    if len(st.session_state["processing_history"]) > 100:
        st.session_state["processing_history"] = st.session_state["processing_history"][:100]


def get_api_keys_status() -> Dict[str, bool]:
    """Проверяет наличие API-ключей в окружении."""
    keys = {
        "OpenAI": "OPENAI_API_KEY",
        "Anthropic": "ANTHROPIC_API_KEY",
        "DeepSeek": "DEEPSEEK_API_KEY",
        "Perplexity": "PERPLEXITY_API_KEY",
        "YandexGPT": "YANDEX_API_KEY",
        "Qwen": "QWEN_API_KEY",
    }
    result = {}
    for label, env_var in keys.items():
        val = os.environ.get(env_var, "")
        result[label] = bool(val and len(val) > 5)
    return result


def get_llm_gateway(provider: Optional[str] = None):
    """Создаёт или возвращает экземпляр LLMGateway."""
    try:
        from src.services.llm_gateway import LLMGateway
        return LLMGateway(provider=provider)
    except Exception as e:
        st.error(f"Ошибка инициализации LLM Gateway: {e}")
        return None


def get_db_session():
    """Создаёт сессию БД."""
    try:
        from src.models.database import SessionLocal
        return SessionLocal()
    except Exception as e:
        st.error(f"Ошибка подключения к БД: {e}")
        return None


def load_env():
    """Загружает .env из корня проекта."""
    env_path = PROJECT_ROOT / ".env"
    if env_path.exists():
        try:
            from dotenv import load_dotenv
            load_dotenv(env_path)
        except ImportError:
            pass
