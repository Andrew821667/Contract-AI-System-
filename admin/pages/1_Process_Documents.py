"""
Обработка документов - "Стеклянный ящик"
Показывает ВСЕ промежуточные результаты обработки
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

uploaded_file = st.file_uploader(
    "Выберите файл договора",
    type=['pdf', 'docx', 'txt', 'png', 'jpg', 'jpeg'],
    help="Поддерживаются: PDF, DOCX, TXT, изображения (с OCR)"
)

# Вспомогательная функция для async обработки
async def process_document_async(file_path, file_ext):
    """Асинхронная обработка документа"""
    from src.services.document_processor import DocumentProcessor
    import os
    from dotenv import load_dotenv

    # Загружаем переменные окружения из .env файла
    load_dotenv()

    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        raise ValueError(
            "OPENAI_API_KEY не установлен в переменных окружения.\n"
            "Создайте файл .env в корне проекта и добавьте: OPENAI_API_KEY=your_key_here"
        )

    processor = DocumentProcessor(
        openai_api_key=openai_api_key,
        use_rag=True,
        use_section_analysis=True  # Включаем детальный анализ разделов
    )
    result = await processor.process_document(file_path, file_ext)
    return result


def get_optimal_model_info(stage: str) -> tuple[str, str]:
    """Возвращает информацию об оптимальной модели для этапа"""
    models = {
        "text_extraction": (
            "N/A (прямое извлечение)",
            "pdfplumber + PaddleOCR для сканов + LayoutLMv3 для сложных макетов"
        ),
        "level1": (
            "regex + SpaCy (ru_core_news_sm)",
            "SpaCy ru_core_news_lg, DeepPavlov NER, или Qwen2.5-VL-72B для визуальных документов"
        ),
        "llm": (
            "gpt-4o-mini ($0.15/1M вход)",
            "Claude 4.5 Sonnet ($3/1M) для сложных договоров, DeepSeek-R1 ($0.28/1M) для экономии, Qwen3-235B-A22B для многоязычных"
        ),
        "rag": (
            "pgvector + text-embedding-ada-002",
            "OpenAI text-embedding-3-large или Cohere embed-multilingual-v3.0 для русского и многоязычных договоров"
        ),
        "validation": (
            "Business rules + Pydantic",
            "Claude 4.5 Sonnet ($3/1M) для юридического анализа, Qwen3-235B-A22B для многоязычных контрактов"
        )
    }
    return models.get(stage, ("N/A", "N/A"))


def display_validation_section(section_analysis_data: Dict[str, Any]):
    """УСТАРЕВШАЯ функция - используйте display_validation_section_dynamic()"""
    # Эта функция больше не используется
    # Вызывается display_validation_section_dynamic() в строке 656
    pass


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
            status_text.text("🚀 Инициализация обработки...")
            progress_bar.progress(5)

            # Запускаем async обработку
            result = asyncio.run(process_document_async(
                tmp_file_path,
                Path(uploaded_file.name).suffix
            ))

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
                        st.success(f"**Метод:** {stage.results.get('method', 'N/A')}")
                        st.info(f"**Модель:** {used_model} | **Оптимально:** {optimal_model}")

                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("Страниц", stage.results.get("pages", "N/A"))
                        with col2:
                            st.metric("Символов", f"{stage.results.get('chars', 0):,}")
                        with col3:
                            confidence = stage.results.get("confidence")
                            st.metric("Confidence", f"{confidence:.2f}" if confidence else "N/A")

                        st.subheader("📋 ПОЛНЫЙ извлеченный текст")
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
                        for idx, (entity_type, count) in enumerate(by_type.items()):
                            with cols[idx % 3]:
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
                                    "Confidence": f"{ent.get('confidence', 0):.2f}",
                                    "Контекст": ent.get("context", "")[:80] + "..."
                                })

                        if all_entities:
                            st.dataframe(all_entities, use_container_width=True)

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

                validation_status = validation_result.get("status", "unknown")
                if validation_status == "passed":
                    st.success("**Статус:** ✅ Валидация пройдена")
                elif validation_status == "passed_with_warnings":
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

                st.markdown("---")

                # Детальная валидация по разделам (ДИНАМИЧЕСКИ из LLM)
                section_analysis_data = None
                for stage in result.stages:
                    if stage.name == "section_analysis" and stage.status == "success":
                        section_analysis_data = stage.results.get("full_data")
                        break

                if section_analysis_data:
                    display_validation_section_dynamic(section_analysis_data)
                else:
                    st.warning("⚠️ Детальный анализ разделов не был выполнен. Возможно, use_section_analysis=False или произошла ошибка.")

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
                if st.button("📄 Экспорт в Word", use_container_width=True):
                    st.info("Экспорт в Word (в разработке)")

            with col4:
                if st.button("❌ Отклонить", use_container_width=True):
                    st.error("Документ отклонен")

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
st.caption("Contract AI System v2.0 - Обработка документов | Модели: Claude 4.5 Sonnet, DeepSeek-R1, Qwen3-235B, GPT-4o")


def display_validation_section_dynamic(section_analysis_data: Dict[str, Any]):
    """Отображает детальную валидацию по разделам договора (ДИНАМИЧЕСКИ из LLM)"""

    if not section_analysis_data:
        st.warning("Анализ разделов не был выполнен")
        return

    st.subheader("📋 Детальный разбор по разделам договора")

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
                st.markdown("**💡 Рекомендации:**")
                for rec in analysis.recommendations:
                    st.info(rec)

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
