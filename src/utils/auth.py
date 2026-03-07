# -*- coding: utf-8 -*-
"""
Authentication and User Management System
"""
import os
import streamlit as st
from enum import Enum
from typing import Optional, Dict, Any
from datetime import datetime
from src.models import SessionLocal, User


class UserRole(Enum):
    """Роли пользователей"""
    DEMO = "demo"
    FULL = "full"
    VIP = "vip"
    ADMIN = "admin"


class UserPermissions:
    """Права доступа для различных ролей"""

    ROLE_PERMISSIONS = {
        UserRole.DEMO: {
            "contracts_per_day": 3,
            "max_file_size_mb": 5,
            "can_export_pdf": False,
            "can_export_docx": True,
            "can_export_xml": False,
            "can_use_rag": False,
            "can_generate_contracts": True,
            "can_analyze_contracts": True,
            "can_use_onboarding": False,
            "can_use_disagreements": False,
            "can_use_changes_analyzer": False,
            "llm_requests_per_day": 10,
        },
        UserRole.FULL: {
            "contracts_per_day": 50,
            "max_file_size_mb": 20,
            "can_export_pdf": True,
            "can_export_docx": True,
            "can_export_xml": True,
            "can_use_rag": True,
            "can_generate_contracts": True,
            "can_analyze_contracts": True,
            "can_use_onboarding": True,
            "can_use_disagreements": True,
            "can_use_changes_analyzer": True,
            "llm_requests_per_day": 100,
        },
        UserRole.VIP: {
            "contracts_per_day": 1000,
            "max_file_size_mb": 100,
            "can_export_pdf": True,
            "can_export_docx": True,
            "can_export_xml": True,
            "can_use_rag": True,
            "can_generate_contracts": True,
            "can_analyze_contracts": True,
            "can_use_onboarding": True,
            "can_use_disagreements": True,
            "can_use_changes_analyzer": True,
            "llm_requests_per_day": 1000,
            "priority_support": True,
        },
        UserRole.ADMIN: {
            "contracts_per_day": float('inf'),
            "max_file_size_mb": float('inf'),
            "can_export_pdf": True,
            "can_export_docx": True,
            "can_export_xml": True,
            "can_use_rag": True,
            "can_generate_contracts": True,
            "can_analyze_contracts": True,
            "can_use_onboarding": True,
            "can_use_disagreements": True,
            "can_use_changes_analyzer": True,
            "llm_requests_per_day": float('inf'),
            "can_manage_users": True,
            "can_manage_templates": True,
            "can_view_logs": True,
            "priority_support": True,
        }
    }

    @classmethod
    def get_permissions(cls, role: UserRole) -> Dict[str, Any]:
        """Получить права для роли"""
        return cls.ROLE_PERMISSIONS.get(role, cls.ROLE_PERMISSIONS[UserRole.DEMO])

    @classmethod
    def check_permission(cls, role: UserRole, permission: str) -> bool:
        """Проверить наличие права"""
        perms = cls.get_permissions(role)
        return perms.get(permission, False)


def init_session_state():
    """Инициализация состояния сессии"""
    if 'user' not in st.session_state:
        st.session_state.user = None
    if 'role' not in st.session_state:
        st.session_state.role = UserRole.DEMO
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False


def login_user(email: str, password: str = None) -> Optional[Dict[str, Any]]:
    """Вход пользователя с проверкой пароля"""
    from src.services.auth_service import AuthService

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email, User.active == True).first()

        if not user:
            return None

        # Проверяем пароль если он задан и у пользователя есть хэш
        if password and user.password_hash:
            if not AuthService.verify_password(password, user.password_hash):
                return None
        elif user.password_hash and not password:
            # У пользователя есть пароль, но он не введён — не пускаем
            return None

        # Определяем роль на основе поля role в БД
        role_map = {
            'admin': UserRole.ADMIN,
            'senior_lawyer': UserRole.VIP,
            'lawyer': UserRole.FULL,
            'junior_lawyer': UserRole.DEMO,
        }
        role = role_map.get(user.role, UserRole.DEMO)

        st.session_state.user = {
            'id': user.id,
            'email': user.email,
            'name': user.name,
            'role': user.role
        }
        st.session_state.role = role
        st.session_state.authenticated = True

        # Обновляем last_login
        user.last_login = datetime.utcnow()
        user.login_count = (user.login_count or 0) + 1
        db.commit()

        return st.session_state.user

    finally:
        db.close()


def logout_user():
    """Выход пользователя"""
    st.session_state.user = None
    st.session_state.role = UserRole.DEMO
    st.session_state.authenticated = False


def get_current_user() -> Optional[Dict[str, Any]]:
    """Получить текущего пользователя"""
    return st.session_state.get('user')


def get_current_role() -> UserRole:
    """Получить текущую роль"""
    return st.session_state.get('role', UserRole.DEMO)


def require_auth(role: Optional[UserRole] = None):
    """
    Декоратор для проверки аутентификации
    Если role указана, проверяет минимальную требуемую роль
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            if not st.session_state.get('authenticated', False):
                st.warning("⚠️ Требуется авторизация")
                show_login_form()
                return None

            if role:
                current_role = get_current_role()
                role_hierarchy = [UserRole.DEMO, UserRole.FULL, UserRole.VIP, UserRole.ADMIN]

                if role_hierarchy.index(current_role) < role_hierarchy.index(role):
                    st.error(f"❌ Недостаточно прав. Требуется роль: {role.value}")
                    return None

            return func(*args, **kwargs)
        return wrapper
    return decorator


def show_login_form():
    """Показать форму входа"""
    st.markdown("### 🔐 Вход в систему")

    with st.form("login_form"):
        email = st.text_input("Email", placeholder="admin@contractai.ru")
        password = st.text_input("Пароль", type="password", placeholder="••••••••")
        submit = st.form_submit_button("Войти", use_container_width=True)

        if submit:
            if email and password:
                user = login_user(email, password)
                if user:
                    st.success(f"✅ Добро пожаловать, {user['name']}!")
                    st.rerun()
                else:
                    st.error("❌ Неверный email или пароль")
            else:
                st.error("❌ Введите email и пароль")

    st.markdown("---")

    with st.expander("📋 Учётные записи для входа"):
        st.markdown("""
        | Email | Роль | Тариф |
        |-------|------|-------|
        | `admin@contractai.ru` | Администратор | enterprise |
        | `lawyer@contractai.ru` | Юрист | pro |
        | `vip@contractai.ru` | VIP | enterprise |
        | `demo@contractai.ru` | Демо | demo |

        *Пароли задаются администратором при развёртывании системы.*
        """)


def show_user_info():
    """Показать информацию о пользователе в сайдбаре"""
    if st.session_state.get('authenticated', False):
        user = get_current_user()
        role = get_current_role()
        perms = UserPermissions.get_permissions(role)

        st.sidebar.markdown("---")
        st.sidebar.markdown(f"### 👤 {user['name']}")

        # Показать роль с цветным индикатором
        role_colors = {
            UserRole.DEMO: "🔵",
            UserRole.FULL: "🟢",
            UserRole.VIP: "🟡",
            UserRole.ADMIN: "🔴"
        }
        role_indicator = role_colors.get(role, "⚪")
        st.sidebar.markdown(f"**Роль:** {role_indicator} {role.value.upper()}")

        # Показать лимиты
        with st.sidebar.expander("📊 Лимиты и возможности"):
            contracts_limit = perms['contracts_per_day']
            if contracts_limit == float('inf'):
                st.write("**Договоров/день:** ♾️ Безлимит")
            else:
                st.write(f"**Договоров/день:** {contracts_limit}")

            llm_limit = perms['llm_requests_per_day']
            if llm_limit == float('inf'):
                st.write("**LLM запросов/день:** ♾️ Безлимит")
            else:
                st.write(f"**LLM запросов/день:** {llm_limit}")

            file_size = perms['max_file_size_mb']
            if file_size == float('inf'):
                st.write("**Макс. размер файла:** ♾️ Безлимит")
            else:
                st.write(f"**Макс. размер файла:** {file_size} MB")

            st.write("---")
            st.write("**Доступные функции:**")
            if perms.get('can_export_pdf'):
                st.write("✅ Экспорт в PDF")
            if perms.get('can_export_xml'):
                st.write("✅ Экспорт в XML")
            if perms.get('can_use_rag'):
                st.write("✅ RAG поиск")
            if perms.get('priority_support'):
                st.write("⭐ Приоритетная поддержка")

        col1, col2 = st.sidebar.columns(2)
        with col1:
            if st.button("🔄 Сменить", use_container_width=True):
                logout_user()
                st.session_state.current_page = 'login'
                st.rerun()
        with col2:
            if st.button("🚪 Выйти", use_container_width=True):
                logout_user()
                st.rerun()
    else:
        st.sidebar.markdown("---")
        st.sidebar.warning("⚠️ Демо-режим\n\nОграниченный функционал")
        if st.sidebar.button("🔐 Войти", use_container_width=True):
            st.session_state.current_page = 'login'
            st.rerun()


def check_feature_access(feature: str) -> bool:
    """Проверить доступ к функции"""
    role = get_current_role()
    return UserPermissions.check_permission(role, feature)


def show_upgrade_message(feature: str):
    """Показать сообщение об улучшении тарифа"""
    st.warning(f"""
    ⚠️ **Функция "{feature}" недоступна в вашем тарифе**

    Обновите тариф для доступа к расширенным возможностям:
    - **FULL** - полный функционал
    - **VIP** - приоритетная поддержка и безлимитный доступ
    """)


# Создание пользователей при первом запуске
def create_demo_users():
    """Создать начальных пользователей если их нет"""
    from src.services.auth_service import AuthService

    db = SessionLocal()
    try:
        seed_users = [
            {"email": "admin@contractai.ru", "name": "Администратор", "password_env": "SEED_ADMIN_PASSWORD", "role": "admin", "subscription_tier": "enterprise"},
            {"email": "lawyer@contractai.ru", "name": "Юрист Иванов", "password_env": "SEED_LAWYER_PASSWORD", "role": "lawyer", "subscription_tier": "pro"},
            {"email": "vip@contractai.ru", "name": "VIP Клиент", "password_env": "SEED_VIP_PASSWORD", "role": "senior_lawyer", "subscription_tier": "enterprise"},
            {"email": "demo@contractai.ru", "name": "Демо Пользователь", "password_env": "SEED_DEMO_PASSWORD", "role": "junior_lawyer", "subscription_tier": "demo"},
        ]

        for u in seed_users:
            existing = db.query(User).filter(User.email == u["email"]).first()
            if not existing:
                password = os.environ.get(u["password_env"], "")
                if not password:
                    continue
                user = User(
                    email=u["email"],
                    name=u["name"],
                    password_hash=AuthService.hash_password(password),
                    role=u["role"],
                    subscription_tier=u.get("subscription_tier", "basic"),
                    active=True,
                    email_verified=True,
                    is_demo=(u.get("subscription_tier") == "demo"),
                )
                db.add(user)

        db.commit()
    except Exception as e:
        print(f"Error creating seed users: {e}")
        db.rollback()
    finally:
        db.close()
