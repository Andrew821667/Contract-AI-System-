# -*- coding: utf-8 -*-
"""
Генерация договоров — создание юридических документов через LLM
Выбор типа → данные сторон → параметры → генерация → предпросмотр + скачивание DOCX
"""
import streamlit as st
import sys
from pathlib import Path
from datetime import datetime, date

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
    page_title="Генерация договоров — Contract AI",
    page_icon="✍️",
    layout="wide"
)

from admin.shared.ui_components import apply_custom_css, section_header
from admin.shared.session_helpers import init_session_state, add_to_history

apply_custom_css()
init_session_state()

section_header("✍️ Генерация договоров", "Создание юридических документов через LLM на основе параметров")

st.markdown("---")

# ─── Шаг 1: Выбор типа договора ─────────────────────────────
st.markdown("### 1️⃣ Тип договора")

try:
    from src.utils.contract_types import (
        CONTRACT_TYPES, CONTRACT_CATEGORIES,
        get_contracts_by_category, get_contract_type_name,
    )
    has_types = True
except ImportError:
    has_types = False
    st.error("Не удалось загрузить справочник типов договоров")

if has_types:
    col1, col2 = st.columns([1, 2])

    with col1:
        category = st.selectbox(
            "Категория",
            list(CONTRACT_CATEGORIES.keys()),
            help="Выберите категорию для фильтрации типов"
        )

    with col2:
        contracts_in_category = get_contracts_by_category(category)
        type_options = {name: code for code, name in contracts_in_category}
        selected_type_name = st.selectbox(
            "Тип договора",
            list(type_options.keys()),
            help="Выберите конкретный тип договора"
        )
        selected_type_code = type_options.get(selected_type_name, "")

    st.markdown("---")

    # ─── Шаг 2: Данные сторон ────────────────────────────────
    st.markdown("### 2️⃣ Данные сторон")

    col_a, col_b = st.columns(2)

    with col_a:
        st.markdown("**Сторона 1 (Заказчик / Покупатель)**")
        a_name = st.text_input("Наименование", value="", key="a_name", placeholder="ООО «Альфа»")
        a_inn = st.text_input("ИНН", value="", key="a_inn", placeholder="7701234567")

        with st.expander("Дополнительные реквизиты Стороны 1"):
            a_ogrn = st.text_input("ОГРН", key="a_ogrn")
            a_address = st.text_input("Юридический адрес", key="a_address")
            a_rep = st.text_input("Представитель (ФИО)", key="a_rep", placeholder="Иванов Иван Иванович")
            a_pos = st.text_input("Должность", key="a_pos", placeholder="Генеральный директор")
            a_basis = st.text_input("Действует на основании", key="a_basis", value="Устава")

    with col_b:
        st.markdown("**Сторона 2 (Исполнитель / Продавец)**")
        b_name = st.text_input("Наименование", value="", key="b_name", placeholder="ООО «Бета»")
        b_inn = st.text_input("ИНН", value="", key="b_inn", placeholder="7709876543")

        with st.expander("Дополнительные реквизиты Стороны 2"):
            b_ogrn = st.text_input("ОГРН", key="b_ogrn")
            b_address = st.text_input("Юридический адрес", key="b_address")
            b_rep = st.text_input("Представитель (ФИО)", key="b_rep", placeholder="Петров Пётр Петрович")
            b_pos = st.text_input("Должность", key="b_pos", placeholder="Генеральный директор")
            b_basis = st.text_input("Действует на основании", key="b_basis", value="Устава")

    st.markdown("---")

    # ─── Шаг 3: Параметры договора ───────────────────────────
    st.markdown("### 3️⃣ Параметры договора")

    col1, col2, col3 = st.columns(3)

    with col1:
        subject = st.text_area(
            "Предмет договора",
            height=80,
            placeholder="Поставка офисной мебели согласно Спецификации",
            help="Опишите, о чём договор"
        )
        city = st.text_input("Город заключения", value="Москва")

    with col2:
        amount = st.text_input("Сумма", placeholder="1 500 000")
        currency = st.selectbox("Валюта", ["рублей", "долларов США", "евро"])
        payment_terms = st.text_area(
            "Условия оплаты",
            height=80,
            placeholder="Предоплата 30%, остаток — в течение 10 рабочих дней после поставки"
        )

    with col3:
        duration = st.text_input("Срок действия", placeholder="12 месяцев")
        start_date = st.date_input("Дата начала", value=date.today())

    additional = st.text_area(
        "Дополнительные условия (необязательно)",
        height=80,
        placeholder="Любые особые условия, которые нужно включить в договор"
    )

    st.markdown("---")

    # ─── Шаг 4: Генерация ────────────────────────────────────
    st.markdown("### 4️⃣ Генерация")

    # Валидация
    can_generate = bool(a_name and b_name and selected_type_code)
    if not can_generate:
        st.warning("Для генерации укажите наименования обеих сторон.")

    if st.button("🚀 Сгенерировать договор", disabled=not can_generate, type="primary", use_container_width=True):
        with st.spinner("Генерация договора через LLM... Это может занять 30-60 секунд."):
            try:
                from src.services.contract_generation_service import (
                    ContractGenerationService, ContractParams, ContractParty
                )

                party_a = ContractParty(
                    name=a_name, inn=a_inn,
                    ogrn=a_ogrn if 'a_ogrn' in dir() else "",
                    address=a_address if 'a_address' in dir() else "",
                    representative=a_rep if 'a_rep' in dir() else "",
                    position=a_pos if 'a_pos' in dir() else "",
                    basis=a_basis if 'a_basis' in dir() else "Устава",
                )
                party_b = ContractParty(
                    name=b_name, inn=b_inn,
                    ogrn=b_ogrn if 'b_ogrn' in dir() else "",
                    address=b_address if 'b_address' in dir() else "",
                    representative=b_rep if 'b_rep' in dir() else "",
                    position=b_pos if 'b_pos' in dir() else "",
                    basis=b_basis if 'b_basis' in dir() else "Устава",
                )

                params = ContractParams(
                    contract_type=selected_type_code,
                    party_a=party_a,
                    party_b=party_b,
                    subject=subject,
                    amount=amount,
                    currency=currency,
                    duration=duration,
                    start_date=start_date.strftime("%d.%m.%Y") if start_date else "",
                    payment_terms=payment_terms,
                    additional_conditions=additional,
                    city=city,
                )

                service = ContractGenerationService()
                result = service.generate(params)

                if result.success:
                    st.success(
                        f"Договор сгенерирован за {result.generation_time:.1f}с "
                        f"({result.tokens_used} токенов)"
                    )

                    # Сохраняем в session_state
                    st.session_state["last_generated_contract"] = result
                    st.session_state["generated_contracts"].append({
                        "type": selected_type_name,
                        "party_a": a_name,
                        "party_b": b_name,
                        "timestamp": datetime.now().isoformat(),
                        "docx_path": result.docx_path,
                    })

                    # Запись в историю
                    add_to_history({
                        "event": "Генерация договора",
                        "details": f"{selected_type_name}: {a_name} ↔ {b_name}",
                        "status": "✅",
                    })
                else:
                    st.error(f"Ошибка генерации: {result.error}")

            except Exception as e:
                st.error(f"Ошибка: {e}")

    # ─── Предпросмотр и скачивание ───────────────────────────
    if "last_generated_contract" in st.session_state and st.session_state["last_generated_contract"]:
        result = st.session_state["last_generated_contract"]

        if result.success:
            st.markdown("---")
            st.markdown("### 📋 Предпросмотр сгенерированного договора")

            # Текст в scrollable-контейнере
            st.text_area(
                "Текст договора",
                value=result.contract_text,
                height=500,
                disabled=True,
                key="contract_preview"
            )

            # Кнопка скачивания DOCX
            col1, col2, col3 = st.columns([2, 2, 1])
            with col1:
                if result.docx_path and Path(result.docx_path).exists():
                    with open(result.docx_path, "rb") as f:
                        st.download_button(
                            label="📥 Скачать DOCX",
                            data=f.read(),
                            file_name=Path(result.docx_path).name,
                            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                            use_container_width=True,
                            type="primary",
                        )

            with col2:
                st.caption(
                    f"Тип: {result.metadata.get('type_name', '')} | "
                    f"Токены: {result.tokens_used} | "
                    f"Время: {result.generation_time:.1f}с"
                )

# Подвал
st.markdown("---")
st.caption("Contract AI v3.0 | Генерация договоров через LLM | 20 типов договоров")
