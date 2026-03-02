# -*- coding: utf-8 -*-
"""
Переиспользуемые UI-компоненты для Streamlit Admin Console
"""
import streamlit as st


def apply_custom_css():
    """Общие CSS-стили для всех страниц консоли."""
    st.markdown("""
    <style>
        .main-header {
            font-size: 2.2rem;
            font-weight: bold;
            color: #1f77b4;
            margin-bottom: 0.5rem;
        }
        .sub-header {
            font-size: 1.1rem;
            color: #666;
            margin-bottom: 1.5rem;
        }
        .action-card {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 1.5rem;
            border-radius: 1rem;
            color: white;
            text-align: center;
            cursor: pointer;
            transition: transform 0.2s;
        }
        .action-card:hover {
            transform: translateY(-2px);
        }
        .action-card h3 {
            color: white;
            margin-bottom: 0.5rem;
        }
        .action-card p {
            color: rgba(255,255,255,0.85);
            font-size: 0.9rem;
        }
        .risk-critical {
            background-color: #fee2e2; color: #dc2626;
            padding: 2px 8px; border-radius: 4px; font-weight: 600;
        }
        .risk-high {
            background-color: #ffedd5; color: #ea580c;
            padding: 2px 8px; border-radius: 4px; font-weight: 600;
        }
        .risk-medium {
            background-color: #fef9c3; color: #ca8a04;
            padding: 2px 8px; border-radius: 4px; font-weight: 600;
        }
        .risk-low {
            background-color: #dcfce7; color: #16a34a;
            padding: 2px 8px; border-radius: 4px; font-weight: 600;
        }
        .status-online { color: #16a34a; font-weight: bold; }
        .status-offline { color: #dc2626; font-weight: bold; }
        .status-warning { color: #ca8a04; font-weight: bold; }
        .metric-highlight {
            background-color: #f0f9ff;
            border-left: 4px solid #3b82f6;
            padding: 0.8rem 1rem;
            border-radius: 0 0.5rem 0.5rem 0;
            margin: 0.3rem 0;
        }
    </style>
    """, unsafe_allow_html=True)


def risk_badge(level: str) -> str:
    """HTML-бейдж уровня риска."""
    labels = {
        "critical": "Критический",
        "high": "Высокий",
        "medium": "Средний",
        "low": "Низкий",
    }
    label = labels.get(level.lower(), level)
    css_class = f"risk-{level.lower()}"
    return f'<span class="{css_class}">{label}</span>'


def risk_emoji(level: str) -> str:
    """Эмодзи-индикатор уровня риска."""
    mapping = {
        "critical": "🔴",
        "high": "🟠",
        "medium": "🟡",
        "low": "🟢",
    }
    return mapping.get(level.lower(), "⚪")


def status_indicator(is_ok: bool, label_ok: str = "Подключено", label_fail: str = "Недоступно") -> str:
    """HTML-индикатор статуса."""
    if is_ok:
        return f'<span class="status-online">✅ {label_ok}</span>'
    return f'<span class="status-offline">❌ {label_fail}</span>'


def metric_card(title: str, value: str, subtitle: str = "", icon: str = "📊"):
    """Карточка с метрикой."""
    st.markdown(f"""
    <div class="metric-highlight">
        <div style="font-size:0.85rem;color:#64748b;">{icon} {title}</div>
        <div style="font-size:1.5rem;font-weight:700;color:#1e293b;">{value}</div>
        <div style="font-size:0.8rem;color:#94a3b8;">{subtitle}</div>
    </div>
    """, unsafe_allow_html=True)


def section_header(title: str, description: str = ""):
    """Заголовок секции с описанием."""
    st.markdown(f'<div class="main-header">{title}</div>', unsafe_allow_html=True)
    if description:
        st.markdown(f'<div class="sub-header">{description}</div>', unsafe_allow_html=True)


def styled_expander_header(title: str, risk_level: str = "") -> str:
    """Заголовок для expander с опциональным бейджем риска."""
    if risk_level:
        return f"{title} {risk_emoji(risk_level)}"
    return title


def risk_level_ru(level: str) -> str:
    """Перевод уровня риска на русский."""
    mapping = {
        "critical": "Критический",
        "high": "Высокий",
        "medium": "Средний",
        "low": "Низкий",
    }
    return mapping.get(str(level).lower(), str(level))
