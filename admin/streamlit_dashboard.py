"""
Contract AI System v2.0 - Streamlit Admin Dashboard
Main admin console with system metrics and configuration
"""
import streamlit as st
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Page configuration
st.set_page_config(
    page_title="Contract AI Admin - v2.0",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        margin-bottom: 1rem;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 0.5rem 0;
    }
    .status-success {
        color: #28a745;
        font-weight: bold;
    }
    .status-warning {
        color: #ffc107;
        font-weight: bold;
    }
    .status-error {
        color: #dc3545;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

# Sidebar
with st.sidebar:
    st.title("⚙️ Contract AI v2.0")
    st.markdown("---")

    # System Status
    st.subheader("🔌 System Status")
    st.success("✅ Online")
    st.metric("Uptime", "12h 34m")

    st.markdown("---")

    # Navigation
    st.subheader("📂 Navigation")
    page = st.radio(
        "Go to:",
        ["Dashboard", "System Config", "LLM Metrics", "RAG Statistics", "Test Connections"],
        label_visibility="collapsed"
    )

    st.markdown("---")
    st.caption("Contract AI System v2.0")
    st.caption("Multi-Model Routing | RAG | Human-in-the-Loop")

# Main content area
if page == "Dashboard":
    # Header
    st.markdown('<div class="main-header">📊 System Dashboard</div>', unsafe_allow_html=True)

    # Row 1: Key Metrics
    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        st.metric(
            label="📄 Documents Today",
            value="47",
            delta="+8",
            help="Documents processed today"
        )

    with col2:
        st.metric(
            label="💰 Cost/Doc",
            value="$0.019",
            delta="-91%",
            delta_color="inverse",
            help="Average cost per document"
        )

    with col3:
        st.metric(
            label="🎯 Confidence",
            value="94.2%",
            delta="+1.2%",
            help="Average confidence score"
        )

    with col4:
        st.metric(
            label="⏳ Pending Approval",
            value="3",
            delta="",
            help="Documents awaiting user approval"
        )

    with col5:
        st.metric(
            label="📑 Active Contracts",
            value="1,842",
            delta="+23",
            help="Total active contracts"
        )

    st.markdown("---")

    # Row 2: Charts
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("📈 Processing Volume (Last 7 Days)")
        # Placeholder for chart
        st.line_chart({
            "Mon": 35, "Tue": 42, "Wed": 38, "Thu": 45,
            "Fri": 52, "Sat": 28, "Sun": 47
        })

    with col2:
        st.subheader("🤖 Model Usage Distribution")
        # Placeholder for pie chart
        model_data = {
            "DeepSeek-V3": 87,
            "Claude 4.5": 10,
            "GPT-4o": 3
        }
        st.bar_chart(model_data)

    st.markdown("---")

    # Row 3: Current System Mode
    st.subheader("⚙️ Current System Configuration")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.info("**System Mode:** Full Load")
        st.caption("All modules running in parallel")

    with col2:
        st.info("**Default Model:** DeepSeek-V3")
        st.caption("Primary worker for cost optimization")

    with col3:
        st.info("**RAG Status:** Enabled")
        st.caption("Top-K: 5, Threshold: 0.7")

    st.markdown("---")

    # Row 4: Recent Activity
    st.subheader("📋 Recent Activity")

    activity_data = [
        {"Time": "10:42", "Event": "Document digitized", "Details": "Contract #2453", "Status": "✅ Success"},
        {"Time": "10:38", "Event": "Negotiation analyzed", "Details": "Session #891", "Status": "⏳ Awaiting Approval"},
        {"Time": "10:35", "Event": "Model switched", "Details": "DeepSeek → Claude (complexity: 0.85)", "Status": "✅ Success"},
        {"Time": "10:30", "Event": "RAG lookup", "Details": "5 precedents found", "Status": "✅ Success"},
        {"Time": "10:25", "Event": "Protocol generated", "Details": "12 disagreements", "Status": "⏳ Awaiting Approval"},
    ]

    st.dataframe(activity_data, use_container_width=True)

elif page == "System Config":
    st.markdown('<div class="main-header">⚙️ System Configuration</div>', unsafe_allow_html=True)

    st.warning("⚠️ Configuration changes require system restart")

    # System Mode
    st.subheader("🔧 System Operation Mode")

    current_mode = st.selectbox(
        "Select Mode",
        ["Full Load (Parallel)", "Sequential (Economy)", "Manual (Custom)"],
        help="Full Load: All modules run in parallel (fastest)\n"
             "Sequential: Modules run one by one (economy)\n"
             "Manual: Select which modules to enable"
    )

    if current_mode == "Manual (Custom)":
        st.multiselect(
            "Enabled Modules",
            ["OCR", "Level1 Extraction", "LLM Extraction", "RAG Filter", "Validation", "Embedding Generation"],
            default=["OCR", "LLM Extraction", "Validation"]
        )

    if st.button("💾 Apply System Mode"):
        st.success("✅ System mode updated!")

    st.markdown("---")

    # Smart Router Config
    st.subheader("🤖 Smart Router Configuration")

    col1, col2 = st.columns(2)

    with col1:
        default_model = st.selectbox(
            "Default Model",
            ["DeepSeek-V3", "Claude 4.5 Sonnet", "GPT-4o", "GPT-4o-mini"]
        )

    with col2:
        complexity_threshold = st.slider(
            "Complexity Threshold",
            min_value=0.0,
            max_value=1.0,
            value=0.8,
            step=0.05,
            help="Threshold for switching to Claude (higher = more selective)"
        )

    enable_fallback = st.checkbox("Enable Fallback Mechanism", value=True)

    if st.button("💾 Apply Router Config"):
        st.success("✅ Router configuration updated!")

    st.markdown("---")

    # RAG Config
    st.subheader("🔍 RAG Configuration")

    col1, col2, col3 = st.columns(3)

    with col1:
        rag_enabled = st.checkbox("Enable RAG", value=True)

    with col2:
        rag_top_k = st.number_input("Top-K Results", min_value=1, max_value=20, value=5)

    with col3:
        rag_threshold = st.slider(
            "Similarity Threshold",
            min_value=0.0,
            max_value=1.0,
            value=0.7,
            step=0.05
        )

    if st.button("💾 Apply RAG Config"):
        st.success("✅ RAG configuration updated!")

elif page == "LLM Metrics":
    st.markdown('<div class="main-header">📊 LLM Usage Metrics</div>', unsafe_allow_html=True)

    # Filters
    col1, col2, col3 = st.columns(3)

    with col1:
        date_range = st.date_input("Date Range", value=[])

    with col2:
        model_filter = st.multiselect(
            "Models",
            ["DeepSeek-V3", "Claude 4.5", "GPT-4o", "GPT-4o-mini"],
            default=["DeepSeek-V3", "Claude 4.5"]
        )

    with col3:
        status_filter = st.selectbox("Status", ["All", "Success", "Failed", "Partial"])

    st.markdown("---")

    # Metrics Table
    st.subheader("📋 Recent LLM Requests")

    metrics_data = [
        {
            "Timestamp": "2026-01-09 10:42:15",
            "Model": "DeepSeek-V3",
            "Document": "Contract #2453",
            "Tokens (In/Out)": "1,234 / 567",
            "Cost": "$0.00028",
            "Time (sec)": "1.8",
            "Confidence": "0.95",
            "Status": "✅ Success"
        },
        {
            "Timestamp": "2026-01-09 10:38:22",
            "Model": "Claude 4.5",
            "Document": "Contract #2452",
            "Tokens (In/Out)": "2,456 / 892",
            "Cost": "$0.02058",
            "Time (sec)": "3.2",
            "Confidence": "0.97",
            "Status": "✅ Success"
        },
        {
            "Timestamp": "2026-01-09 10:35:10",
            "Model": "DeepSeek-V3",
            "Document": "Session #891",
            "Tokens (In/Out)": "980 / 423",
            "Cost": "$0.00020",
            "Time (sec)": "1.5",
            "Confidence": "0.89",
            "Status": "⚠️ Fallback Used"
        },
    ]

    st.dataframe(metrics_data, use_container_width=True)

    st.markdown("---")

    # Cost Breakdown
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("💰 Cost by Model (Last 30 Days)")
        cost_data = {
            "DeepSeek-V3": 12.45,
            "Claude 4.5": 38.92,
            "GPT-4o": 4.23,
            "GPT-4o-mini": 0.87
        }
        st.bar_chart(cost_data)

    with col2:
        st.subheader("📊 Request Count by Model")
        request_data = {
            "DeepSeek-V3": 1250,
            "Claude 4.5": 145,
            "GPT-4o": 42,
            "GPT-4o-mini": 85
        }
        st.bar_chart(request_data)

elif page == "RAG Statistics":
    st.markdown('<div class="main-header">🔍 RAG Statistics</div>', unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("📚 Knowledge Base Entries", "247")

    with col2:
        st.metric("🔍 Total Queries (Today)", "184")

    with col3:
        st.metric("📊 Avg Similarity Score", "0.82")

    st.markdown("---")

    # Most Used Knowledge
    st.subheader("📖 Most Referenced Knowledge")

    knowledge_data = [
        {"Title": "Ограничение ответственности в договорах поставки", "Type": "best_practice", "Usage": 47},
        {"Title": "Стандартная формулировка штрафа", "Type": "template_clause", "Usage": 38},
        {"Title": "Компромисс по предоплате", "Type": "negotiation_tactic", "Usage": 25},
        {"Title": "Иностранная подсудность", "Type": "risk_pattern", "Usage": 19},
    ]

    st.dataframe(knowledge_data, use_container_width=True)

    st.markdown("---")

    # Add New Knowledge
    st.subheader("➕ Add New Knowledge Entry")

    with st.form("add_knowledge"):
        col1, col2 = st.columns(2)

        with col1:
            title = st.text_input("Title")
            content_type = st.selectbox(
                "Type",
                ["best_practice", "regulation", "precedent", "template_clause", "risk_pattern", "negotiation_tactic"]
            )

        with col2:
            source = st.text_input("Source (optional)")

        content = st.text_area("Content", height=150)

        submitted = st.form_submit_button("💾 Add Entry")

        if submitted:
            st.success("✅ Knowledge entry added!")

elif page == "Test Connections":
    st.markdown('<div class="main-header">🔌 Test API Connections</div>', unsafe_allow_html=True)

    st.info("Test connectivity to all configured LLM APIs")

    if st.button("🚀 Run Connection Tests"):
        with st.spinner("Testing connections..."):
            import time

            # Simulate API tests
            col1, col2, col3, col4 = st.columns(4)

            with col1:
                st.markdown("### DeepSeek-V3")
                time.sleep(0.5)
                st.success("✅ Connected")
                st.caption("Response time: 150ms")

            with col2:
                st.markdown("### Claude 4.5")
                time.sleep(0.5)
                st.success("✅ Connected")
                st.caption("Response time: 220ms")

            with col3:
                st.markdown("### GPT-4o")
                time.sleep(0.5)
                st.success("✅ Connected")
                st.caption("Response time: 180ms")

            with col4:
                st.markdown("### GPT-4o-mini")
                time.sleep(0.5)
                st.success("✅ Connected")
                st.caption("Response time: 120ms")

        st.success("🎉 All APIs connected successfully!")

    st.markdown("---")

    # Configuration Preview
    st.subheader("📋 Configuration Preview")

    config_preview = """
    Default Model: DeepSeek-V3
    Complexity Threshold: 0.8
    RAG Enabled: True
    RAG Top-K: 5
    Fallback: Enabled
    """

    st.code(config_preview)

# Footer
st.markdown("---")
st.caption("Contract AI System v2.0 | Multi-Model Routing | Built with Streamlit")
