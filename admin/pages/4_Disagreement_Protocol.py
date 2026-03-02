# -*- coding: utf-8 -*-
"""
Протокол разногласий — формирование юридических возражений к договору
Загрузка/выбор договора → показ рисков → выбор пунктов → генерация протокола → экспорт
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
    page_title="Протокол разногласий — Contract AI",
    page_icon="⚖️",
    layout="wide"
)

from admin.shared.ui_components import apply_custom_css, section_header, risk_emoji, risk_level_ru
from admin.shared.session_helpers import init_session_state, add_to_history

apply_custom_css()
init_session_state()

section_header("⚖️ Протокол разногласий", "Формирование юридических возражений к проблемным пунктам договора")

st.markdown("---")

# ─── Источник данных ─────────────────────────────────────────
st.markdown("### 1️⃣ Источник данных для возражений")

source_mode = st.radio(
    "Откуда взять данные о рисках?",
    [
        "Из текущей сессии (результат предыдущего анализа)",
        "Ввести вручную",
        "Загрузить JSON с результатами анализа",
    ],
    horizontal=True,
    label_visibility="collapsed",
)

risks_data: List[Dict[str, Any]] = []
contract_name = ""
contract_type = ""

if source_mode == "Из текущей сессии (результат предыдущего анализа)":
    # Проверяем session_state на наличие результатов анализа
    analysis_result = st.session_state.get("current_analysis_result")

    if analysis_result:
        st.success("Найден результат анализа в текущей сессии")

        # Извлекаем риски из результата анализа
        if hasattr(analysis_result, "stages"):
            for stage in analysis_result.stages:
                if stage.name == "section_analysis" and stage.status == "success":
                    full_data = stage.results.get("full_data", {})
                    sections = full_data.get("sections", [])
                    for section in sections:
                        for risk in section.get("risks", []):
                            risks_data.append({
                                "section_number": section.get("section_number", ""),
                                "section_title": section.get("section_title", ""),
                                "original_text": section.get("text", "")[:300],
                                "risk_type": risk.get("risk_type", ""),
                                "severity": risk.get("severity", "medium"),
                                "description": risk.get("description", risk.get("title", "")),
                                "consequences": risk.get("consequences", ""),
                                "relevant_laws": risk.get("relevant_laws", []),
                            })
        elif isinstance(analysis_result, dict):
            # Если результат — словарь
            for section in analysis_result.get("sections", []):
                for risk in section.get("risks", []):
                    risks_data.append({
                        "section_number": section.get("section_number", ""),
                        "section_title": section.get("section_title", ""),
                        "original_text": section.get("text", "")[:300],
                        "risk_type": risk.get("risk_type", ""),
                        "severity": risk.get("severity", "medium"),
                        "description": risk.get("description", risk.get("title", "")),
                        "consequences": risk.get("consequences", ""),
                        "relevant_laws": risk.get("relevant_laws", []),
                    })

        contract_name = st.session_state.get("current_contract_name", "")
        contract_type = st.session_state.get("current_contract_type", "")

        if not risks_data:
            st.warning("В результате анализа не найдено рисков. Попробуйте ввести вручную.")
    else:
        st.info("Нет результатов анализа в текущей сессии. Сначала проанализируйте договор на странице «Обработка документов» или введите данные вручную.")

elif source_mode == "Загрузить JSON с результатами анализа":
    uploaded_json = st.file_uploader("Загрузите JSON с результатами анализа", type=["json"])
    if uploaded_json:
        try:
            data = json.loads(uploaded_json.read().decode("utf-8"))
            contract_name = data.get("contract_name", "")
            contract_type = data.get("contract_type", "")

            for section in data.get("sections", data.get("risks", [])):
                if isinstance(section, dict):
                    # Поддержка обоих форматов
                    if "risks" in section:
                        for risk in section["risks"]:
                            risks_data.append({
                                "section_number": section.get("section_number", ""),
                                "section_title": section.get("section_title", ""),
                                "original_text": section.get("text", "")[:300],
                                "severity": risk.get("severity", "medium"),
                                "description": risk.get("description", ""),
                                "consequences": risk.get("consequences", ""),
                                "relevant_laws": risk.get("relevant_laws", []),
                            })
                    else:
                        risks_data.append({
                            "section_number": section.get("section_number", ""),
                            "section_title": section.get("section_title", ""),
                            "original_text": section.get("original_text", "")[:300],
                            "severity": section.get("severity", "medium"),
                            "description": section.get("description", ""),
                            "consequences": section.get("consequences", ""),
                            "relevant_laws": section.get("relevant_laws", []),
                        })

            st.success(f"Загружено {len(risks_data)} рисков")
        except Exception as e:
            st.error(f"Ошибка чтения JSON: {e}")

elif source_mode == "Ввести вручную":
    contract_name = st.text_input("Название договора", placeholder="Договор поставки №123 от 01.01.2026")
    contract_type = st.text_input("Тип договора", placeholder="Договор поставки")

    st.markdown("**Добавьте проблемные пункты:**")

    num_risks = st.number_input("Количество пунктов", min_value=1, max_value=20, value=3)

    for i in range(int(num_risks)):
        with st.expander(f"Пункт {i + 1}", expanded=(i == 0)):
            col1, col2 = st.columns(2)
            with col1:
                sec_num = st.text_input("Номер раздела", key=f"manual_sec_{i}", placeholder="3.1")
                sec_title = st.text_input("Название раздела", key=f"manual_title_{i}", placeholder="Сроки оплаты")
            with col2:
                severity = st.selectbox(
                    "Уровень риска", ["critical", "high", "medium", "low"],
                    key=f"manual_sev_{i}", index=2,
                    format_func=lambda x: f"{risk_emoji(x)} {risk_level_ru(x)}"
                )
            orig_text = st.text_area("Текст пункта договора", key=f"manual_text_{i}", height=60)
            description = st.text_area("Описание проблемы", key=f"manual_desc_{i}", height=60)
            consequences = st.text_input("Возможные последствия", key=f"manual_cons_{i}")

            risks_data.append({
                "section_number": sec_num,
                "section_title": sec_title,
                "original_text": orig_text,
                "severity": severity,
                "description": description,
                "consequences": consequences,
                "relevant_laws": [],
            })

st.markdown("---")

# ─── Шаг 2: Отображение и выбор рисков ──────────────────────
if risks_data:
    st.markdown(f"### 2️⃣ Найденные риски ({len(risks_data)} шт.)")
    st.markdown("Отметьте пункты, по которым нужно сформировать возражения:")

    selected_indices = []

    # Кнопки «выбрать все / снять все»
    col1, col2, _ = st.columns([1, 1, 3])
    with col1:
        select_all = st.button("Выбрать все", use_container_width=True)
    with col2:
        deselect_all = st.button("Снять все", use_container_width=True)

    for i, risk in enumerate(risks_data):
        emoji = risk_emoji(risk.get("severity", "medium"))
        level = risk_level_ru(risk.get("severity", "medium"))
        label = f"{emoji} [{level}] п. {risk.get('section_number', '?')} — {risk.get('description', 'Без описания')[:80]}"

        # Управление выбором
        default = True if select_all else (False if deselect_all else (risk.get("severity") in ("critical", "high")))
        checked = st.checkbox(label, value=default, key=f"risk_select_{i}")
        if checked:
            selected_indices.append(i)

    st.markdown("---")

    # ─── Шаг 3: Генерация протокола ──────────────────────────
    st.markdown("### 3️⃣ Генерация протокола разногласий")

    if not selected_indices:
        st.warning("Выберите хотя бы один пункт для формирования возражений.")

    if st.button(
        f"⚖️ Сформировать протокол ({len(selected_indices)} пунктов)",
        disabled=not selected_indices,
        type="primary",
        use_container_width=True,
    ):
        with st.spinner("Генерация возражений через LLM... Это может занять 30-60 секунд."):
            try:
                from src.services.disagreement_service import DisagreementService, RiskItem

                # Преобразуем в RiskItem
                risk_items = []
                for idx in selected_indices:
                    r = risks_data[idx]
                    risk_items.append(RiskItem(
                        section_number=r.get("section_number", ""),
                        section_title=r.get("section_title", ""),
                        original_text=r.get("original_text", ""),
                        risk_type=r.get("risk_type", ""),
                        severity=r.get("severity", "medium"),
                        description=r.get("description", ""),
                        consequences=r.get("consequences", ""),
                        relevant_laws=r.get("relevant_laws", []),
                    ))

                service = DisagreementService()
                protocol = service.generate(
                    risks=risk_items,
                    contract_name=contract_name,
                    contract_type=contract_type,
                )

                if protocol.success:
                    st.session_state["last_protocol"] = protocol
                    st.session_state["disagreement_protocols"].append({
                        "contract_name": contract_name,
                        "objections_count": len(protocol.objections),
                        "timestamp": datetime.now().isoformat(),
                        "docx_path": protocol.docx_path,
                    })
                    add_to_history({
                        "event": "Протокол разногласий",
                        "details": f"{contract_name}: {len(protocol.objections)} возражений",
                        "status": "✅",
                    })
                    st.success(
                        f"Протокол сгенерирован: {len(protocol.objections)} возражений "
                        f"за {protocol.generation_time:.1f}с ({protocol.tokens_used} токенов)"
                    )
                else:
                    st.error(f"Ошибка: {protocol.error}")

            except Exception as e:
                st.error(f"Ошибка генерации: {e}")

    # ─── Шаг 4: Отображение результата ───────────────────────
    if "last_protocol" in st.session_state and st.session_state["last_protocol"]:
        protocol = st.session_state["last_protocol"]

        if protocol.success and protocol.objections:
            st.markdown("---")
            st.markdown(f"### 📋 Результат: {len(protocol.objections)} возражений")

            for i, obj in enumerate(protocol.objections, 1):
                emoji = risk_emoji(obj.priority)
                level = risk_level_ru(obj.priority)
                with st.expander(f"{emoji} Возражение {i}: п. {obj.section_number} [{level}]", expanded=(i <= 3)):
                    st.markdown(f"**Замечание:** {obj.issue_description}")

                    if obj.legal_basis:
                        st.markdown(f"**Правовое обоснование:** {obj.legal_basis}")

                    if obj.risk_explanation:
                        st.warning(f"**Риски:** {obj.risk_explanation}")

                    if obj.proposed_formulation:
                        st.success(f"**Предлагаемая формулировка:**\n\n{obj.proposed_formulation}")

                    if obj.reasoning:
                        st.info(f"**Обоснование:** {obj.reasoning}")

            # Кнопки экспорта
            st.markdown("---")
            st.markdown("### 📥 Экспорт")

            col1, col2, col3 = st.columns(3)

            with col1:
                if protocol.docx_path and Path(protocol.docx_path).exists():
                    with open(protocol.docx_path, "rb") as f:
                        st.download_button(
                            label="📥 Скачать DOCX",
                            data=f.read(),
                            file_name=Path(protocol.docx_path).name,
                            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                            use_container_width=True,
                            type="primary",
                        )

            with col2:
                if protocol.json_path and Path(protocol.json_path).exists():
                    with open(protocol.json_path, "rb") as f:
                        st.download_button(
                            label="📥 Скачать JSON",
                            data=f.read(),
                            file_name=Path(protocol.json_path).name,
                            mime="application/json",
                            use_container_width=True,
                        )

            with col3:
                st.caption(
                    f"Время: {protocol.generation_time:.1f}с\n"
                    f"Токены: {protocol.tokens_used}\n"
                    f"Дата: {protocol.date}"
                )

# Подвал
st.markdown("---")
st.caption("Contract AI v3.0 | Протокол разногласий | Генерация возражений через LLM с юридическим обоснованием")
