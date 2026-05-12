# -*- coding: utf-8 -*-
"""Пользователи Contract AI: регистрация, лимиты и базовое управление."""

import sys
from pathlib import Path
from datetime import datetime

import pandas as pd
import streamlit as st
from sqlalchemy import func

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

st.set_page_config(
    page_title="Пользователи — Contract AI",
    page_icon="👥",
    layout="wide",
)

from admin.shared.session_helpers import check_admin_auth, show_admin_sidebar_user
from admin.shared.ui_components import apply_custom_css, section_header
from src.models.database import SessionLocal, Contract
from src.models.auth_models import User
from src.services.quota_service import FREE_CONTRACTS_PER_MONTH, contracts_used_this_month

apply_custom_css()

if not check_admin_auth():
    st.stop()

with st.sidebar:
    st.markdown("## 👥 Пользователи")
    st.caption("Учет пользователей контрактной системы")
    st.markdown("---")
    show_admin_sidebar_user()

section_header("👥 Пользователи", "Регистрации, статусы, тарифы и месячные лимиты free/demo")


def _month_start() -> datetime:
    return datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _option_index(options: list[str], value: str) -> int:
    return options.index(value) if value in options else 0


def load_users():
    db = SessionLocal()
    try:
        users = db.query(User).order_by(User.created_at.desc()).all()
        rows = []
        for user in users:
            month_contracts = contracts_used_this_month(db, user.id)
            total_contracts = db.query(func.count(Contract.id)).filter(
                Contract.assigned_to == user.id,
                Contract.status != "deleted",
            ).scalar() or 0
            rows.append({
                "id": user.id,
                "email": user.email,
                "name": user.name,
                "role": user.role,
                "tier": user.subscription_tier,
                "active": bool(user.active),
                "verified": bool(user.email_verified),
                "month_contracts": month_contracts,
                "free_limit": FREE_CONTRACTS_PER_MONTH if user.subscription_tier == "demo" or user.role == "demo" else None,
                "total_contracts": total_contracts,
                "created_at": user.created_at.strftime("%Y-%m-%d %H:%M") if user.created_at else "",
                "last_login": user.last_login.strftime("%Y-%m-%d %H:%M") if user.last_login else "",
                "login_count": user.login_count or 0,
            })
        return rows
    finally:
        db.close()


def update_user(user_id: str, active: bool, role: str, tier: str):
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return False, "Пользователь не найден"
        user.active = active
        user.role = role
        user.subscription_tier = tier
        db.commit()
        return True, "Пользователь обновлен"
    except Exception as exc:
        db.rollback()
        return False, str(exc)
    finally:
        db.close()


rows = load_users()
df = pd.DataFrame(rows)

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Всего пользователей", len(rows))
with col2:
    st.metric("Активных", int(df["active"].sum()) if not df.empty else 0)
with col3:
    st.metric("Free/Demo", int(((df["tier"] == "demo") | (df["role"] == "demo")).sum()) if not df.empty else 0)
with col4:
    st.metric("Регистраций в месяце", int((pd.to_datetime(df["created_at"], errors="coerce") >= _month_start()).sum()) if not df.empty else 0)

st.markdown("---")

if df.empty:
    st.info("Пользователей пока нет.")
    st.stop()

search = st.text_input("Поиск по email или имени", placeholder="user@example.com")
tier_filter = st.multiselect("Тариф", sorted(df["tier"].dropna().unique().tolist()))
role_filter = st.multiselect("Роль", sorted(df["role"].dropna().unique().tolist()))

filtered = df.copy()
if search:
    needle = search.lower()
    filtered = filtered[
        filtered["email"].str.lower().str.contains(needle, na=False)
        | filtered["name"].str.lower().str.contains(needle, na=False)
    ]
if tier_filter:
    filtered = filtered[filtered["tier"].isin(tier_filter)]
if role_filter:
    filtered = filtered[filtered["role"].isin(role_filter)]

if filtered.empty:
    st.info("По выбранным фильтрам пользователей нет.")
    st.stop()

st.dataframe(
    filtered[[
        "email", "name", "role", "tier", "active", "verified",
        "month_contracts", "free_limit", "total_contracts",
        "created_at", "last_login", "login_count",
    ]],
    use_container_width=True,
    hide_index=True,
)

st.markdown("---")
st.subheader("Управление пользователем")

selected_email = st.selectbox("Пользователь", filtered["email"].tolist())
selected = next(row for row in rows if row["email"] == selected_email)
role_options = ["admin", "senior_lawyer", "lawyer", "junior_lawyer", "demo"]
tier_options = ["demo", "personal", "team", "business", "enterprise", "basic", "pro"]

col1, col2, col3 = st.columns(3)
with col1:
    active = st.checkbox("Активен", value=selected["active"])
with col2:
    role = st.selectbox(
        "Роль",
        role_options,
        index=_option_index(role_options, selected["role"]),
    )
with col3:
    tier = st.selectbox(
        "Тариф",
        tier_options,
        index=_option_index(tier_options, selected["tier"]),
    )

if st.button("Сохранить изменения", type="primary"):
    ok, message = update_user(selected["id"], active, role, tier)
    if ok:
        st.success(message)
        st.rerun()
    else:
        st.error(message)
