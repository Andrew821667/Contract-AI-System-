"""
Admin Panel for Contract-AI-System

Features:
- User management (create, edit, change roles)
- Demo link generation with QR codes
- System analytics
- Audit log viewer
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta, timezone
import qrcode
from io import BytesIO
import base64

from src.models import get_db, User, DemoToken, AuditLog
from src.services.auth_service import AuthService
from src.utils.auth import get_current_user, get_current_role, check_feature_access


def show_admin_panel():
    """Main admin panel interface"""

    st.title("🔐 Админ-Панель")

    # Check admin access
    if not check_feature_access('can_manage_users'):
        st.error("❌ Доступ запрещен. Требуется роль ADMIN.")
        st.info("Войдите с правами администратора для доступа к панели управления.")
        return

    current_user = get_current_user()

    # Header with user info
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown(f"**Администратор:** {current_user['name']} ({current_user['email']})")
    with col2:
        if st.button("🔄 Обновить", use_container_width=True):
            st.rerun()

    st.markdown("---")

    # Main tabs
    tabs = st.tabs([
        "👥 Пользователи",
        "🔗 Демо-Ссылки",
        "📊 Аналитика",
        "📋 Аудит Логи"
    ])

    # Get database session
    db = next(get_db())
    auth_service = AuthService(db)

    # ====================TAB 1: User Management ====================
    with tabs[0]:
        show_user_management_tab(auth_service, current_user, db)

    # ==================== TAB 2: Demo Links ====================
    with tabs[1]:
        show_demo_links_tab(auth_service, current_user, db)

    # ==================== TAB 3: Analytics ====================
    with tabs[2]:
        show_analytics_tab(auth_service, db)

    # ==================== TAB 4: Audit Logs ====================
    with tabs[3]:
        show_audit_logs_tab(db)


def show_user_management_tab(auth_service: AuthService, current_user: dict, db):
    """User management tab"""

    st.header("Управление Пользователями")

    # Filters
    col1, col2, col3 = st.columns(3)
    with col1:
        role_filter = st.selectbox(
            "Роль",
            ["Все", "admin", "senior_lawyer", "lawyer", "junior_lawyer", "demo"]
        )
    with col2:
        demo_filter = st.selectbox("Тип", ["Все", "Обычные", "Demo"])
    with col3:
        search = st.text_input("🔍 Поиск", placeholder="Email или имя")

    # Get users
    is_demo = None if demo_filter == "Все" else (demo_filter == "Demo")

    users_data = auth_service.list_users(
        page=1,
        limit=100,
        role=None if role_filter == "Все" else role_filter,
        search=search if search else None,
        is_demo=is_demo
    )

    # Display stats
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Всего пользователей", users_data['total'])
    with col2:
        active_count = sum(1 for u in users_data['users'] if u['active'])
        st.metric("Активных", active_count)
    with col3:
        demo_count = sum(1 for u in users_data['users'] if u['is_demo'])
        st.metric("Demo", demo_count)
    with col4:
        verified_count = sum(1 for u in users_data['users'] if u['email_verified'])
        st.metric("Подтверждено", verified_count)

    st.markdown("---")

    # Users table
    if users_data['users']:
        df = pd.DataFrame(users_data['users'])

        # Format datetime columns
        if 'created_at' in df.columns:
            df['created_at'] = pd.to_datetime(df['created_at']).dt.strftime('%Y-%m-%d %H:%M')
        if 'last_login' in df.columns:
            df['last_login'] = pd.to_datetime(df['last_login'], errors='coerce').dt.strftime('%Y-%m-%d %H:%M')

        # Display dataframe
        st.dataframe(
            df[['email', 'name', 'role', 'subscription_tier', 'active', 'is_demo', 'created_at', 'last_login']],
            column_config={
                "email": st.column_config.TextColumn("Email", width="medium"),
                "name": st.column_config.TextColumn("Имя", width="medium"),
                "role": st.column_config.TextColumn("Роль", width="small"),
                "subscription_tier": st.column_config.TextColumn("Тариф", width="small"),
                "active": st.column_config.CheckboxColumn("Активен", width="small"),
                "is_demo": st.column_config.CheckboxColumn("Demo", width="small"),
                "created_at": st.column_config.TextColumn("Создан", width="medium"),
                "last_login": st.column_config.TextColumn("Последний вход", width="medium")
            },
            use_container_width=True,
            height=400
        )
    else:
        st.info("Пользователи не найдены")

    st.markdown("---")

    # Actions
    st.subheader("Действия")

    col1, col2 = st.columns(2)

    # Create user
    with col1:
        st.markdown("#### ➕ Создать Пользователя")
        with st.form("create_user_form"):
            new_email = st.text_input("Email*", placeholder="user@example.com")
            new_name = st.text_input("Имя*", placeholder="Иван Иванов")
            new_role = st.selectbox(
                "Роль*",
                ["junior_lawyer", "lawyer", "senior_lawyer", "admin"]
            )
            new_tier = st.selectbox(
                "Тариф*",
                ["demo", "basic", "pro", "enterprise"]
            )

            if st.form_submit_button("Создать пользователя", use_container_width=True):
                if new_email and new_name:
                    user, temp_password, error = auth_service.create_user_as_admin(
                        email=new_email,
                        name=new_name,
                        role=new_role,
                        subscription_tier=new_tier,
                        admin_user_id=current_user['id']
                    )

                    if error:
                        st.error(f"❌ Ошибка: {error}")
                    else:
                        st.success(f"✅ Пользователь создан!")
                        st.code(f"Временный пароль: {temp_password}", language=None)
                        st.info("💡 Отправьте временный пароль пользователю. Он должен будет изменить его при первом входе.")
                        st.rerun()
                else:
                    st.error("❌ Заполните все обязательные поля")

    # Change role
    with col2:
        st.markdown("#### ✏️ Изменить Роль")
        with st.form("change_role_form"):
            if users_data['users']:
                user_options = {u['email']: u['id'] for u in users_data['users']}
                selected_email = st.selectbox("Пользователь*", list(user_options.keys()))
                selected_user_id = user_options[selected_email]

                new_role = st.selectbox(
                    "Новая роль*",
                    ["junior_lawyer", "lawyer", "senior_lawyer", "admin"],
                    key="role_change_select"
                )
                new_tier = st.selectbox(
                    "Новый тариф",
                    [None, "demo", "basic", "pro", "enterprise"],
                    key="tier_change_select"
                )

                if st.form_submit_button("Изменить роль", use_container_width=True):
                    success, error = auth_service.update_user_role(
                        user_id=selected_user_id,
                        new_role=new_role,
                        admin_user_id=current_user['id'],
                        subscription_tier=new_tier if new_tier else None
                    )

                    if error:
                        st.error(f"❌ Ошибка: {error}")
                    else:
                        st.success(f"✅ Роль изменена на {new_role}")
                        st.rerun()
            else:
                st.info("Нет пользователей для изменения")


def show_demo_links_tab(auth_service: AuthService, current_user: dict, db):
    """Demo links management tab"""

    st.header("Генерация Демо-Ссылок")

    st.info("""
    💡 **Демо-ссылки** позволяют предоставить временный доступ к системе.

    **Как это работает:**
    1. Админ генерирует ссылку с настройками (кол-во контрактов, время действия)
    2. Ссылка публикуется на сайте или в рекламных материалах
    3. Пользователь переходит по ссылке → вводит email → получает DEMO доступ автоматически
    """)

    st.markdown("---")

    col1, col2 = st.columns(2)

    # Generate demo link
    with col1:
        st.markdown("### 🔗 Создать Демо-Ссылку")

        with st.form("generate_demo_form"):
            campaign = st.text_input(
                "Кампания (UTM)",
                placeholder="website_header_cta",
                help="Для отслеживания эффективности"
            )
            max_contracts = st.number_input(
                "Макс. контрактов",
                min_value=1,
                max_value=10,
                value=3,
                help="Сколько контрактов может проанализировать demo-пользователь"
            )
            max_llm = st.number_input(
                "Макс. LLM запросов",
                min_value=1,
                max_value=100,
                value=10,
                help="Лимит на AI запросы"
            )
            expires_hours = st.number_input(
                "Действует (часов)",
                min_value=1,
                max_value=168,
                value=24,
                help="Время действия demo-доступа"
            )

            if st.form_submit_button("🔗 Сгенерировать Ссылку", use_container_width=True):
                demo_token = auth_service.generate_demo_token(
                    created_by_user_id=current_user['id'],
                    max_contracts=max_contracts,
                    max_llm_requests=max_llm,
                    expires_in_hours=expires_hours,
                    campaign=campaign if campaign else None,
                    source="admin_panel"
                )

                demo_url = f"https://contract-ai.example.com/demo?token={demo_token.token}"

                st.success("✅ Демо-ссылка создана!")

                # Display URL
                st.code(demo_url, language=None)

                # QR Code
                qr = qrcode.QRCode(version=1, box_size=10, border=4)
                qr.add_data(demo_url)
                qr.make(fit=True)
                img = qr.make_image(fill_color="black", back_color="white")

                # Convert to bytes
                buf = BytesIO()
                img.save(buf, format='PNG')
                buf.seek(0)

                st.image(buf, caption="QR код для демо-ссылки", width=200)

                # Download QR code
                st.download_button(
                    label="📥 Скачать QR код",
                    data=buf.getvalue(),
                    file_name=f"demo_qr_{demo_token.token[:10]}.png",
                    mime="image/png",
                    use_container_width=True
                )

                # Details
                with st.expander("📋 Детали"):
                    st.write(f"**Token:** {demo_token.token}")
                    st.write(f"**Истекает:** {demo_token.expires_at.strftime('%Y-%m-%d %H:%M')}")
                    st.write(f"**Макс. контрактов:** {max_contracts}")
                    st.write(f"**Макс. LLM запросов:** {max_llm}")

    # Active demo tokens
    with col2:
        st.markdown("### 📊 Активные Токены")

        # Get active tokens
        active_tokens = db.query(DemoToken).filter(
            DemoToken.expires_at > datetime.now(timezone.utc)
        ).order_by(DemoToken.created_at.desc()).limit(10).all()

        if active_tokens:
            for token in active_tokens:
                with st.expander(f"Token: {token.token[:20]}... {'✅ Использован' if token.used else '⏳ Ожидает'}"):
                    st.write(f"**Кампания:** {token.campaign or 'N/A'}")
                    st.write(f"**Использован:** {'Да' if token.used else 'Нет'}")
                    if token.used:
                        st.write(f"**Использовано:** {token.used_at.strftime('%Y-%m-%d %H:%M')}")
                        user = db.query(User).filter(User.id == token.used_by_user_id).first()
                        if user:
                            st.write(f"**Пользователь:** {user.email}")
                    st.write(f"**Истекает:** {token.expires_at.strftime('%Y-%m-%d %H:%M')}")
                    st.write(f"**Макс. контрактов:** {token.max_contracts}")

                    # Revoke button
                    if not token.used and st.button("🚫 Отозвать токен", key=f"revoke_{token.id}", type="secondary"):
                        token.expires_at = datetime.now(timezone.utc)
                        db.commit()
                        st.success("✅ Токен успешно отозван")
                        st.rerun()
        else:
            st.info("Нет активных токенов")


def show_analytics_tab(auth_service: AuthService, db):
    """Analytics tab"""

    st.header("Аналитика Системы")

    # Get analytics
    analytics = auth_service.get_analytics()

    # Overview metrics
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            "Всего пользователей",
            analytics['total_users'],
            delta="+12 за неделю" if analytics['total_users'] > 0 else None
        )
    with col2:
        st.metric(
            "Активных",
            analytics['active_users'],
            delta=f"{int((analytics['active_users']/analytics['total_users']*100) if analytics['total_users'] > 0 else 0)}%"
        )
    with col3:
        st.metric(
            "Demo пользователей",
            analytics['demo_users']
        )
    with col4:
        st.metric(
            "Активных за неделю",
            analytics['active_last_week']
        )

    st.markdown("---")

    # Charts
    col1, col2 = st.columns(2)

    with col1:
        # Users by role pie chart
        if analytics['users_by_role']:
            fig = px.pie(
                values=list(analytics['users_by_role'].values()),
                names=list(analytics['users_by_role'].keys()),
                title="Распределение по ролям",
                hole=0.4
            )
            fig.update_traces(textposition='inside', textinfo='percent+label')
            st.plotly_chart(fig, use_container_width=True)

    with col2:
        # Demo conversion
        conversion_data = {
            'Статус': ['Остались на Demo', 'Конвертировались'],
            'Количество': [
                analytics['demo_users'] - analytics['demo_converted'],
                analytics['demo_converted']
            ]
        }
        fig = px.bar(
            conversion_data,
            x='Статус',
            y='Количество',
            title=f"Конверсия Demo → Платные ({analytics['conversion_rate']:.1f}%)",
            color='Статус',
            color_discrete_map={
                'Остались на Demo': '#FFA07A',
                'Конвертировались': '#90EE90'
            }
        )
        st.plotly_chart(fig, use_container_width=True)

    # Registration trend (real data from database)
    st.markdown("---")
    st.subheader("📈 Тренд Регистраций (последние 30 дней)")

    # Get real registration stats from database
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)

    # Query users grouped by registration date
    users_in_period = db.query(User).filter(
        User.created_at >= start_date,
        User.created_at <= end_date
    ).all()

    # Count registrations per day
    registration_counts = {}
    for user in users_in_period:
        date = user.created_at.date()
        registration_counts[date] = registration_counts.get(date, 0) + 1

    # Create complete date range and fill with zeros
    dates = pd.date_range(start=start_date, end=end_date, freq='D')
    registrations = [registration_counts.get(date.date(), 0) for date in dates]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=dates,
        y=registrations,
        mode='lines+markers',
        name='Регистрации',
        line=dict(color='#3B82F6', width=2),
        marker=dict(size=6)
    ))
    fig.update_layout(
        title="Новые регистрации по дням",
        xaxis_title="Дата",
        yaxis_title="Регистраций",
        hovermode='x unified'
    )
    st.plotly_chart(fig, use_container_width=True)

    # Registration summary
    total_registrations = sum(registrations)
    avg_daily = total_registrations / 30 if total_registrations > 0 else 0
    max_daily = max(registrations) if registrations else 0

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("📊 Всего за период", total_registrations)
    with col2:
        st.metric("📈 Среднее в день", f"{avg_daily:.1f}")
    with col3:
        st.metric("🔝 Максимум за день", max_daily)


def show_audit_logs_tab(db):
    """Audit logs tab"""

    st.header("Журнал Аудита")

    # Filters
    col1, col2, col3 = st.columns(3)
    with col1:
        action_filter = st.selectbox(
            "Действие",
            ["Все", "login", "logout", "user_created_by_admin", "user_role_changed", "demo_activated"]
        )
    with col2:
        severity_filter = st.selectbox(
            "Важность",
            ["Все", "info", "warning", "error", "critical"]
        )
    with col3:
        days_back = st.number_input("За последние дней", min_value=1, max_value=90, value=7)

    # Get logs
    query = db.query(AuditLog).filter(
        AuditLog.created_at >= datetime.now(timezone.utc) - timedelta(days=days_back)
    )

    if action_filter != "Все":
        query = query.filter(AuditLog.action == action_filter)

    if severity_filter != "Все":
        query = query.filter(AuditLog.severity == severity_filter)

    logs = query.order_by(AuditLog.created_at.desc()).limit(100).all()

    # Display logs
    if logs:
        logs_data = []
        for log in logs:
            user = db.query(User).filter(User.id == log.user_id).first() if log.user_id else None

            logs_data.append({
                'Время': log.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                'Пользователь': user.email if user else 'N/A',
                'Действие': log.action,
                'Статус': log.status,
                'IP': log.ip_address or 'N/A',
                'Важность': log.severity
            })

        df = pd.DataFrame(logs_data)

        st.dataframe(
            df,
            column_config={
                "Время": st.column_config.TextColumn("Время", width="medium"),
                "Пользователь": st.column_config.TextColumn("Пользователь", width="medium"),
                "Действие": st.column_config.TextColumn("Действие", width="medium"),
                "Статус": st.column_config.TextColumn("Статус", width="small"),
                "IP": st.column_config.TextColumn("IP", width="medium"),
                "Важность": st.column_config.TextColumn("Важность", width="small")
            },
            use_container_width=True,
            height=500
        )

        # Export logs
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Экспортировать в CSV",
            data=csv,
            file_name=f"audit_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
            use_container_width=True
        )
    else:
        st.info("Логи не найдены за выбранный период")


# Entry point
if __name__ == "__main__":
    show_admin_panel()
