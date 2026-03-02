"""
Dashboard метрик Smart Router
Показывает статистику использования моделей, стоимость и производительность
"""
import streamlit as st
import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

st.set_page_config(
    page_title="Метрики моделей - Contract AI",
    page_icon="📊",
    layout="wide"
)

st.title("📊 Метрики Smart Router")
st.markdown("Статистика использования LLM моделей и стоимость обработки")

st.markdown("---")

# ============================================================
# Инициализация session_state для хранения метрик
# ============================================================
if "processing_metrics" not in st.session_state:
    st.session_state.processing_metrics = []


def add_metric(metric: dict):
    """Добавляет метрику в session_state (вызывается из Process Documents)."""
    st.session_state.processing_metrics.append({
        "timestamp": datetime.now().isoformat(),
        **metric,
    })


# ============================================================
# Данные
# ============================================================
metrics = st.session_state.processing_metrics

if not metrics:
    st.info(
        "📭 Нет данных. Обработайте документы на странице **Process Documents**, "
        "и метрики появятся здесь автоматически."
    )

    # Показываем описание полей
    st.markdown("### Что будет отображаться")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("""
        **По каждой обработке:**
        - Выбранная модель
        - Complexity score
        - Способ выбора модели
        """)
    with col2:
        st.markdown("""
        **Токены и стоимость:**
        - Input / Output tokens
        - Стоимость в USD
        - Стоимость за сессию
        """)
    with col3:
        st.markdown("""
        **Производительность:**
        - Время обработки
        - Confidence score
        - Статус (success / fallback)
        """)

    # Конфигурация моделей
    st.markdown("---")
    st.header("⚙️ Конфигурация моделей")

    try:
        from src.config.llm_config import get_llm_config
        config = get_llm_config()
        available = config.get_available_models()

        models_info = [
            ("DeepSeek-V3", config.DEEPSEEK_MODEL, config.COST_DEEPSEEK_INPUT, config.COST_DEEPSEEK_OUTPUT),
            ("Claude Sonnet", config.ANTHROPIC_MODEL, config.COST_CLAUDE_INPUT, config.COST_CLAUDE_OUTPUT),
            ("GPT-4o", config.OPENAI_MODEL, config.COST_GPT4O_INPUT, config.COST_GPT4O_OUTPUT),
            ("GPT-4o-mini", config.OPENAI_MODEL_MINI, config.COST_GPT4O_MINI_INPUT, config.COST_GPT4O_MINI_OUTPUT),
        ]

        cols = st.columns(len(models_info))
        for i, (name, model_id, cost_in, cost_out) in enumerate(models_info):
            is_available = model_id in available
            with cols[i]:
                status_icon = "✅" if is_available else "🔒"
                st.metric(f"{status_icon} {name}", f"${cost_in:.2f} / ${cost_out:.2f}")
                st.caption(f"Input / Output за 1M tokens")
                if not is_available:
                    st.caption("API ключ не настроен")

        st.markdown(f"**Router threshold:** {config.ROUTER_COMPLEXITY_THRESHOLD}")
        st.markdown(f"**Fallback:** {'включён' if config.ROUTER_ENABLE_FALLBACK else 'выключен'}")

    except Exception as e:
        st.warning(f"Не удалось загрузить конфигурацию: {e}")

    st.stop()

# ============================================================
# Агрегаты
# ============================================================
st.header("📈 Сводка за сессию")

total_docs = len(metrics)
total_cost = sum(m.get("cost_usd", 0) for m in metrics)
total_tokens_in = sum(m.get("tokens_input", 0) for m in metrics)
total_tokens_out = sum(m.get("tokens_output", 0) for m in metrics)
avg_time = sum(m.get("processing_time_sec", 0) for m in metrics) / total_docs if total_docs else 0
avg_complexity = sum(m.get("complexity_score", 0) for m in metrics) / total_docs if total_docs else 0

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Документов обработано", total_docs)
with col2:
    st.metric("Общая стоимость", f"${total_cost:.4f}")
with col3:
    st.metric("Среднее время", f"{avg_time:.1f}s")
with col4:
    st.metric("Средняя сложность", f"{avg_complexity:.2f}")

# Токены
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Tokens Input (всего)", f"{total_tokens_in:,}")
with col2:
    st.metric("Tokens Output (всего)", f"{total_tokens_out:,}")
with col3:
    avg_cost = total_cost / total_docs if total_docs else 0
    st.metric("Средняя стоимость/док", f"${avg_cost:.4f}")

# ============================================================
# По моделям
# ============================================================
st.markdown("---")
st.header("🤖 По моделям")

# Группировка по моделям
model_stats = {}
for m in metrics:
    model = m.get("model_used", "unknown")
    if model not in model_stats:
        model_stats[model] = {
            "count": 0,
            "cost": 0.0,
            "tokens_in": 0,
            "tokens_out": 0,
            "time": 0.0,
        }
    model_stats[model]["count"] += 1
    model_stats[model]["cost"] += m.get("cost_usd", 0)
    model_stats[model]["tokens_in"] += m.get("tokens_input", 0)
    model_stats[model]["tokens_out"] += m.get("tokens_output", 0)
    model_stats[model]["time"] += m.get("processing_time_sec", 0)

cols = st.columns(max(len(model_stats), 1))
for i, (model, stats) in enumerate(model_stats.items()):
    with cols[i % len(cols)]:
        st.subheader(f"🔹 {model}")
        st.write(f"**Документов:** {stats['count']}")
        st.write(f"**Стоимость:** ${stats['cost']:.4f}")
        st.write(f"**Tokens:** {stats['tokens_in']:,} in / {stats['tokens_out']:,} out")
        avg_t = stats['time'] / stats['count'] if stats['count'] else 0
        st.write(f"**Среднее время:** {avg_t:.1f}s")

# ============================================================
# По статусу
# ============================================================
status_counts = {}
for m in metrics:
    s = m.get("status", "unknown")
    status_counts[s] = status_counts.get(s, 0) + 1

if len(status_counts) > 1 or "success" not in status_counts:
    st.markdown("---")
    st.header("⚡ По статусу")
    for status, count in sorted(status_counts.items()):
        icon = {"success": "✅", "fallback_used": "🔄", "retry_success": "🔁", "failed": "❌"}.get(status, "❓")
        st.write(f"{icon} **{status}**: {count}")

# ============================================================
# Графики
# ============================================================
st.markdown("---")
st.header("📉 Графики")

# Стоимость по документам
cost_data = {f"Док {i+1}": m.get("cost_usd", 0) for i, m in enumerate(metrics)}
if cost_data:
    st.subheader("Стоимость по документам")
    st.bar_chart(cost_data)

# Complexity по документам
complexity_data = {f"Док {i+1}": m.get("complexity_score", 0) for i, m in enumerate(metrics)}
if complexity_data:
    st.subheader("Сложность документов")
    st.bar_chart(complexity_data)

# Время по документам
time_data = {f"Док {i+1}": m.get("processing_time_sec", 0) for i, m in enumerate(metrics)}
if time_data:
    st.subheader("Время обработки (сек)")
    st.bar_chart(time_data)

# ============================================================
# Таблица всех обработок
# ============================================================
st.markdown("---")
st.header("📋 Все обработки")

table_data = []
for i, m in enumerate(metrics):
    table_data.append({
        "#": i + 1,
        "Время": m.get("timestamp", "")[:19],
        "Модель": m.get("model_used", ""),
        "Выбор": m.get("model_selected_by", ""),
        "Сложность": f"{m.get('complexity_score', 0):.2f}",
        "Tokens In": m.get("tokens_input", 0),
        "Tokens Out": m.get("tokens_output", 0),
        "Стоимость": f"${m.get('cost_usd', 0):.4f}",
        "Время (с)": f"{m.get('processing_time_sec', 0):.1f}",
        "Статус": m.get("status", ""),
    })

if table_data:
    st.dataframe(table_data, use_container_width=True)

# ============================================================
# Очистка
# ============================================================
st.markdown("---")
if st.button("🗑️ Очистить метрики сессии"):
    st.session_state.processing_metrics = []
    st.rerun()
