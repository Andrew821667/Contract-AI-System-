# -*- coding: utf-8 -*-
"""
Библиотека договоров — все обработанные и сгенерированные документы
Таблица с фильтрами, детали анализа, повторный анализ, экспорт
"""
import streamlit as st
import sys
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List

# Путь к корню проекта
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Загрузка .env
env_path = project_root / ".env"
if env_path.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(env_path)
    except ImportError:
        pass

st.set_page_config(
    page_title="Библиотека договоров — Contract AI",
    page_icon="📚",
    layout="wide"
)

from admin.shared.ui_components import apply_custom_css, section_header, risk_emoji, risk_level_ru
from admin.shared.session_helpers import init_session_state

apply_custom_css()
init_session_state()

section_header("📚 Библиотека договоров", "Все обработанные и сгенерированные документы")

st.markdown("---")

# ─── Сбор данных из session_state ────────────────────────────
# Обработанные документы (из истории обработки)
processing_history = st.session_state.get("processing_history", [])
generated_contracts = st.session_state.get("generated_contracts", [])
disagreement_protocols = st.session_state.get("disagreement_protocols", [])

# Объединяем все записи в единый список
all_items: List[Dict[str, Any]] = []

for entry in processing_history:
    all_items.append({
        "type": "Анализ",
        "icon": "📄",
        "name": entry.get("details", "Документ"),
        "contract_type": entry.get("contract_type", "—"),
        "risk_level": entry.get("risk_level", "—"),
        "status": entry.get("status", "✅"),
        "timestamp": entry.get("timestamp", ""),
        "source": "processing",
        "data": entry,
    })

for entry in generated_contracts:
    all_items.append({
        "type": "Генерация",
        "icon": "✍️",
        "name": f"{entry.get('type', '?')}: {entry.get('party_a', '')} ↔ {entry.get('party_b', '')}",
        "contract_type": entry.get("type", "—"),
        "risk_level": "—",
        "status": "✅",
        "timestamp": entry.get("timestamp", ""),
        "source": "generated",
        "data": entry,
    })

for entry in disagreement_protocols:
    all_items.append({
        "type": "Протокол",
        "icon": "⚖️",
        "name": entry.get("contract_name", "Протокол разногласий"),
        "contract_type": "—",
        "risk_level": "—",
        "status": f"✅ {entry.get('objections_count', 0)} возражений",
        "timestamp": entry.get("timestamp", ""),
        "source": "disagreement",
        "data": entry,
    })

# Сортировка по дате (новые первыми)
all_items.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

# ─── Фильтры ────────────────────────────────────────────────
st.markdown("### 🔍 Фильтры")

col1, col2, col3 = st.columns(3)

with col1:
    filter_type = st.multiselect(
        "Тип операции",
        ["Анализ", "Генерация", "Протокол"],
        default=["Анализ", "Генерация", "Протокол"],
    )

with col2:
    filter_risk = st.multiselect(
        "Уровень риска",
        ["critical", "high", "medium", "low", "—"],
        default=["critical", "high", "medium", "low", "—"],
        format_func=lambda x: f"{risk_emoji(x)} {risk_level_ru(x)}" if x != "—" else "— Не определён"
    )

with col3:
    search_query = st.text_input("Поиск по названию", placeholder="Введите текст для поиска")

# Применяем фильтры
filtered = all_items
if filter_type:
    filtered = [i for i in filtered if i["type"] in filter_type]
if filter_risk:
    filtered = [i for i in filtered if i["risk_level"] in filter_risk]
if search_query:
    q = search_query.lower()
    filtered = [i for i in filtered if q in i.get("name", "").lower() or q in i.get("contract_type", "").lower()]

st.markdown("---")

# ─── Статистика ──────────────────────────────────────────────
st.markdown("### 📊 Статистика")

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Всего записей", len(all_items))
with col2:
    st.metric("Анализов", sum(1 for i in all_items if i["type"] == "Анализ"))
with col3:
    st.metric("Генераций", sum(1 for i in all_items if i["type"] == "Генерация"))
with col4:
    st.metric("Протоколов", sum(1 for i in all_items if i["type"] == "Протокол"))

st.markdown("---")

# ─── Таблица документов ─────────────────────────────────────
st.markdown(f"### 📋 Документы ({len(filtered)} из {len(all_items)})")

if not filtered:
    st.info(
        "Библиотека пуста. Документы появятся здесь после:\n"
        "- Анализа договора на странице «Обработка документов»\n"
        "- Генерации договора на странице «Генерация договоров»\n"
        "- Формирования протокола на странице «Протокол разногласий»"
    )
else:
    for i, item in enumerate(filtered):
        with st.expander(
            f"{item['icon']} [{item['type']}] {item['name'][:80]}",
            expanded=False
        ):
            col1, col2, col3 = st.columns([2, 1, 1])

            with col1:
                st.markdown(f"**Название:** {item['name']}")
                if item['contract_type'] != "—":
                    st.markdown(f"**Тип договора:** {item['contract_type']}")
                if item['risk_level'] != "—":
                    st.markdown(f"**Уровень риска:** {risk_emoji(item['risk_level'])} {risk_level_ru(item['risk_level'])}")

            with col2:
                st.markdown(f"**Статус:** {item['status']}")
                if item['timestamp']:
                    try:
                        dt = datetime.fromisoformat(item['timestamp'])
                        st.markdown(f"**Дата:** {dt.strftime('%d.%m.%Y %H:%M')}")
                    except (ValueError, TypeError):
                        st.markdown(f"**Дата:** {item['timestamp']}")

            with col3:
                # Кнопки действий
                data = item.get("data", {})
                docx_path = data.get("docx_path", "")

                if docx_path and Path(docx_path).exists():
                    with open(docx_path, "rb") as f:
                        st.download_button(
                            label="📥 DOCX",
                            data=f.read(),
                            file_name=Path(docx_path).name,
                            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                            key=f"download_{i}",
                            use_container_width=True,
                        )

                # Ссылки на повторные действия
                if item["type"] == "Анализ":
                    if st.button("🔄 Повторить анализ", key=f"reanalyze_{i}", use_container_width=True):
                        st.switch_page("pages/1_Process_Documents.py")
                elif item["type"] == "Генерация":
                    if st.button("✍️ Новая генерация", key=f"regenerate_{i}", use_container_width=True):
                        st.switch_page("pages/2_Generate_Contract.py")

# ─── Экспорт всей библиотеки ────────────────────────────────
if all_items:
    st.markdown("---")
    st.markdown("### 📤 Экспорт библиотеки")

    export_data = []
    for item in all_items:
        export_data.append({
            "type": item["type"],
            "name": item["name"],
            "contract_type": item["contract_type"],
            "risk_level": item["risk_level"],
            "status": item["status"],
            "timestamp": item["timestamp"],
        })

    json_str = json.dumps(export_data, ensure_ascii=False, indent=2)
    st.download_button(
        label="📥 Экспортировать библиотеку (JSON)",
        data=json_str.encode("utf-8"),
        file_name=f"contract_library_{datetime.now().strftime('%Y%m%d')}.json",
        mime="application/json",
    )

# Подвал
st.markdown("---")
st.caption("Contract AI v3.0 | Библиотека договоров | Все обработанные и сгенерированные документы")
