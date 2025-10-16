# -*- coding: utf-8 -*-
"""
Streamlit UI for Contract AI System
"""
import streamlit as st
import os
from datetime import datetime
from typing import Optional

# Configure page
st.set_page_config(
    page_title="Contract AI System",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Import settings first
from config.settings import settings

# Import auth utilities
from src.utils.auth import (
    init_session_state as init_auth_state,
    show_user_info,
    show_login_form,
    get_current_user,
    check_feature_access,
    show_upgrade_message,
    create_demo_users
)
from src.utils.contract_types import (
    get_all_contract_names,
    get_contract_type_code,
    get_contracts_by_category,
    get_all_categories
)
from src.utils.knowledge_base import (
    KnowledgeBaseManager,
    KnowledgeBaseCategory,
    initialize_knowledge_base
)

# Import improved pages
from app_pages_improved import page_generator_improved, page_knowledge_base

# Import agents and services
try:
    from src.agents import (
        OrchestratorAgent,
        OnboardingAgent,
        ContractGeneratorAgent,
        ContractAnalyzerAgent,
        DisagreementProcessorAgent,
        ChangesAnalyzerAgent,
        QuickExportAgent
    )
    from src.services.llm_gateway import LLMGateway
    from src.models import SessionLocal
    AGENTS_AVAILABLE = True
except ImportError as e:
    st.error(f"Ошибка импорта: {e}")
    AGENTS_AVAILABLE = False


def init_session_state():
    """Initialize session state"""
    # Initialize auth state
    init_auth_state()

    # Initialize page state
    if 'current_page' not in st.session_state:
        st.session_state.current_page = 'home'

    # Initialize services
    if 'llm_gateway' not in st.session_state and AGENTS_AVAILABLE:
        st.session_state.llm_gateway = LLMGateway()
    if 'db_session' not in st.session_state and AGENTS_AVAILABLE:
        st.session_state.db_session = SessionLocal()

    # Initialize knowledge base
    if 'kb_manager' not in st.session_state:
        st.session_state.kb_manager = initialize_knowledge_base()

    # Create demo users on first run
    if 'demo_users_created' not in st.session_state:
        create_demo_users()
        st.session_state.demo_users_created = True


def sidebar_navigation():
    """Sidebar navigation"""
    st.sidebar.title("📄 Contract AI System")
    st.sidebar.markdown("---")

    pages = {
        'home': '🏠 Главная',
        'onboarding': '📥 Обработка запросов',
        'generator': '✍️ Генератор договоров',
        'analyzer': '🔍 Анализ договоров',
        'disagreements': '⚖️ Возражения',
        'changes': '📊 Анализ изменений',
        'export': '📤 Экспорт',
        'knowledge_base': '📚 База знаний',
        'settings': '⚙️ Настройки'
    }

    for key, label in pages.items():
        if st.sidebar.button(label, key=f"nav_{key}"):
            st.session_state.current_page = key

    st.sidebar.markdown("---")

    # Show user info
    show_user_info()

    st.sidebar.markdown("---")
    st.sidebar.info(f"**Версия:** 1.0.0\n**LLM провайдер:** {settings.default_llm_provider}")


def page_home():
    """Home page"""
    st.title("🏠 Contract AI System")
    st.markdown("### Интеллектуальная система для автоматизации работы с договорами")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.info("**📥 Onboarding Agent**\n\nАнализ входящих запросов, классификация типов договоров, извлечение параметров")
    
    with col2:
        st.success("**✍️ Generator Agent**\n\nГенерация договоров по шаблонам XML с LLM-заполнением переменных")
    
    with col3:
        st.warning("**🔍 Analyzer Agent**\n\nАнализ договоров контрагентов, идентификация рисков, рекомендации")
    
    col4, col5, col6 = st.columns(3)
    
    with col4:
        st.error("**⚖️ Disagreement Agent**\n\nГенерация возражений с правовыми обоснованиями, экспорт в ЭДО")
    
    with col5:
        st.info("**📊 Changes Analyzer**\n\nСравнение версий договора, анализ влияния изменений")
    
    with col6:
        st.success("**📤 Quick Export**\n\nБыстрый экспорт в DOCX, PDF, TXT, JSON")
    
    st.markdown("---")
    st.markdown("**Статус системы:** ✅ Все агенты активны")


def page_onboarding():
    """Onboarding Agent page"""
    st.title("📥 Обработка входящих запросов")

    # Check access
    if not check_feature_access('can_use_onboarding'):
        show_upgrade_message('Обработка запросов')
        return

    user = get_current_user()
    user_id = user['id'] if user else 'demo_user'

    st.markdown("### Введите запрос пользователя")
    user_query = st.text_area(
        "Запрос",
        placeholder="Например: Нужен договор поставки товара на 500 000 рублей с ООО 'Поставщик'",
        height=150
    )
    
    if st.button("🚀 Обработать запрос", type="primary"):
        if not user_query:
            st.error("Введите запрос")
            return
        
        if not AGENTS_AVAILABLE:
            st.error("Агенты недоступны")
            return
        
        with st.spinner("Обработка запроса..."):
            try:
                agent = OnboardingAgent(
                    llm_gateway=st.session_state.llm_gateway,
                    db_session=st.session_state.db_session
                )
                
                result = agent.execute({
                    'user_query': user_query,
                    'user_id': user_id
                })
                
                if result.success:
                    st.success("✅ Запрос обработан")
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.subheader("Классификация")
                        st.write(f"**Тип:** {result.data.get('contract_type', 'N/A')}")
                        st.write(f"**Действие:** {result.data.get('intent', 'N/A')}")
                    
                    with col2:
                        st.subheader("Параметры")
                        params = result.data.get('extracted_params', {})
                        for key, value in params.items():
                            st.write(f"**{key}:** {value}")
                    
                    if result.next_action:
                        st.info(f"**Рекомендуемое действие:** {result.next_action}")
                else:
                    st.error(f"Ошибка: {result.error}")
            
            except Exception as e:
                st.error(f"Ошибка: {e}")


def page_generator():
    """Generator Agent page"""
    st.title("✍️ Генератор договоров")
    
    st.markdown("### Генерация договора по шаблону")
    
    col1, col2 = st.columns(2)
    
    with col1:
        template_id = st.text_input("ID шаблона", value="tpl_supply_001")
        contract_type = st.selectbox(
            "Тип договора",
            ["supply", "service", "lease", "purchase", "confidentiality"]
        )
    
    with col2:
        party_a = st.text_input("Сторона A", value="ООО 'Компания'")
        party_b = st.text_input("Сторона B", value="ООО 'Контрагент'")
    
    amount = st.number_input("Сумма (руб)", min_value=0, value=100000)
    user_id = st.text_input("ID пользователя", value="user_001", key="gen_user")
    
    if st.button("🚀 Сгенерировать договор", type="primary"):
        if not AGENTS_AVAILABLE:
            st.error("Агенты недоступны")
            return
        
        with st.spinner("Генерация договора..."):
            try:
                agent = ContractGeneratorAgent(
                    llm_gateway=st.session_state.llm_gateway,
                    db_session=st.session_state.db_session
                )
                
                result = agent.execute({
                    'template_id': template_id,
                    'contract_type': contract_type,
                    'params': {
                        'party_a': party_a,
                        'party_b': party_b,
                        'amount': amount
                    },
                    'user_id': user_id
                })
                
                if result.success:
                    st.success("✅ Договор сгенерирован")
                    st.write(f"**Contract ID:** {result.data.get('contract_id')}")
                    st.write(f"**Путь к файлу:** {result.data.get('file_path')}")
                    
                    if result.data.get('validation_passed'):
                        st.success("✅ Валидация пройдена")
                    else:
                        st.warning("⚠️ Есть предупреждения валидации")
                else:
                    st.error(f"Ошибка: {result.error}")
            
            except Exception as e:
                st.error(f"Ошибка: {e}")


def page_analyzer():
    """Analyzer Agent page"""
    st.title("🔍 Анализ договоров")

    # Check access
    if not check_feature_access('can_analyze_contracts'):
        show_upgrade_message('Анализ договоров')
        return

    user = get_current_user()
    user_id = user['id'] if user else 'demo_user'

    st.markdown("### Анализ договора контрагента")

    uploaded_file = st.file_uploader("Загрузите договор", type=['docx', 'pdf', 'xml'])

    counterparty_tin = st.text_input("ИНН контрагента", value="7700000000")
    
    if st.button("🚀 Анализировать", type="primary"):
        if not uploaded_file:
            st.error("Загрузите файл")
            return
        
        if not AGENTS_AVAILABLE:
            st.error("Агенты недоступны")
            return
        
        with st.spinner("Анализ договора..."):
            try:
                # Save uploaded file
                file_path = os.path.join("data/contracts", uploaded_file.name)
                os.makedirs(os.path.dirname(file_path), exist_ok=True)
                with open(file_path, 'wb') as f:
                    f.write(uploaded_file.getbuffer())
                
                agent = ContractAnalyzerAgent(
                    llm_gateway=st.session_state.llm_gateway,
                    db_session=st.session_state.db_session
                )
                
                result = agent.execute({
                    'contract_id': 'contract_' + datetime.now().strftime('%Y%m%d_%H%M%S'),
                    'file_path': file_path,
                    'counterparty_tin': counterparty_tin,
                    'user_id': user_id
                })
                
                if result.success:
                    st.success("✅ Анализ завершен")
                    
                    # Risk level
                    risk_level = result.data.get('risk_level', 'unknown')
                    if risk_level == 'high':
                        st.error(f"🔴 **Уровень риска:** {risk_level.upper()}")
                    elif risk_level == 'medium':
                        st.warning(f"🟡 **Уровень риска:** {risk_level.upper()}")
                    else:
                        st.success(f"🟢 **Уровень риска:** {risk_level.upper()}")
                    
                    # Risks
                    st.subheader("Выявленные риски")
                    risks = result.data.get('risks', [])
                    if risks:
                        for i, risk in enumerate(risks, 1):
                            with st.expander(f"{i}. {risk.get('category', 'N/A')} - {risk.get('severity', 'N/A')}"):
                                st.write(f"**Описание:** {risk.get('description', 'N/A')}")
                                st.write(f"**Раздел:** {risk.get('section_name', 'N/A')}")
                    else:
                        st.info("Риски не обнаружены")
                    
                    # Recommendations
                    st.subheader("Рекомендации")
                    recommendations = result.data.get('recommendations', [])
                    if recommendations:
                        for rec in recommendations:
                            st.write(f"- {rec.get('recommendation_text', 'N/A')}")
                    
                else:
                    st.error(f"Ошибка: {result.error}")
            
            except Exception as e:
                st.error(f"Ошибка: {e}")


def page_disagreements():
    """Disagreement Processor page"""
    st.title("⚖️ Генерация возражений")

    # Check access
    if not check_feature_access('can_generate_disagreements'):
        show_upgrade_message('Генерация возражений')
        return

    user = get_current_user()
    user_id = user['id'] if user else 'demo_user'

    st.markdown("### Создание документа с возражениями")

    contract_id = st.text_input("ID договора для анализа", value="contract_001")
    analysis_id = st.text_input("ID анализа", value="analysis_001")
    
    auto_prioritize = st.checkbox("Автоматическая приоритизация", value=True)
    
    if st.button("🚀 Генерировать возражения", type="primary"):
        if not AGENTS_AVAILABLE:
            st.error("Агенты недоступны")
            return
        
        with st.spinner("Генерация возражений..."):
            try:
                agent = DisagreementProcessorAgent(
                    llm_gateway=st.session_state.llm_gateway,
                    db_session=st.session_state.db_session
                )
                
                result = agent.execute({
                    'contract_id': contract_id,
                    'analysis_id': analysis_id,
                    'auto_prioritize': auto_prioritize,
                    'user_id': user_id
                })
                
                if result.success:
                    st.success("✅ Возражения сгенерированы")
                    st.write(f"**Disagreement ID:** {result.data.get('disagreement_id')}")
                    st.write(f"**Всего возражений:** {result.data.get('total_objections')}")
                    st.write(f"**Статус:** {result.data.get('status')}")
                    
                    # Show objections
                    st.subheader("Возражения")
                    objections = result.data.get('objections', [])
                    for obj in objections:
                        with st.expander(f"Возражение {obj.get('objection_number')} (Приоритет: {obj.get('priority')})"):
                            st.write(f"**Раздел:** {obj.get('section_reference')}")
                            st.write(f"**Текст:** {obj.get('objection_text')}")
                            st.write(f"**Обоснование:** {obj.get('legal_justification')}")
                else:
                    st.error(f"Ошибка: {result.error}")
            
            except Exception as e:
                st.error(f"Ошибка: {e}")


def page_changes():
    """Changes Analyzer page"""
    st.title("📊 Анализ изменений")

    # Check access
    if not check_feature_access('can_analyze_changes'):
        show_upgrade_message('Анализ изменений')
        return

    st.markdown("### Сравнение версий договора")

    col1, col2 = st.columns(2)

    with col1:
        from_version_id = st.number_input("От версии ID", min_value=1, value=1)

    with col2:
        to_version_id = st.number_input("До версии ID", min_value=1, value=2)

    contract_id = st.text_input("ID договора", value="contract_001", key="changes_contract")
    
    if st.button("🚀 Анализировать изменения", type="primary"):
        if not AGENTS_AVAILABLE:
            st.error("Агенты недоступны")
            return
        
        with st.spinner("Анализ изменений..."):
            try:
                agent = ChangesAnalyzerAgent(
                    llm_gateway=st.session_state.llm_gateway,
                    db_session=st.session_state.db_session
                )
                
                result = agent.execute({
                    'from_version_id': from_version_id,
                    'to_version_id': to_version_id,
                    'contract_id': contract_id
                })
                
                if result.success:
                    st.success("✅ Анализ изменений завершен")
                    
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        st.metric("Всего изменений", result.data.get('total_changes', 0))
                    
                    with col2:
                        assessment = result.data.get('overall_assessment', 'N/A')
                        st.metric("Общая оценка", assessment)
                    
                    with col3:
                        st.metric("Отчет", "Готов" if result.data.get('report_path') else "Нет")
                    
                    if result.data.get('report_path'):
                        st.download_button(
                            "📥 Скачать отчет",
                            data=open(result.data['report_path'], 'rb'),
                            file_name=os.path.basename(result.data['report_path'])
                        )
                else:
                    st.error(f"Ошибка: {result.error}")
            
            except Exception as e:
                st.error(f"Ошибка: {e}")


def page_export():
    """Quick Export page"""
    st.title("📤 Быстрый экспорт")

    # Check access
    user = get_current_user()
    user_id = user['id'] if user else 'demo_user'

    st.markdown("### Экспорт договора")

    contract_id = st.text_input("ID договора", value="contract_001", key="export_contract")

    col1, col2 = st.columns(2)

    with col1:
        export_format = st.selectbox(
            "Формат экспорта",
            ["docx", "pdf", "txt", "json", "xml", "all"]
        )

    with col2:
        include_analysis = st.checkbox("Включить результаты анализа", value=False)

    # Check PDF export permission
    if export_format in ['pdf', 'all']:
        if not check_feature_access('can_export_pdf'):
            st.warning("⚠️ Экспорт в PDF доступен только в полной версии")
            if export_format == 'pdf':
                show_upgrade_message('Экспорт в PDF')
                return
    
    if st.button("🚀 Экспортировать", type="primary"):
        if not AGENTS_AVAILABLE:
            st.error("Агенты недоступны")
            return
        
        with st.spinner("Экспорт..."):
            try:
                agent = QuickExportAgent(
                    llm_gateway=st.session_state.llm_gateway,
                    db_session=st.session_state.db_session
                )
                
                result = agent.execute({
                    'contract_id': contract_id,
                    'export_format': export_format,
                    'include_analysis': include_analysis,
                    'user_id': user_id
                })
                
                if result.success:
                    st.success("✅ Экспорт завершен")
                    
                    file_paths = result.data.get('file_paths', {})
                    for fmt, path in file_paths.items():
                        if path and os.path.exists(path):
                            st.write(f"**{fmt.upper()}:** {path}")
                            with open(path, 'rb') as f:
                                st.download_button(
                                    f"📥 Скачать {fmt.upper()}",
                                    data=f,
                                    file_name=os.path.basename(path),
                                    key=f"download_{fmt}"
                                )
                else:
                    st.error(f"Ошибка: {result.error}")
            
            except Exception as e:
                st.error(f"Ошибка: {e}")


def page_login():
    """Login page"""
    st.title("🔐 Вход в систему")
    show_login_form()


def page_settings():
    """Settings page"""
    st.title("⚙️ Настройки")

    st.markdown("### Конфигурация системы")

    st.subheader("LLM Provider")
    provider = st.selectbox(
        "Провайдер",
        ["openai", "anthropic", "yandex", "gigachat"],
        index=0
    )

    api_key = st.text_input("API Key", type="password", value="")

    st.subheader("База данных")
    db_url = st.text_input("Database URL", value=settings.database_url)

    st.subheader("RAG System")
    chroma_path = st.text_input("ChromaDB Path", value=settings.chroma_persist_directory)

    if st.button("💾 Сохранить настройки"):
        st.success("Настройки сохранены (функциональность в разработке)")


def main():
    """Main application"""
    init_session_state()
    sidebar_navigation()

    # Route to page
    page = st.session_state.current_page

    if page == 'login':
        page_login()
    elif page == 'home':
        page_home()
    elif page == 'onboarding':
        page_onboarding()
    elif page == 'generator':
        page_generator_improved()  # Use improved version
    elif page == 'analyzer':
        page_analyzer()
    elif page == 'disagreements':
        page_disagreements()
    elif page == 'changes':
        page_changes()
    elif page == 'export':
        page_export()
    elif page == 'knowledge_base':
        page_knowledge_base()  # Add knowledge base page
    elif page == 'settings':
        page_settings()


if __name__ == "__main__":
    main()
