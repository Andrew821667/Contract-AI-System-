# -*- coding: utf-8 -*-
"""
Contract AI System v3.0 — Единая Административная Консоль
Главная страница с навигацией, быстрыми действиями и статусом системы
"""
import streamlit as st
import sys
import os
from pathlib import Path
from datetime import datetime

# Путь к корню проекта
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Загрузка .env
env_path = project_root / ".env"
if env_path.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(env_path)
    except ImportError:
        pass

# Конфигурация страницы
st.set_page_config(
    page_title="Contract AI — Единая Консоль",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Импорт shared-компонентов
from admin.shared.ui_components import apply_custom_css, metric_card, status_indicator, section_header
from admin.shared.session_helpers import (
    init_session_state,
    get_processing_history,
    get_api_keys_status,
)

# Инициализация
apply_custom_css()
init_session_state()

# ─── Боковая панель ─────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🏛️ Contract AI v3.0")
    st.caption("Единая консоль управления")
    st.markdown("---")

    st.markdown("### 📂 Разделы")
    st.markdown("""
    - **Главная** ← вы здесь
    - 📋 Тесты инфраструктуры
    - 📄 Обработка документов
    - ✍️ Генерация договоров
    - 📊 Метрики моделей
    - ⚖️ Протокол разногласий
    - 📚 Библиотека договоров
    """)

    st.markdown("---")

    # Статус API
    st.markdown("### 🔌 API-ключи")
    api_status = get_api_keys_status()
    for provider, is_ok in api_status.items():
        icon = "✅" if is_ok else "⬜"
        st.caption(f"{icon} {provider}")

    st.markdown("---")
    st.caption(f"🕐 {datetime.now().strftime('%d.%m.%Y %H:%M')}")

# ─── Основной контент ───────────────────────────────────────

section_header(
    "🏛️ Единая Консоль Contract AI",
    "Управление анализом, генерацией и мониторингом договоров"
)

# ─── Ряд 1: Ключевые метрики ────────────────────────────────
st.markdown("### 📊 Обзор системы")

col1, col2, col3, col4, col5 = st.columns(5)

# Подсчёт из session_state
history = get_processing_history()
generated = st.session_state.get("generated_contracts", [])
protocols = st.session_state.get("disagreement_protocols", [])

with col1:
    metric_card("Обработано", str(len(history)), "документов за сессию", "📄")
with col2:
    metric_card("Сгенерировано", str(len(generated)), "договоров", "✍️")
with col3:
    metric_card("Протоколов", str(len(protocols)), "разногласий", "⚖️")
with col4:
    active_keys = sum(1 for v in api_status.values() if v)
    metric_card("API", f"{active_keys}/{len(api_status)}", "подключено", "🔌")
with col5:
    metric_card("Типов", "20", "договоров в справочнике", "📋")

st.markdown("---")

# ─── Ряд 2: Быстрые действия ────────────────────────────────
st.markdown("### ⚡ Быстрые действия")

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.markdown("""
    <div style="background: linear-gradient(135deg, #3b82f6, #1d4ed8); padding: 1.5rem; border-radius: 1rem; text-align: center;">
        <div style="font-size: 2rem;">📄</div>
        <div style="color: white; font-weight: 700; font-size: 1.1rem; margin: 0.5rem 0;">Анализ договора</div>
        <div style="color: rgba(255,255,255,0.8); font-size: 0.85rem;">Загрузить и проанализировать документ</div>
    </div>
    """, unsafe_allow_html=True)
    if st.button("Перейти к анализу →", key="goto_analysis", use_container_width=True):
        st.switch_page("pages/1_Process_Documents.py")

with col2:
    st.markdown("""
    <div style="background: linear-gradient(135deg, #8b5cf6, #6d28d9); padding: 1.5rem; border-radius: 1rem; text-align: center;">
        <div style="font-size: 2rem;">✍️</div>
        <div style="color: white; font-weight: 700; font-size: 1.1rem; margin: 0.5rem 0;">Генерация договора</div>
        <div style="color: rgba(255,255,255,0.8); font-size: 0.85rem;">Создать договор по шаблону через LLM</div>
    </div>
    """, unsafe_allow_html=True)
    if st.button("Перейти к генерации →", key="goto_generate", use_container_width=True):
        st.switch_page("pages/2_Generate_Contract.py")

with col3:
    st.markdown("""
    <div style="background: linear-gradient(135deg, #f59e0b, #d97706); padding: 1.5rem; border-radius: 1rem; text-align: center;">
        <div style="font-size: 2rem;">⚖️</div>
        <div style="color: white; font-weight: 700; font-size: 1.1rem; margin: 0.5rem 0;">Протокол разногласий</div>
        <div style="color: rgba(255,255,255,0.8); font-size: 0.85rem;">Сформировать возражения к договору</div>
    </div>
    """, unsafe_allow_html=True)
    if st.button("Перейти к протоколу →", key="goto_disagreement", use_container_width=True):
        st.switch_page("pages/4_Disagreement_Protocol.py")

with col4:
    st.markdown("""
    <div style="background: linear-gradient(135deg, #10b981, #059669); padding: 1.5rem; border-radius: 1rem; text-align: center;">
        <div style="font-size: 2rem;">📚</div>
        <div style="color: white; font-weight: 700; font-size: 1.1rem; margin: 0.5rem 0;">Библиотека</div>
        <div style="color: rgba(255,255,255,0.8); font-size: 0.85rem;">Все обработанные договоры</div>
    </div>
    """, unsafe_allow_html=True)
    if st.button("Открыть библиотеку →", key="goto_library", use_container_width=True):
        st.switch_page("pages/5_Contract_Library.py")

st.markdown("---")

# ─── Ряд 3: Статус системы ──────────────────────────────────
st.markdown("### 🔧 Статус системы")

col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("**Провайдер по умолчанию**")
    default_provider = os.environ.get("DEFAULT_LLM_PROVIDER", "openai")
    st.info(f"🤖 {default_provider.upper()}")

    st.markdown("**Доступные модели**")
    models_info = []
    if api_status.get("OpenAI"):
        models_info.append("GPT-4o, GPT-4o-mini")
    if api_status.get("DeepSeek"):
        models_info.append("DeepSeek-V3")
    if api_status.get("Anthropic"):
        models_info.append("Claude 4.5 Sonnet")
    st.caption(", ".join(models_info) if models_info else "Нет доступных моделей")

with col2:
    st.markdown("**База данных**")
    db_path = project_root / "contract_ai.db"
    if db_path.exists():
        size_mb = db_path.stat().st_size / (1024 * 1024)
        st.success(f"SQLite — {size_mb:.1f} MB")
    else:
        st.warning("БД не найдена")

    st.markdown("**Директории данных**")
    for dir_name in ["uploads", "exports", "templates"]:
        dir_path = project_root / "data" / dir_name
        exists = dir_path.exists()
        icon = "✅" if exists else "⬜"
        st.caption(f"{icon} data/{dir_name}/")

with col3:
    st.markdown("**Справочник типов договоров**")
    try:
        from src.utils.contract_types import CONTRACT_TYPES, CONTRACT_CATEGORIES
        st.success(f"{len(CONTRACT_TYPES)} типов в {len(CONTRACT_CATEGORIES)} категориях")
    except ImportError:
        st.warning("Справочник недоступен")

    st.markdown("**Режим работы**")
    test_mode = os.environ.get("LLM_TEST_MODE", "true").lower() == "true"
    if test_mode:
        st.warning("🧪 Тестовый режим (экономия токенов)")
    else:
        st.success("🚀 Продакшн-режим")

st.markdown("---")

# ─── Ряд 4: Последняя активность ────────────────────────────
st.markdown("### 📋 Последняя активность")

if history:
    for entry in history[:10]:
        ts = entry.get("timestamp", "")
        event = entry.get("event", "Обработка")
        details = entry.get("details", "")
        status = entry.get("status", "✅")
        st.caption(f"{ts} | {status} {event} — {details}")
else:
    st.info("Пока нет обработок в текущей сессии. Перейдите к анализу или генерации договора.")

# ─── Подвал ──────────────────────────────────────────────────
st.markdown("---")
st.caption("Contract AI System v3.0 | Единая консоль | Анализ | Генерация | Разногласия | Библиотека")
