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


def check_admin_auth() -> bool:
    """
    Проверка авторизации для админ-панели.
    Возвращает True если пользователь авторизован, иначе показывает форму входа.
    """
    if st.session_state.get("admin_authenticated"):
        return True

    st.markdown("## 🔐 Вход в админ-панель")
    st.markdown("---")

    with st.form("admin_login_form"):
        email = st.text_input("Email", placeholder="admin@contractai.ru")
        password = st.text_input("Пароль", type="password", placeholder="Введите пароль")
        submitted = st.form_submit_button("Войти", use_container_width=True)

    if submitted:
        if not email or not password:
            st.error("Введите email и пароль")
            return False

        try:
            from src.models.database import SessionLocal
            from src.models.auth_models import User
            from src.services.auth_service import AuthService

            db = SessionLocal()
            try:
                auth = AuthService(db)
                user = db.query(User).filter(User.email == email).first()

                if not user or not user.password_hash:
                    st.error("Неверный email или пароль")
                    return False

                if not auth.verify_password(password, user.password_hash):
                    st.error("Неверный email или пароль")
                    return False

                if user.role not in ("admin", "senior_lawyer"):
                    st.error("Доступ только для администраторов и старших юристов")
                    return False

                st.session_state["admin_authenticated"] = True
                st.session_state["admin_user_email"] = user.email
                st.session_state["admin_user_name"] = user.name
                st.session_state["admin_user_role"] = user.role
                st.rerun()
            finally:
                db.close()
        except Exception as e:
            st.error(f"Ошибка авторизации: {e}")
            return False

    return False


def show_admin_sidebar_user():
    """Показать информацию о пользователе и кнопку выхода в sidebar."""
    if st.session_state.get("admin_authenticated"):
        name = st.session_state.get("admin_user_name", "")
        role = st.session_state.get("admin_user_role", "")
        role_label = {"admin": "Администратор", "senior_lawyer": "Старший юрист"}.get(role, role)
        st.sidebar.markdown(f"👤 **{name}**")
        st.sidebar.caption(role_label)
        if st.sidebar.button("🚪 Выйти", key="admin_logout"):
            for k in ["admin_authenticated", "admin_user_email", "admin_user_name", "admin_user_role"]:
                st.session_state.pop(k, None)
            st.rerun()


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
