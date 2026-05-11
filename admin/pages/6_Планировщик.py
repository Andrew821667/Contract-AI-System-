# -*- coding: utf-8 -*-
"""
Планировщик фоновых задач — управление и мониторинг
"""
import streamlit as st
import sys
from pathlib import Path

# Project root
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

st.set_page_config(
    page_title="Contract AI — Планировщик",
    page_icon="🕐",
    layout="wide",
)

# Auth check
from admin.shared.session_helpers import check_admin_auth, show_admin_sidebar_user
if not check_admin_auth():
    st.stop()

show_admin_sidebar_user()

st.title("🕐 Планировщик задач")

from src.services.scheduler_service import SchedulerService, APSCHEDULER_AVAILABLE

if not APSCHEDULER_AVAILABLE:
    st.error("APScheduler не установлен. Выполните: `pip install APScheduler==3.10.4`")
    st.stop()

# Получить или создать экземпляр планировщика
if 'scheduler_service' not in st.session_state:
    from src.models import SessionLocal
    svc = SchedulerService(db_session_factory=SessionLocal)
    st.session_state['scheduler_service'] = svc
svc = st.session_state['scheduler_service']

# ─── Статус ──────────────────────────────────────────
col1, col2 = st.columns([3, 1])
with col1:
    if svc.is_running:
        st.success("Планировщик **запущен**")
    else:
        st.warning("Планировщик **остановлен**")

with col2:
    if svc.is_running:
        if st.button("Остановить", key="sched_stop"):
            svc.stop()
            st.rerun()
    else:
        if st.button("Запустить", key="sched_start"):
            svc.start()
            st.rerun()

st.markdown("---")

# ─── Зарегистрированные задачи ───────────────────────
st.subheader("Задачи")

job_descriptions = {
    'reindex_pending': {
        'desc': 'Переиндексация документов базы знаний с is_vectorized=False',
        'interval': 'Каждые 30 минут',
    },
    'cleanup_sessions': {
        'desc': 'Удаление сессий пользователей старше 7 дней',
        'interval': 'Ежедневно в 03:00',
    },
    'aggregate_analytics': {
        'desc': 'Подсчёт аналитических метрик за последний час',
        'interval': 'Каждый час',
    },
}

if svc.is_running:
    jobs = svc.get_jobs_info()
    if jobs:
        for job in jobs:
            info = job_descriptions.get(job['id'], {})
            with st.expander(f"**{job['name']}** — {info.get('interval', job['trigger'])}", expanded=False):
                st.markdown(f"**ID:** `{job['id']}`")
                st.markdown(f"**Описание:** {info.get('desc', '—')}")
                st.markdown(f"**Следующий запуск:** {job['next_run']}")
                st.markdown(f"**Триггер:** `{job['trigger']}`")
                if st.button("Запустить сейчас", key=f"run_{job['id']}"):
                    with st.spinner(f"Выполняется: {job['name']}..."):
                        msg = svc.run_job_now(job['id'])
                    st.success(msg)
                    st.rerun()
    else:
        st.info("Нет зарегистрированных задач")
else:
    for job_id, info in job_descriptions.items():
        st.markdown(f"- **{info.get('desc', job_id)}** — {info.get('interval', '')}")
    st.caption("Запустите планировщик для активации задач")

st.markdown("---")

# ─── История выполнений ──────────────────────────────
st.subheader("История выполнений")

logs = svc.get_recent_logs(limit=30)

if logs:
    import pandas as pd

    status_icons = {
        'success': '✅',
        'error': '❌',
        'skipped': '⏭️',
        'running': '🔄',
    }

    rows = []
    for log in logs:
        icon = status_icons.get(log['status'], '❓')
        rows.append({
            'Статус': f"{icon} {log['status']}",
            'Задача': log['job_name'],
            'Время': log['started_at'],
            'Длительность (сек)': log['duration_sec'] or '—',
            'Результат': log['result'] or log['error'] or '—',
            'Обработано': log['items_processed'],
        })

    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)
else:
    st.info("История пока пуста. Задачи ещё не выполнялись.")
