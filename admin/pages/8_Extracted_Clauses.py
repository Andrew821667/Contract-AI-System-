# -*- coding: utf-8 -*-
"""
Извлечённые клаузулы — просмотр и фильтрация пунктов из проанализированных договоров
Внутренний инструмент для администраторов
"""
import streamlit as st
import sys
import json
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

env_path = project_root / ".env"
if env_path.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(env_path)
    except ImportError:
        pass

st.set_page_config(
    page_title="Извлечённые клаузулы — Contract AI",
    page_icon="📑",
    layout="wide"
)

from admin.shared.session_helpers import check_admin_auth, show_admin_sidebar_user
if not check_admin_auth():
    st.stop()

from admin.shared.ui_components import apply_custom_css, section_header
apply_custom_css()

# ─── Sidebar ─────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 📑 Извлечённые клаузулы")
    st.caption("Пункты из проанализированных договоров")
    st.markdown("---")
    show_admin_sidebar_user()

# ─── Constants ────────────────────────────────────────────────
CLAUSE_TYPES = {
    'financial': 'Финансовые',
    'temporal': 'Временные',
    'liability': 'Ответственность',
    'termination': 'Расторжение',
    'confidentiality': 'Конфиденциальность',
    'dispute_resolution': 'Разрешение споров',
    'force_majeure': 'Форс-мажор',
    'warranties': 'Гарантии',
    'intellectual_property': 'Интел. собственность',
    'definitions': 'Определения',
    'general': 'Общие',
}

RISK_COLORS = {
    'critical': '#ef4444',
    'high': '#f97316',
    'medium': '#eab308',
    'low': '#22c55e',
    'none': '#9ca3af',
}

RISK_LABELS = {
    'critical': 'Критический',
    'high': 'Высокий',
    'medium': 'Средний',
    'low': 'Низкий',
    'none': 'Нет',
}


def get_db():
    try:
        from src.models.database import SessionLocal
        return SessionLocal()
    except Exception as e:
        st.error(f"Ошибка подключения к БД: {e}")
        return None


# ─── Main Content ─────────────────────────────────────────────
section_header("📑 Извлечённые клаузулы", "Пункты из проанализированных договоров — внутренний инструмент")

db = get_db()
if not db:
    st.stop()

try:
    from src.models.clause_models import ExtractedClause
    from src.models.database import Contract
    from sqlalchemy import func

    # ─── Filters ─────────────────────────────────────────────
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        # Get list of contracts with clauses
        contract_ids = db.query(ExtractedClause.contract_id).distinct().all()
        contract_ids = [c[0] for c in contract_ids]
        contract_options = ["Все договоры"] + contract_ids
        selected_contract = st.selectbox("Договор", contract_options)

    with col2:
        type_options = ["Все типы"] + list(CLAUSE_TYPES.keys())
        selected_type = st.selectbox(
            "Тип клаузулы",
            type_options,
            format_func=lambda x: "Все типы" if x == "Все типы" else CLAUSE_TYPES.get(x, x)
        )

    with col3:
        risk_options = ["Все уровни", "critical", "high", "medium", "low", "none"]
        selected_risk = st.selectbox(
            "Уровень риска",
            risk_options,
            format_func=lambda x: "Все уровни" if x == "Все уровни" else RISK_LABELS.get(x, x)
        )

    with col4:
        search_text = st.text_input("Поиск по тексту", placeholder="Введите текст...")

    st.markdown("---")

    # ─── Query ───────────────────────────────────────────────
    query = db.query(ExtractedClause)

    if selected_contract != "Все договоры":
        query = query.filter(ExtractedClause.contract_id == selected_contract)
    if selected_type != "Все типы":
        query = query.filter(ExtractedClause.clause_type == selected_type)
    if selected_risk != "Все уровни":
        query = query.filter(ExtractedClause.risk_level == selected_risk)
    if search_text:
        query = query.filter(ExtractedClause.text.ilike(f"%{search_text}%"))

    total = query.count()
    clauses = query.order_by(
        ExtractedClause.contract_id,
        ExtractedClause.clause_number
    ).limit(100).all()

    # ─── Stats ───────────────────────────────────────────────
    total_all = db.query(ExtractedClause).count()
    contracts_count = db.query(ExtractedClause.contract_id).distinct().count()

    type_stats = dict(
        db.query(ExtractedClause.clause_type, func.count(ExtractedClause.id))
        .group_by(ExtractedClause.clause_type).all()
    )
    risk_stats = dict(
        db.query(ExtractedClause.risk_level, func.count(ExtractedClause.id))
        .group_by(ExtractedClause.risk_level).all()
    )

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Всего клаузул", total_all)
    with col2:
        st.metric("Договоров", contracts_count)
    with col3:
        st.metric("Типов", len(type_stats))
    with col4:
        st.metric("Показано", f"{len(clauses)}/{total}")

    st.markdown("---")

    # ─── Type distribution ───────────────────────────────────
    if type_stats:
        st.markdown("#### Распределение по типам")
        cols = st.columns(min(len(type_stats), 6))
        for i, (t, count) in enumerate(sorted(type_stats.items(), key=lambda x: -x[1])):
            with cols[i % len(cols)]:
                label = CLAUSE_TYPES.get(t, t)
                st.metric(label, count)

    st.markdown("---")

    # ─── Clauses list ────────────────────────────────────────
    st.markdown(f"#### Клаузулы ({len(clauses)} из {total})")

    if not clauses:
        st.info("Нет клаузул по заданным фильтрам. Клаузулы появляются после анализа договоров.")
    else:
        for clause in clauses:
            risk_color = RISK_COLORS.get(clause.risk_level, '#9ca3af')
            risk_label = RISK_LABELS.get(clause.risk_level, clause.risk_level or 'Нет')
            type_label = CLAUSE_TYPES.get(clause.clause_type, clause.clause_type)

            with st.expander(
                f"**#{clause.clause_number}** [{type_label}] {clause.title[:80]} — "
                f"Риск: {risk_label}"
            ):
                col1, col2 = st.columns([3, 1])

                with col1:
                    st.markdown(f"**Заголовок:** {clause.title}")
                    st.markdown(f"**Тип:** {type_label}")
                    st.text_area(
                        "Текст клаузулы",
                        value=clause.text,
                        height=120,
                        disabled=True,
                        key=f"text_{clause.id}",
                    )

                with col2:
                    st.markdown(
                        f'<div style="background:{risk_color}; color:white; '
                        f'padding:8px 16px; border-radius:8px; text-align:center; '
                        f'font-weight:bold; margin-bottom:8px;">{risk_label}</div>',
                        unsafe_allow_html=True
                    )
                    if clause.severity_score is not None:
                        st.metric("Серьёзность", f"{clause.severity_score * 100:.0f}%")
                    st.caption(f"ID: {clause.id[:12]}...")
                    st.caption(f"Договор: {clause.contract_id[:12]}...")

                # Analysis JSON
                if clause.analysis_json:
                    try:
                        analysis = json.loads(clause.analysis_json)
                        st.markdown("**Анализ LLM:**")

                        if analysis.get('risks'):
                            for risk in analysis['risks']:
                                st.markdown(
                                    f"- **{risk.get('title', '')}** ({risk.get('severity', '')}): "
                                    f"{risk.get('description', '')}"
                                )

                        if analysis.get('recommendations'):
                            st.markdown("**Рекомендации:**")
                            for rec in analysis['recommendations']:
                                st.markdown(f"- {rec.get('title', '')}: {rec.get('description', '')}")
                    except (json.JSONDecodeError, TypeError):
                        pass

                # Tags
                if clause.tags:
                    try:
                        tags = json.loads(clause.tags) if isinstance(clause.tags, str) else clause.tags
                        if tags:
                            st.markdown("**Теги:** " + ", ".join(f"`{t}`" for t in tags))
                    except (json.JSONDecodeError, TypeError):
                        pass

finally:
    if db:
        db.close()

st.markdown("---")
st.caption("Contract AI v3.0 | Извлечённые клаузулы | Внутренний инструмент")
