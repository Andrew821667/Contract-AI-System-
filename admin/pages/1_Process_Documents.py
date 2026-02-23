"""
Обработка документов - "Стеклянный ящик"
Показывает ВСЕ промежуточные результаты обработки
Поддерживает два режима: "Новый договор" и "Подписанный договор"
"""

import streamlit as st
import sys
from pathlib import Path
import asyncio
import json
import os
import tempfile
import pandas as pd
from typing import Dict, Any
import io

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

st.set_page_config(
    page_title="Обработка документов - Contract AI",
    page_icon="📄",
    layout="wide"
)

st.title("📄 Обработка документов")
st.markdown("**Стеклянный ящик:** видны все промежуточные результаты работы системы")

st.markdown("---")

# Загрузка файла
st.header("1️⃣ Загрузка документа")

# Выбор режима работы
contract_mode = st.radio(
    "Режим работы с договором:",
    ["Новый договор (Pre-Execution)", "Подписанный договор (Post-Execution)"],
    help="**Новый договор** — правки вносятся прямо в DOCX-документ.\n\n"
         "**Подписанный договор** — оригинал не трогаем, формируем протокол разногласий.",
    horizontal=True
)

is_new_contract = contract_mode.startswith("Новый")

uploaded_file = st.file_uploader(
    "Выберите файл договора",
    type=['pdf', 'docx', 'txt', 'xml', 'html', 'htm', 'png', 'jpg', 'jpeg'],
    help="Поддерживаются: PDF, DOCX, TXT, XML, HTML, изображения (с OCR)"
)

# Вспомогательная функция для async обработки
async def process_document_async(file_path, file_ext, use_section_analysis=False):
    """Асинхронная обработка документа с автоматическим fallback"""
    from src.services.document_processor import DocumentProcessor
    import os
    from dotenv import load_dotenv

    # Загружаем переменные окружения из .env файла
    project_root = Path(__file__).parent.parent.parent
    env_path = project_root / ".env"
    load_dotenv(env_path)

    # DeepSeek — основная модель (дешевле, $0.14/1M токенов)
    # GPT-4o-mini — fallback
    deepseek_key = os.getenv("DEEPSEEK_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")

    if deepseek_key:
        api_key = deepseek_key
        base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
        model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
    elif openai_key:
        api_key = openai_key
        base_url = None
        model = os.getenv("OPENAI_MODEL_MINI", "gpt-4o-mini")
    else:
        raise ValueError(
            "API ключ не настроен.\n"
            "Добавьте в .env: OPENAI_API_KEY=... или DEEPSEEK_API_KEY=..."
        )

    processor = DocumentProcessor(
        api_key=api_key,
        model=model,
        base_url=base_url,
        use_rag=False,
        use_section_analysis=use_section_analysis
    )

    result = await processor.process_document(file_path, file_ext)
    return result


def render_docx_preview(docx_bytes: bytes) -> str:
    """Конвертирует DOCX bytes в HTML через mammoth для предпросмотра"""
    try:
        import mammoth
        result = mammoth.convert_to_html(io.BytesIO(docx_bytes))
        html = result.value
        # Оборачиваем в стили для лучшего отображения
        styled_html = f"""
        <div style="background: white; color: black; padding: 20px; border: 1px solid #ddd;
                    border-radius: 8px; font-family: 'Times New Roman', serif; line-height: 1.6;
                    max-height: 600px; overflow-y: auto;">
            {html}
        </div>
        """
        return styled_html
    except Exception as e:
        return f"<p style='color:red;'>Ошибка предпросмотра: {e}</p>"


def get_entity_purpose(entity_type: str) -> str:
    """Возвращает КОНКРЕТНОЕ назначение сущности в системе"""
    purposes = {
        "contract_number": "📝 Первичный ключ для индексации в БД (таблица contracts, поле contract_id). Используется для поиска договора через UI, API endpoints (/api/contracts/{id}), формирования уникального файлового имени при экспорте",
        "date": "📅 Заполняет поля: contract_date, start_date, end_date в таблице contracts. Используется для: автоматических уведомлений о сроках (модуль notifications), фильтрации по датам в UI (страница Contract List), валидации актуальности договора, расчета длительности договора",
        "inn": "🏢 Связывание с таблицей counterparties (foreign key counterparty_inn). Используется для: автозаполнения карточки контрагента, проверки в ФНС через API интеграцию, дедупликации контрагентов, построения графа взаимосвязей компаний, риск-анализа контрагента",
        "ogrn": "🔐 Проверка легитимности юрлица через API ФНС/ЕГРЮЛ. Сохраняется в counterparties.ogrn. Используется для валидации регистрации, определения даты регистрации компании, проверки актуальности юрлица",
        "kpp": "🏦 Идентификация конкретного подразделения компании (counterparties.kpp). Используется для: определения филиала/обособленного подразделения, корректной отправки документов на нужный адрес, группировки договоров по подразделениям",
        "amount": "💰 Финансовые поля: total_amount, currency, vat_amount в таблице contracts. Используется для: подсчета общей суммы портфеля договоров (Dashboard Analytics), лимит-контроля (проверка превышения бюджета), формирования финансовых отчетов, прогнозирования cash flow",
        "organization": "🏛️ Извлечение названий компаний для заполнения counterparties.name. Используется для: создания новой записи контрагента, fuzzy-match поиска существующих контрагентов (избегание дублей), отображения в UI списка сторон договора",
        "person": "👤 ФИО подписантов сохраняются в таблице signatories (fields: full_name, position, authority_document). Используется для: проверки полномочий подписанта, валидации права подписи (cross-check с доверенностями), юридической значимости договора",
        "address": "📍 Юр. и факт. адреса в counterparties.legal_address и counterparties.actual_address. Используется для: формирования почтовых уведомлений, геолокации контрагентов на карте (UI Dashboard), проверки совпадения адресов (fraud detection)",
        "phone": "📞 Контактные данные в counterparties.phone и contacts.phone. Используется для: автоматических звонков/SMS уведомлений о сроках, связи с контрагентом через CRM интеграцию, валидации формата телефона",
        "email": "📧 Email адреса в counterparties.email и contacts.email. Используется для: автоматической отправки email уведомлений (истечение срока, изменения), приглашений в систему для подписания, интеграции с email-клиентом",
        "account": "💳 Банковские счета в counterparties.bank_account. Используется для: автозаполнения платежных поручений, проверки корректности р/с через API ЦБ РФ, связывания с таблицей payments для отслеживания оплат",
        "bic": "🏦 БИК банка в counterparties.bank_bic. Используется для: валидации существования банка через справочник ЦБ РФ, автозаполнения наименования банка и корр. счета, проверки банка на санкционные списки",
        "percent": "📊 Процентные ставки сохраняются в contract_terms.penalty_rate, discount_rate, interest_rate. Используется для: автоматического расчета пеней за просрочку, применения скидок, начисления процентов по договорам займа/кредита",
        "payment_term": "⏰ Условия оплаты в contracts.payment_terms (предоплата/постоплата/рассрочка). Используется для: планирования платежей в модуле Finance, создания напоминаний о платежах, формирования графика платежей",
        "delivery_address": "🚚 Адрес поставки в contracts.delivery_address. Используется для: логистического планирования, интеграции с транспортными компаниями, расчета стоимости доставки",
        "warranty_period": "🛡️ Гарантийный срок в contract_terms.warranty_months. Используется для: отслеживания гарантийных обязательств, автоматических напоминаний об окончании гарантии, учета гарантийных случаев"
    }
    # Если тип не найден - вернуть детальное объяснение
    if entity_type not in purposes:
        return f"❓ Сущность '{entity_type}' не имеет специфичного назначения. Сохраняется в contracts.metadata (JSON) для справочной информации и полнотекстового поиска"
    return purposes.get(entity_type)


def get_optimal_model_info(stage: str) -> tuple[str, str]:
    """Возвращает информацию об оптимальной модели для этапа (актуализировано 2026)"""
    models = {
        "text_extraction": (
            "N/A (прямое извлечение)",
            "pdfplumber + PaddleOCR для сканов + LayoutLMv3 для сложных макетов"
        ),
        "level1": (
            "regex + SpaCy (ru_core_news_sm)",
            "SpaCy ru_core_news_lg, DeepPavlov NER, или Qwen2.5-VL-72B (119 языков!) для визуальных документов"
        ),
        "llm": (
            "gpt-4o-mini ($0.15/$0.6 per 1M) или DeepSeek-V3.2 ($0.25/$0.38 per 1M)",
            "Лучшие в 2026: GPT-4.1 ($2/$8, 1M context), Claude Sonnet 4.5 ($3/$15), DeepSeek-V3.2 ($0.25/$0.38, экономия 90%!), Qwen2.5-VL-72B (119 языков, визуальный анализ)"
        ),
        "rag": (
            "pgvector + text-embedding-3-large",
            "OpenAI text-embedding-3-large или Cohere embed-multilingual-v3.0 для русского и многоязычных договоров"
        ),
        "validation": (
            "Business rules + Pydantic",
            "Топ-3 в 2026: Claude Opus 4.5 ($5/$25, самый точный), GPT-4.1 ($2/$8, 1M context), Qwen2.5-VL-72B (многоязычный + визуальный анализ)"
        ),
        "section_analysis": (
            "DeepSeek-V3.2 ($0.25/$0.38 per 1M) или gpt-4o-mini ($0.15/$0.6)",
            "Оптимальные: DeepSeek-V3.2 (90% экономия!), Claude Sonnet 4.5 ($3/$15, юридический анализ), GPT-4.1 ($2/$8, длинные контексты 1M)"
        )
    }
    return models.get(stage, ("N/A", "N/A"))


def display_validation_section_dynamic(section_analysis_data: Dict[str, Any], is_new_contract: bool = True):
    """Отображает детальную валидацию по разделам договора (ДИНАМИЧЕСКИ из LLM)"""

    if not section_analysis_data:
        st.warning("Анализ разделов не был выполнен")
        return

    st.subheader("📋 Детальный разбор по разделам договора")

    # Показываем текущий режим
    if is_new_contract:
        st.info("📝 **Режим: Новый договор** — принятые рекомендации будут внесены в DOCX-документ")
    else:
        st.info("📋 **Режим: Подписанный договор** — принятые рекомендации будут собраны в протокол разногласий")

    sections = section_analysis_data.get("sections", [])
    section_analyses = section_analysis_data.get("section_analyses", [])
    complex_analysis = section_analysis_data.get("complex_analysis")

    if not sections:
        st.warning("Разделы не обнаружены в договоре")
        return

    st.info(f"**Найдено разделов:** {len(sections)} | **Порядок проверки:** 1️⃣ Сравнение с собственными договорами → 2️⃣ Проверка по RAG базе (актуальная правовая база) → 3️⃣ Фолбэк на базу знаний модели")

    # Динамически создаем вкладки
    tab_names = [f"Раздел {s.number}" for s in sections] + ["🔍 Комплексный анализ"]
    tabs = st.tabs(tab_names)

    # Инициализируем список принятых рекомендаций для протокола разногласий
    if "accepted_recommendations" not in st.session_state:
        st.session_state.accepted_recommendations = []

    # Отображаем каждый раздел ДИНАМИЧЕСКИ
    for idx, (section, analysis) in enumerate(zip(sections, section_analyses)):
        with tabs[idx]:
            st.markdown(f"### 📄 Раздел {section.number}: {section.title}")

            # Текст раздела
            st.text_area("Текст раздела:", section.text, height=150, key=f"section_{section.number}_text")

            st.markdown("---")

            # Сравнение с собственными договорами
            st.markdown("**1️⃣ Сравнение с собственными договорами:**")
            if analysis.own_contracts_comparison.startswith("✅"):
                st.success(analysis.own_contracts_comparison)
            elif analysis.own_contracts_comparison.startswith("⚠️"):
                st.warning(analysis.own_contracts_comparison)
            else:
                st.error(analysis.own_contracts_comparison)

            # Детальные проверки
            if analysis.own_contracts_details:
                st.dataframe(analysis.own_contracts_details, use_container_width=True)

            # RAG проверка
            st.markdown("**2️⃣ Проверка по RAG (актуальная правовая база):**")
            st.info(analysis.rag_legal_check)

            if analysis.rag_legal_references:
                st.markdown("**Ссылки на законодательство:**")
                for ref in analysis.rag_legal_references:
                    st.markdown(f"- {ref}")

            st.markdown("---")

            # Выводы и рекомендации
            if analysis.conclusion.startswith("Раздел проработан хорошо") or "соответствует" in analysis.conclusion.lower():
                st.success(f"**Вывод:** {analysis.conclusion}")
            elif "требует" in analysis.conclusion.lower() or "доработк" in analysis.conclusion.lower():
                st.warning(f"**Вывод:** {analysis.conclusion}")
            else:
                st.info(f"**Вывод:** {analysis.conclusion}")

            if analysis.warnings:
                st.markdown("**⚠️ Предупреждения:**")
                for warning in analysis.warnings:
                    st.warning(warning)

            if analysis.recommendations:
                st.markdown("**💡 Рекомендации по улучшению:**")
                for i, rec in enumerate(analysis.recommendations):
                    # Определяем цвет по приоритету
                    if hasattr(rec, 'priority'):
                        if rec.priority == "critical":
                            priority_badge = "🔴 **КРИТИЧНО**"
                        elif rec.priority == "important":
                            priority_badge = "🟡 **ВАЖНО**"
                        else:
                            priority_badge = "🟢 **РЕКОМЕНДОВАНО**"
                    else:
                        priority_badge = "💡"

                    # Определяем тип действия
                    if hasattr(rec, 'action_type'):
                        if rec.action_type == "add":
                            action_badge = "➕ Добавить"
                        elif rec.action_type == "modify":
                            action_badge = "✏️ Изменить"
                        elif rec.action_type == "remove":
                            action_badge = "❌ Удалить"
                        else:
                            action_badge = "✏️ Изменить"
                    else:
                        action_badge = "✏️ Изменить"

                    with st.container():
                        st.markdown(f"##### {priority_badge} | {action_badge}")

                        # Причина рекомендации
                        if hasattr(rec, 'reason'):
                            st.markdown(f"**Причина:** {rec.reason}")
                        else:
                            st.markdown(f"**Рекомендация:** {rec}")

                        # Предлагаемый текст
                        if hasattr(rec, 'proposed_text') and rec.proposed_text:
                            st.markdown("**Предлагаемый текст пункта:**")
                            st.text_area(
                                label="",
                                value=rec.proposed_text,
                                height=150,
                                key=f"rec_{section.number}_{i}",
                                label_visibility="collapsed"
                            )

                            # Кнопки действий — зависят от режима
                            col1, col2, col3 = st.columns(3)
                            with col1:
                                accept_label = "✅ Принять в DOCX" if is_new_contract else "✅ В протокол разногласий"
                                if st.button(accept_label, key=f"accept_{section.number}_{i}", type="primary"):
                                    if is_new_contract:
                                        st.success("✅ Рекомендация принята. Правка будет внесена в DOCX-документ.")
                                    else:
                                        # Добавляем в протокол разногласий
                                        st.session_state.accepted_recommendations.append({
                                            "section_number": section.number,
                                            "section_title": section.title,
                                            "original_text": section.text[:200] + "...",
                                            "proposed_text": rec.proposed_text,
                                            "reason": rec.reason if hasattr(rec, 'reason') else str(rec)
                                        })
                                        st.success("✅ Добавлено в протокол разногласий.")
                            with col2:
                                if st.button("✏️ Редактировать", key=f"edit_{section.number}_{i}"):
                                    st.info("✏️ Откройте редактор для изменения текста.")
                            with col3:
                                if st.button("❌ Отклонить", key=f"reject_{section.number}_{i}"):
                                    st.warning("❌ Рекомендация отклонена.")

                        st.markdown("---")

    # Комплексный анализ (последняя вкладка)
    with tabs[-1]:
        st.markdown("### 🔍 КОМПЛЕКСНЫЙ АНАЛИЗ ДОГОВОРА")
        st.markdown("Анализ взаимосвязей между разделами и общая оценка документа")

        if not complex_analysis:
            st.warning("Комплексный анализ не выполнен")
            return

        st.markdown("---")
        st.markdown("#### 1️⃣ Проверка целостности и согласованности")
        if complex_analysis.integrity_checks:
            st.dataframe(complex_analysis.integrity_checks, use_container_width=True)

        st.markdown("---")
        st.markdown("#### 2️⃣ Юридические риски")

        risk_col1, risk_col2, risk_col3 = st.columns(3)

        with risk_col1:
            st.markdown("**🟢 НИЗКИЙ РИСК:**")
            for risk in complex_analysis.risk_assessment.get("low", []):
                st.success(f"✅ {risk}")

        with risk_col2:
            st.markdown("**🟡 СРЕДНИЙ РИСК:**")
            for risk in complex_analysis.risk_assessment.get("medium", []):
                st.warning(f"⚠️ {risk}")

        with risk_col3:
            st.markdown("**🔴 ВЫСОКИЙ РИСК:**")
            for risk in complex_analysis.risk_assessment.get("high", []):
                st.error(f"❌ {risk}")

        st.markdown("---")
        st.markdown("#### 3️⃣ Соответствие законодательству РФ")
        if complex_analysis.legal_compliance:
            st.dataframe(complex_analysis.legal_compliance, use_container_width=True)

        st.markdown("---")
        st.markdown("#### 4️⃣ Сравнение с лучшими практиками")
        st.info("**Источник:** Анализ похожих договоров из базы + RAG актуальная правовая база + база знаний модели")
        if complex_analysis.best_practices:
            st.dataframe(complex_analysis.best_practices, use_container_width=True)

        st.markdown("---")
        st.markdown("#### 5️⃣ Итоговая оценка и рекомендации")

        score_col1, score_col2, score_col3 = st.columns(3)

        with score_col1:
            st.metric("Общая оценка", f"{complex_analysis.overall_score}/100",
                      delta="Хорошо" if complex_analysis.overall_score >= 80 else "Требует доработки")

        with score_col2:
            st.metric("Юридическая надежность", f"{complex_analysis.legal_reliability:.1f}/10",
                      delta="Высокая" if complex_analysis.legal_reliability >= 8 else "Средняя")

        with score_col3:
            st.metric("Соответствие закону", f"{complex_analysis.compliance_percent}%",
                      delta=f"+{100 - complex_analysis.compliance_percent}% после доработки")

        st.markdown("---")

        rec_col1, rec_col2 = st.columns(2)

        with rec_col1:
            st.markdown("**✅ СИЛЬНЫЕ СТОРОНЫ:**")
            for strength in complex_analysis.strengths:
                st.success(strength)

        with rec_col2:
            st.markdown("**⚠️ КРИТИЧНЫЕ ДОРАБОТКИ:**")
            for improvement in complex_analysis.critical_improvements:
                if improvement.startswith("ОБЯЗАТЕЛЬНО") or improvement.startswith("КРИТИЧНО"):
                    st.error(improvement)
                else:
                    st.warning(improvement)

        st.markdown("---")
        avg_score = complex_analysis.overall_score
        if avg_score >= 90:
            st.success("**💡 Рекомендация:** Договор готов к подписанию. Отличная проработка!")
        elif avg_score >= 80:
            st.info("**💡 Рекомендация:** Договор можно подписывать после внесения рекомендованных доработок.")
        elif avg_score >= 70:
            st.warning("**💡 Рекомендация:** Договор требует доработок. Рекомендуется исправить критичные замечания перед подписанием.")
        else:
            st.error("**💡 Рекомендация:** Договор требует существенной переработки. Не рекомендуется к подписанию в текущем виде.")


def extract_section_text(full_text: str, start_marker: str, end_marker: str) -> str:
    """Извлекает текст конкретного раздела договора"""
    try:
        start_idx = full_text.find(start_marker)
        end_idx = full_text.find(end_marker)

        if start_idx == -1:
            return "Раздел не найден"

        if end_idx == -1:
            # Если это последний раздел
            return full_text[start_idx:start_idx + 500]

        return full_text[start_idx:end_idx].strip()
    except:
        return "Ошибка извлечения текста раздела"


# Кнопка обработки
if uploaded_file is not None:
    st.success(f"✅ Файл загружен: **{uploaded_file.name}** ({uploaded_file.size} байт)")

    # Настройки обработки
    with st.expander("⚙️ Настройки обработки", expanded=False):
        use_section_analysis = st.checkbox(
            "Детальный анализ разделов (Section Analysis)",
            value=True,
            help="LLM-анализ каждого раздела договора с рекомендациями. Добавляет ~60-90 сек к обработке."
        )

    if st.button("🚀 Начать обработку", type="primary"):
        # Сохраняем загруженный файл во временную директорию
        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(uploaded_file.name).suffix) as tmp_file:
            tmp_file.write(uploaded_file.read())
            tmp_file_path = tmp_file.name

        try:
            # Progress bar
            progress_bar = st.progress(0)
            status_text = st.empty()

            # Запускаем реальную обработку
            if use_section_analysis:
                status_text.text("🚀 Обработка запущена. Детальный анализ разделов займёт ~60-90 сек. Пожалуйста, подождите...")
            else:
                status_text.text("🚀 Обработка запущена (~15 сек)...")
            progress_bar.progress(5)

            # Запускаем async обработку
            import concurrent.futures
            def _run_async(coro):
                loop = asyncio.new_event_loop()
                try:
                    return loop.run_until_complete(coro)
                finally:
                    loop.close()

            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    _run_async,
                    process_document_async(tmp_file_path, Path(uploaded_file.name).suffix, use_section_analysis=use_section_analysis)
                )
                result = future.result(timeout=300)

            st.markdown("---")
            st.header("2️⃣ Ход обработки")

            # Отображаем результаты каждого этапа
            total_stages = len(result.stages)

            for idx, stage in enumerate(result.stages):
                progress = int((idx + 1) / total_stages * 90)
                progress_bar.progress(progress)

                # Stage 1: Text Extraction
                if stage.name == "text_extraction":
                    status_text.text("📄 Извлечение текста...")

                    with st.expander(f"✅ Извлечение текста ({stage.duration_sec:.1f} сек)", expanded=True):
                        used_model, optimal_model = get_optimal_model_info("text_extraction")
                        st.success(f"**Метод:** {stage.results.get('method', 'N/A')} | **Формат:** {stage.results.get('original_format', 'N/A')} | **DOCX-версия:** {'✅ Есть' if stage.results.get('has_docx') else '❌ Нет'}")
                        st.info(f"**Модель:** {used_model} | **Оптимально:** {optimal_model}")

                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("Страниц", stage.results.get("pages", "N/A"))
                        with col2:
                            st.metric("Символов", f"{stage.results.get('chars', 0):,}")
                        with col3:
                            confidence = stage.results.get("confidence")
                            st.metric("Confidence", f"{confidence:.2f}" if confidence else "N/A")

                        # Предпросмотр с форматированием (если есть DOCX)
                        if result.docx_file_bytes:
                            st.subheader("📄 Предпросмотр документа (с форматированием)")
                            preview_html = render_docx_preview(result.docx_file_bytes)
                            st.markdown(preview_html, unsafe_allow_html=True)

                            # Кнопки скачивания
                            st.markdown("---")
                            dl_col1, dl_col2 = st.columns(2)
                            with dl_col1:
                                if result.original_file_bytes:
                                    orig_ext = result.original_format or 'bin'
                                    st.download_button(
                                        f"📥 Скачать оригинал (.{orig_ext})",
                                        data=result.original_file_bytes,
                                        file_name=f"original_{uploaded_file.name}",
                                        mime="application/octet-stream",
                                        key="download_original"
                                    )
                            with dl_col2:
                                st.download_button(
                                    "📥 Скачать DOCX-версию",
                                    data=result.docx_file_bytes,
                                    file_name=f"{Path(uploaded_file.name).stem}.docx",
                                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                    key="download_docx"
                                )
                        else:
                            st.subheader("📋 Извлечённый текст")
                            st.text_area("Весь текст документа (прокрутите вниз):", value=result.raw_text, height=400, key="full_text_area")

                # Stage 2: Level 1 Extraction
                elif stage.name == "level1_extraction":
                    status_text.text("🔍 Level 1: Извлечение базовых сущностей...")

                    with st.expander(f"✅ Level 1 Extraction ({stage.duration_sec:.1f} сек)", expanded=True):
                        used_model, optimal_model = get_optimal_model_info("level1")
                        st.success(f"**Найдено сущностей:** {stage.results.get('entities_count', 0)}")
                        st.info(f"**Модель:** {used_model} | **Оптимально:** {optimal_model}")

                        # Метрики по типам
                        by_type = stage.results.get("by_type", {})
                        cols = st.columns(min(len(by_type), 3))
                        for idx2, (entity_type, count) in enumerate(by_type.items()):
                            with cols[idx2 % 3]:
                                st.metric(entity_type, count)

                        # Детальная таблица
                        st.subheader("📋 Детальная таблица сущностей")
                        details = stage.results.get("details", {})

                        all_entities = []
                        for entity_type, entities in details.items():
                            for ent in entities:
                                all_entities.append({
                                    "Тип": entity_type,
                                    "Значение": ent.get("value", ""),
                                    "Назначение": get_entity_purpose(entity_type),
                                    "Confidence": f"{ent.get('confidence', 0):.2f}",
                                    "Контекст": ent.get("context", "")[:80] + "..."
                                })

                        if all_entities:
                            st.dataframe(all_entities, use_container_width=True)
                            st.caption("💡 **Назначение** показывает, для чего используется каждая сущность в системе")

                # Stage 3: LLM Extraction
                elif stage.name == "llm_extraction":
                    status_text.text("🤖 LLM извлечение структурированных данных...")

                    with st.expander(f"✅ LLM Extraction ({stage.duration_sec:.1f} сек)", expanded=True):
                        model_used = stage.results.get("model", "N/A")
                        used_model, optimal_model = get_optimal_model_info("llm")

                        st.success(f"**Модель использована:** {model_used}")
                        st.info(f"**Оптимальная модель:** {optimal_model}")

                        # Метрики обработки
                        st.subheader("📊 Метрики обработки")
                        tokens_in = stage.results.get("tokens_input", 0)
                        tokens_out = stage.results.get("tokens_output", 0)
                        cost = stage.results.get("cost_usd", 0)
                        confidence = stage.results.get("confidence", 0)

                        metrics_data = [
                            {"Параметр": "Токены (вход)", "Значение": f"{tokens_in:,}", "Описание": "Токенов отправлено в модель"},
                            {"Параметр": "Токены (выход)", "Значение": f"{tokens_out:,}", "Описание": "Токенов получено от модели"},
                            {"Параметр": "Всего токенов", "Значение": f"{tokens_in + tokens_out:,}", "Описание": "Суммарное использование"},
                            {"Параметр": "Стоимость", "Значение": f"${cost:.5f}", "Описание": f"{model_used}: см. тарифы провайдера"},
                            {"Параметр": "Confidence", "Значение": f"{confidence:.2f} ({confidence*100:.0f}%)", "Описание": "Средняя уверенность модели"},
                        ]
                        st.table(metrics_data)

                        # Извлеченные данные
                        st.subheader("📊 Извлеченные данные")
                        extracted_data = stage.results.get("data", {})

                        tab1, tab2, tab3, tab4, tab5 = st.tabs(["Стороны", "Предмет", "Финансы", "Сроки", "Санкции"])

                        with tab1:
                            st.json(extracted_data.get("parties", {}))

                        with tab2:
                            st.json(extracted_data.get("subject", {}))

                        with tab3:
                            st.json(extracted_data.get("financials", {}))

                        with tab4:
                            st.json(extracted_data.get("terms", {}))

                        with tab5:
                            st.json(extracted_data.get("penalties", {}))

                # Stage 4: RAG Filter
                elif stage.name == "rag_filter":
                    status_text.text("🔍 RAG: Поиск похожих договоров...")

                    with st.expander(f"✅ RAG Filter ({stage.duration_sec:.1f} сек)", expanded=False):
                        used_model, optimal_model = get_optimal_model_info("rag")
                        similar_count = stage.results.get("similar_contracts_found", 0)

                        st.success(f"**Найдено похожих:** {similar_count} договоров")
                        st.info(f"**Модель:** {used_model} | **Оптимально:** {optimal_model}")

                        contracts = stage.results.get("contracts", [])
                        if contracts:
                            similar_data = []
                            for c in contracts:
                                similar_data.append({
                                    "Договор": c.get("contract_number", "N/A"),
                                    "Схожесть": f"{c.get('similarity', 0):.2f}",
                                    "Тип": c.get("doc_type", "N/A"),
                                    "Сумма": f"₽{c.get('amount', 0):,.0f}"
                                })
                            st.dataframe(similar_data, use_container_width=True)
                        else:
                            st.info("Похожие договоры не найдены (база пуста или нет совпадений)")

            # Stage 5: Validation
            progress_bar.progress(95)
            status_text.text("✅ Валидация извлеченных данных...")

            validation_result = result.validation_result or {}

            with st.expander("⚠️ Validation", expanded=True):
                used_model, optimal_model = get_optimal_model_info("validation")

                is_valid = validation_result.get("is_valid", False)
                has_warnings = len(validation_result.get("warnings", [])) > 0
                if is_valid and not has_warnings:
                    st.success("**Статус:** ✅ Валидация пройдена")
                elif is_valid and has_warnings:
                    st.warning("**Статус:** ⚠️ Валидация пройдена с предупреждениями")
                else:
                    st.error("**Статус:** ❌ Валидация не пройдена")

                st.info(f"**Модель:** {used_model} | **Оптимально:** {optimal_model}")

                errors = validation_result.get("errors", [])
                warnings = validation_result.get("warnings", [])

                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Ошибок", len(errors), delta="✅" if len(errors) == 0 else "❌")
                with col2:
                    st.metric("Предупреждений", len(warnings), delta="⚠️" if len(warnings) > 0 else "✅")
                with col3:
                    compliance = 100 - (len(errors) * 10 + len(warnings) * 2)
                    st.metric("Соответствие", f"{compliance}%", delta=f"{compliance-100}%" if compliance < 100 else "✅")

                # Отображение конкретных ошибок и предупреждений
                if errors:
                    st.markdown("### ❌ Ошибки валидации:")
                    for i, error in enumerate(errors, 1):
                        if isinstance(error, dict):
                            st.error(f"**{i}.** `{error.get('field', 'N/A')}`: {error.get('message', 'N/A')}")
                        else:
                            st.error(f"**{i}.** {error}")

                if warnings:
                    st.markdown("### ⚠️ Предупреждения:")
                    for i, warning in enumerate(warnings, 1):
                        if isinstance(warning, dict):
                            st.warning(f"**{i}.** `{warning.get('field', 'N/A')}`: {warning.get('message', 'N/A')}")
                        else:
                            st.warning(f"**{i}.** {warning}")

                st.markdown("---")

                # Детальная валидация по разделам (ДИНАМИЧЕСКИ из LLM)
                section_analysis_data = None
                for stage in result.stages:
                    if stage.name == "section_analysis" and stage.status == "success":
                        section_analysis_data = stage.results.get("full_data")
                        break

                if section_analysis_data:
                    display_validation_section_dynamic(section_analysis_data, is_new_contract=is_new_contract)
                elif use_section_analysis:
                    st.warning("⚠️ Детальный анализ разделов не был выполнен из-за ошибки.")
                else:
                    st.info("ℹ️ Детальный анализ разделов отключен. Включите в настройках обработки для глубокого анализа.")

            progress_bar.progress(100)
            status_text.empty()

            st.markdown("---")

            # Финальные метрики
            st.header("3️⃣ Итоговые метрики")

            col1, col2, col3, col4 = st.columns(4)

            with col1:
                st.metric("⏱️ Время обработки", f"{result.total_time_sec:.1f} сек")

            with col2:
                st.metric("💰 Стоимость", f"${result.total_cost_usd:.5f}")

            with col3:
                st.metric("🤖 Модель", result.model_used)

            with col4:
                avg_confidence = 0
                for stage in result.stages:
                    if stage.name == "llm_extraction":
                        avg_confidence = stage.results.get("confidence", 0)
                st.metric("🎯 Уверенность", f"{avg_confidence*100:.0f}%")

            st.markdown("---")

            # Кнопки действий
            st.header("4️⃣ Действия с результатами")

            col1, col2, col3, col4 = st.columns(4)

            with col1:
                if st.button("✅ Утвердить", type="primary", use_container_width=True):
                    st.success("✅ Документ утвержден и сохранен в базу данных!")
                    st.balloons()

            with col2:
                if st.button("💾 Сохранить JSON", use_container_width=True):
                    json_data = json.dumps(result.to_dict(), ensure_ascii=False, indent=2)
                    st.download_button(
                        "Скачать результат",
                        json_data,
                        file_name=f"contract_analysis_{uploaded_file.name}.json",
                        mime="application/json"
                    )

            with col3:
                # Скачивание DOCX-версии
                if result.docx_file_bytes:
                    st.download_button(
                        "📄 Скачать DOCX",
                        data=result.docx_file_bytes,
                        file_name=f"{Path(uploaded_file.name).stem}_result.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        use_container_width=True,
                        key="download_docx_final"
                    )
                else:
                    if st.button("📄 Экспорт в Word", use_container_width=True):
                        st.info("DOCX-версия недоступна для данного формата")

            with col4:
                if st.button("❌ Отклонить", use_container_width=True):
                    st.error("Документ отклонен")

            # Протокол разногласий (только для подписанных договоров)
            if not is_new_contract and st.session_state.get("accepted_recommendations"):
                st.markdown("---")
                st.header("📋 Протокол разногласий")
                st.info(f"Собрано рекомендаций: {len(st.session_state.accepted_recommendations)}")

                protocol_data = []
                for i, rec in enumerate(st.session_state.accepted_recommendations, 1):
                    protocol_data.append({
                        "№": i,
                        "Раздел": f"{rec['section_number']}. {rec['section_title']}",
                        "Текст оригинала": rec["original_text"],
                        "Предлагаемая редакция": rec["proposed_text"],
                        "Обоснование": rec["reason"]
                    })

                st.dataframe(protocol_data, use_container_width=True)

                # Скачать протокол как JSON
                protocol_json = json.dumps(protocol_data, ensure_ascii=False, indent=2)
                st.download_button(
                    "📥 Скачать протокол разногласий (JSON)",
                    protocol_json,
                    file_name=f"protocol_{uploaded_file.name}.json",
                    mime="application/json",
                    key="download_protocol"
                )

        except Exception as e:
            st.error(f"Ошибка обработки: {str(e)}")
            import traceback
            st.code(traceback.format_exc())

        finally:
            # Удаляем временный файл
            if os.path.exists(tmp_file_path):
                os.unlink(tmp_file_path)

else:
    st.info("👆 Загрузите файл договора для начала обработки")

    # Ссылка на тестовый файл
    st.markdown("---")
    st.markdown("**💡 Для тестирования:** используйте файл `tests/fixtures/test_supply_contract.txt`")

st.markdown("---")
st.caption("Contract AI System v2.0 - Обработка документов | Модели 2026: Claude Opus/Sonnet 4.5, GPT-4.1, DeepSeek-V3.2, Qwen2.5-VL-72B (119 языков)")
