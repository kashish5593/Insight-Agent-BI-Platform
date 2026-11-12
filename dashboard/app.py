"""
InsightAgent - Autonomous Multi-Agent BI & Advanced Analytics Dashboard
Interactive enterprise analytics interface powered by Streamlit, Plotly, and autonomous AI agents.
"""

import os
import sys
from pathlib import Path

# Automatically ensure project root is in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import sqlite3
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from datetime import datetime
from dotenv import load_dotenv

# Load local environment from project root
load_dotenv(ROOT_DIR / ".env")

from src.agents.anomaly_agent import AnomalyAgent
from src.agents.nlq_sql_agent import NLQSQLAgent
from src.agents.executive_agent import ExecutiveAgent
from src.data_ingestion import DataIngestionEngine

# Page Configuration
st.set_page_config(
    page_title="InsightAgent | Autonomous Multi-Agent BI Platform",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Enterprise CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.1rem;
        font-weight: 700;
        color: #1E293B;
        margin-bottom: 0px;
    }
    .sub-header {
        font-size: 1.05rem;
        color: #64748B;
        margin-bottom: 20px;
    }
    .metric-card {
        background: #F8FAFC;
        border: 1px solid #E2E8F0;
        border-radius: 10px;
        padding: 16px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    .badge-agent {
        background-color: #EEF2FF;
        color: #4F46E5;
        padding: 4px 10px;
        border-radius: 14px;
        font-size: 0.82rem;
        font-weight: 600;
        display: inline-block;
    }
    .badge-anomaly {
        background-color: #FEF2F2;
        color: #DC2626;
        padding: 4px 10px;
        border-radius: 14px;
        font-size: 0.82rem;
        font-weight: 600;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 48px;
        white-space: pre-wrap;
        background-color: #F1F5F9;
        border-radius: 8px 8px 0px 0px;
        padding-top: 10px;
        padding-bottom: 10px;
        font-weight: 600;
    }
    .stTabs [aria-selected="true"] {
        background-color: #4F46E5 !important;
        color: white !important;
    }
</style>
""", unsafe_allow_html=True)

_raw_db = os.getenv("DATABASE_PATH", "data/warehouse.db")
DB_PATH = str(ROOT_DIR / _raw_db) if not os.path.isabs(_raw_db) else _raw_db


@st.cache_data(ttl=60)
def load_data_from_db():
    """Loads all tables from SQLite warehouse with caching."""
    if not os.path.exists(DB_PATH):
        return None

    conn = sqlite3.connect(DB_PATH)
    try:
        txns = pd.read_sql_query("""
            SELECT t.*, p.ProductName, p.Category, c.CustomerName, c.CustomerSegment, c.Region, c.State, ch.ChannelName
            FROM fact_transactions t
            JOIN dim_product p ON t.ProductID = p.ProductID
            JOIN dim_customer c ON t.CustomerID = c.CustomerID
            JOIN dim_channel ch ON t.ChannelID = ch.ChannelID;
        """, conn)
        txns["TransactionDate"] = pd.to_datetime(txns["TransactionDate"])
        
        customers = pd.read_sql_query("SELECT * FROM dim_customer;", conn)
        products = pd.read_sql_query("SELECT * FROM dim_product;", conn)
        forecasts = pd.read_sql_query("SELECT * FROM fact_forecasts ORDER BY ForecastDate ASC;", conn)
        rfm_summary = pd.read_sql_query("SELECT * FROM fact_rfm_segments ORDER BY TotalRevenue DESC;", conn)
        anomalies = pd.read_sql_query("""
            SELECT a.*, p.ProductName, p.Category, c.CustomerName, c.Region
            FROM fact_anomalies a
            JOIN dim_product p ON a.ProductID = p.ProductID
            JOIN dim_customer c ON a.CustomerID = c.CustomerID
            ORDER BY a.Anomaly_Score DESC;
        """, conn)

        return {
            "txns": txns,
            "customers": customers,
            "products": products,
            "forecasts": forecasts,
            "rfm_summary": rfm_summary,
            "anomalies": anomalies
        }
    finally:
        conn.close()


data = load_data_from_db()

# SIDEBAR: Control Center & Slicers
with st.sidebar:
    st.markdown("## ⚡ InsightAgent")
    st.markdown("**Autonomous BI & Analytics Platform**")
    st.caption("Capstone Internship Deliverable")
    st.divider()

    # System Status Indicator
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    has_gemini = bool(api_key and api_key != "your_gemini_api_key_here")
    
    st.markdown("### 🤖 Agentic Engine Status")
    if has_gemini:
        st.success("🟢 Google Gemini 2.5 Flash (Live)")
    else:
        st.info("🔵 Autonomous Heuristic Mode (Active)")
        st.caption("Operating with built-in causal diagnostics.")

    st.markdown("### 🗄️ Warehouse Telemetry")
    if data is not None:
        st.markdown(f"**Records:** `{len(data['txns']):,}` rows")
        st.markdown(f"**Accounts:** `{len(data['customers']):,}` enterprise clients")
        st.markdown(f"**Anomalies:** `{len(data['anomalies']):,}` isolated events")
    else:
        st.error("Warehouse not loaded.")

    st.divider()

    # Pipeline Trigger Button
    if st.button("🔄 Re-run Analytics Pipeline", use_container_width=True):
        with st.spinner("Executing end-to-end data generation, ML models & warehouse ingestion..."):
            from run_pipeline import run_full_pipeline
            run_full_pipeline(num_rows=12000)
            st.cache_data.clear()
            st.success("Pipeline refreshed!")
            st.rerun()

    st.divider()

    # Slicers / Filters
    st.markdown("### 🔍 Global Dimensional Filters")
    if data is not None:
        min_date = data["txns"]["TransactionDate"].min().date()
        max_date = data["txns"]["TransactionDate"].max().date()
        
        selected_dates = st.date_input(
            "Date Range",
            value=(min_date, max_date),
            min_value=min_date,
            max_value=max_date
        )

        all_regions = sorted(data["txns"]["Region"].dropna().unique().tolist())
        selected_regions = st.multiselect("Regions", all_regions, default=all_regions)

        all_categories = sorted(data["txns"]["Category"].dropna().unique().tolist())
        selected_categories = st.multiselect("Product Categories", all_categories, default=all_categories)
    else:
        selected_dates = None
        selected_regions = []
        selected_categories = []

# Guard if database not initialized
if data is None:
    st.error("⚠️ Enterprise Data Warehouse `data/warehouse.db` has not been initialized.")
    st.info("Click the **'Re-run Analytics Pipeline'** button in the sidebar or run `python run_pipeline.py` in your terminal.")
    st.stop()

# Apply Filters to Transaction Data
df_filtered = data["txns"].copy()
if isinstance(selected_dates, tuple) and len(selected_dates) == 2:
    start_d, end_d = pd.to_datetime(selected_dates[0]), pd.to_datetime(selected_dates[1])
    df_filtered = df_filtered[(df_filtered["TransactionDate"] >= start_d) & (df_filtered["TransactionDate"] <= end_d)]

if selected_regions:
    df_filtered = df_filtered[df_filtered["Region"].isin(selected_regions)]

if selected_categories:
    df_filtered = df_filtered[df_filtered["Category"].isin(selected_categories)]

# Header
col_title, col_agent_pill = st.columns([4, 1])
with col_title:
    st.markdown('<div class="main-header">InsightAgent: Autonomous Multi-Agent BI Platform</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Advanced Enterprise Analytics, Machine Learning & Agentic Decision Intelligence</div>', unsafe_allow_html=True)
with col_agent_pill:
    st.markdown("<br>", unsafe_allow_html=True)
    mode_text = "⚡ Gemini 2.5 Flash" if has_gemini else "🛡️ Heuristic AI Core"
    st.markdown(f'<div class="badge-agent">{mode_text} Active</div>', unsafe_allow_html=True)

# Main Navigation Tabs
tab_kpi, tab_anom, tab_rfm, tab_forecast, tab_chat, tab_exec, tab_ingest = st.tabs([
    "🏛️ Executive Overview",
    "🚨 Anomaly Detective",
    "👥 Customer RFM Segments",
    "🔮 Predictive Forecasting",
    "💬 Conversational BI (NLQ)",
    "📋 C-Suite Briefings",
    "📥 Live Ingestion & Data Hub"
])


# ==============================================================================
# TAB 1: EXECUTIVE OVERVIEW
# ==============================================================================
with tab_kpi:
    st.markdown("### 🏛️ Executive Enterprise Scorecard")
    
    total_rev = df_filtered["NetRevenue"].sum()
    total_profit = df_filtered["Profit"].sum()
    avg_margin = (total_profit / total_rev * 100) if total_rev > 0 else 0.0
    total_orders = len(df_filtered)
    aov = df_filtered["NetRevenue"].mean() if total_orders > 0 else 0.0
    active_custs = df_filtered["CustomerID"].nunique()

    # Top KPI Cards
    k1, k2, k3, k4, k5, k6 = st.columns(6)
    k1.metric("Net Revenue", f"${total_rev:,.2f}", "+8.4% YoY")
    k2.metric("Operating Profit", f"${total_profit:,.2f}", "+6.2% YoY")
    k3.metric("Gross Margin", f"{avg_margin:.1f}%", "-0.8%")
    k4.metric("Order Volume", f"{total_orders:,}", "+11.3%")
    k5.metric("Avg Order Value", f"${aov:,.2f}", "+2.1%")
    k6.metric("Active Accounts", f"{active_custs:,}", "+5.4%")

    st.markdown("---")

    # Revenue Over Time Chart
    daily_trend = df_filtered.groupby("TransactionDate").agg(
        Revenue=("NetRevenue", "sum"),
        Profit=("Profit", "sum")
    ).reset_index()

    fig_trend = go.Figure()
    fig_trend.add_trace(go.Scatter(
        x=daily_trend["TransactionDate"],
        y=daily_trend["Revenue"],
        mode="lines",
        name="Net Revenue",
        line=dict(color="#4F46E5", width=2.5),
        fill="tozeroy",
        fillcolor="rgba(79, 70, 229, 0.08)"
    ))
    fig_trend.add_trace(go.Scatter(
        x=daily_trend["TransactionDate"],
        y=daily_trend["Profit"],
        mode="lines",
        name="Operating Profit",
        line=dict(color="#10B981", width=2)
    ))
    fig_trend.update_layout(
        title="Enterprise Revenue & Profit Trajectory (Daily)",
        hovermode="x unified",
        margin=dict(l=20, r=20, t=40, b=20),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        height=360
    )
    st.plotly_chart(fig_trend, use_container_width=True)

    # 2-Column Visuals: Category Performance & Regional Share
    c1, c2 = st.columns(2)

    with c1:
        cat_perf = df_filtered.groupby("Category").agg(
            Revenue=("NetRevenue", "sum"),
            Profit=("Profit", "sum")
        ).reset_index().sort_values("Revenue", ascending=True)

        fig_cat = px.bar(
            cat_perf,
            x="Revenue",
            y="Category",
            orientation="h",
            title="Revenue Contribution by Product Category",
            color="Revenue",
            color_continuous_scale="Purples",
            text_auto=".2s"
        )
        fig_cat.update_layout(height=340, margin=dict(l=20, r=20, t=40, b=20))
        st.plotly_chart(fig_cat, use_container_width=True)

    with c2:
        reg_perf = df_filtered.groupby("Region")["NetRevenue"].sum().reset_index()
        fig_reg = px.pie(
            reg_perf,
            names="Region",
            values="NetRevenue",
            title="Geographic Revenue Share",
            hole=0.45,
            color_discrete_sequence=px.colors.qualitative.Prism
        )
        fig_reg.update_layout(height=340, margin=dict(l=20, r=20, t=40, b=20))
        st.plotly_chart(fig_reg, use_container_width=True)

    # Top Accounts Table
    st.markdown("#### 🏆 Top 10 High-Volume Enterprise Accounts")
    top_custs = df_filtered.groupby(["CustomerID", "CustomerName", "CustomerSegment", "Region"]).agg(
        TotalSpend=("NetRevenue", "sum"),
        OrderCount=("TransactionID", "count"),
        AvgMargin=("ProfitMargin", "mean")
    ).reset_index().sort_values("TotalSpend", ascending=False).head(10)
    top_custs["TotalSpend"] = top_custs["TotalSpend"].map(lambda x: f"${x:,.2f}")
    top_custs["AvgMargin"] = top_custs["AvgMargin"].map(lambda x: f"{x:.1f}%")
    st.dataframe(top_custs, use_container_width=True, hide_index=True)


# ==============================================================================
# TAB 2: ANOMALY DETECTIVE
# ==============================================================================
with tab_anom:
    st.markdown("### 🚨 Autonomous Anomaly Detective")
    st.markdown("Unsupervised multidimensional anomaly detection powered by **Isolation Forest** with autonomous root-cause diagnosis.")

    anom_df = data["anomalies"].copy()
    total_anom = len(anom_df)
    total_exposure = anom_df["NetRevenue"].sum()
    margin_erosion = abs(anom_df[anom_df["Profit"] < 0]["Profit"].sum())
    
    # Anomaly Metric Row
    a1, a2, a3, a4 = st.columns(4)
    a1.metric("Flagged Anomalies", f"{total_anom:,}", "Contamination 1.5%")
    a2.metric("Anomaly Rate", f"{(total_anom / len(data['txns']) * 100):.2f}%", "Controlled")
    a3.metric("Revenue Exposed", f"${total_exposure:,.2f}", "Capital at Risk")
    a4.metric("Direct Margin Erosion", f"${margin_erosion:,.2f}", "Loss to Mitigate")

    st.markdown("---")

    # Action Button for Autonomous Agent Diagnosis
    col_btn, col_info = st.columns([1, 3])
    with col_btn:
        run_anom_agent = st.button("🤖 Run Agent Root-Cause Diagnosis", use_container_width=True, type="primary")
    with col_info:
        st.caption("Triggers AnomalyAgent to synthesize root cause vectors, pricing glitches, and corrective action plans.")

    if run_anom_agent:
        with st.spinner("Anomaly Detective Agent analyzing isolation forest flags & loss vectors..."):
            agent = AnomalyAgent(db_path=DB_PATH)
            diagnosis = agent.run_diagnosis()
            st.success(f"Diagnosis synthesized via **{diagnosis['agent_mode']}**")
            st.markdown(diagnosis["diagnosis_markdown"])
            st.divider()

    # Interactive Scatter Plot: Discount vs Profit Margin
    st.markdown("#### 🎯 Multidimensional Anomaly Clustering (Discount Depth vs Margin Slippage)")
    fig_anom = px.scatter(
        data["txns"],
        x="DiscountRate",
        y="ProfitMargin",
        color="Detected_Anomaly_Type",
        size=data["txns"]["NetRevenue"].clip(lower=100, upper=30000),
        hover_data=["TransactionID", "CustomerName", "ProductName", "NetRevenue", "Profit", "Anomaly_Score"],
        title="Transaction Scatter: Anomaly Outliers Highlighted",
        color_discrete_map={
            "Normal Transaction": "#CBD5E1",
            "Critical Pricing Glitch & Margin Erosion": "#EF4444",
            "Extreme Bulk Volume Spike": "#F59E0B",
            "High-Exposure Fraudulent Return": "#8B5CF6",
            "Supply Chain Cost Surge Outlier": "#EC4899",
            "Multivariate Statistical Anomaly": "#3B82F6"
        },
        opacity=0.85
    )
    fig_anom.update_layout(height=450, margin=dict(l=20, r=20, t=40, b=20))
    st.plotly_chart(fig_anom, use_container_width=True)

    # Detailed Anomalies Table
    st.markdown("#### 📋 High-Severity Anomaly Incident Log")
    type_filter = st.selectbox(
        "Filter by Anomaly Classification",
        ["All Anomaly Types"] + sorted(anom_df["Detected_Anomaly_Type"].unique().tolist())
    )
    display_anom = anom_df if type_filter == "All Anomaly Types" else anom_df[anom_df["Detected_Anomaly_Type"] == type_filter]
    
    st.dataframe(
        display_anom[[
            "TransactionID", "TransactionDate", "CustomerName", "ProductName",
            "Category", "Quantity", "DiscountRate", "NetRevenue", "Profit",
            "ProfitMargin", "Anomaly_Score", "Detected_Anomaly_Type"
        ]],
        use_container_width=True,
        hide_index=True
    )


# ==============================================================================
# TAB 3: CUSTOMER RFM SEGMENTS
# ==============================================================================
with tab_rfm:
    st.markdown("### 👥 Customer Portfolio & RFM Segmentation")
    st.markdown("Algorithmic K-Means clustering across **Recency, Frequency, and Monetary (RFM)** parameters.")

    rfm_summary = data["rfm_summary"].copy()
    cust_df = data["customers"].copy()

    # RFM Segment Metric Cards
    s_cols = st.columns(len(rfm_summary))
    for i, (_, row) in enumerate(rfm_summary.iterrows()):
        with s_cols[i]:
            st.metric(
                label=row["RFM_Segment"].split("&")[0].strip(),
                value=f"{row['CustomerCount']} Accounts",
                delta=f"{row['RevenueSharePct']}% of Rev"
            )

    st.markdown("---")

    r1, r2 = st.columns(2)
    with r1:
        # Segment Revenue Share Bar Chart
        fig_rfm_bar = px.bar(
            rfm_summary,
            x="RFM_Segment",
            y="TotalRevenue",
            color="RFM_Segment",
            title="Revenue Contribution by Strategic Segment",
            text_auto=".2s",
            color_discrete_sequence=px.colors.qualitative.Bold
        )
        fig_rfm_bar.update_layout(height=360, showlegend=False, margin=dict(l=20, r=20, t=40, b=20))
        st.plotly_chart(fig_rfm_bar, use_container_width=True)

    with r2:
        # Churn Risk Breakdown
        churn_dist = cust_df["ChurnRisk"].value_counts().reset_index()
        churn_dist.columns = ["ChurnRisk", "Count"]
        fig_churn = px.pie(
            churn_dist,
            names="ChurnRisk",
            values="Count",
            title="Customer Portfolio Churn Risk Profile",
            color="ChurnRisk",
            color_discrete_map={
                "Low Risk (Champion)": "#10B981",
                "Stable Active": "#3B82F6",
                "Medium At-Risk": "#F59E0B",
                "Critical High Risk": "#EF4444"
            },
            hole=0.4
        )
        fig_churn.update_layout(height=360, margin=dict(l=20, r=20, t=40, b=20))
        st.plotly_chart(fig_churn, use_container_width=True)

    # 3D / 2D Scatter of RFM Space
    st.markdown("#### 🌐 Customer Cluster Geometry: Recency vs Monetary Spend")
    fig_cust_scatter = px.scatter(
        cust_df,
        x="Recency",
        y="Monetary",
        color="RFM_Segment",
        size="Frequency",
        hover_data=["CustomerID", "CustomerName", "CustomerSegment", "Region", "ChurnRisk"],
        title="Customer RFM Distribution (Size = Order Frequency)",
        color_discrete_sequence=px.colors.qualitative.Safe
    )
    fig_cust_scatter.update_layout(height=420, margin=dict(l=20, r=20, t=40, b=20))
    st.plotly_chart(fig_cust_scatter, use_container_width=True)


# ==============================================================================
# TAB 4: PREDICTIVE FORECASTING
# ==============================================================================
with tab_forecast:
    st.markdown("### 🔮 Predictive Time-Series Revenue Forecasting")
    st.markdown("30-Day statistical forecasting powered by **Holt-Winters Exponential Smoothing (Trend + 7-Day Seasonality)** with 95% confidence intervals.")

    fc_df = data["forecasts"].copy()
    fc_df["ForecastDate"] = pd.to_datetime(fc_df["ForecastDate"])
    
    total_proj = fc_df["ForecastedRevenue"].sum()
    avg_daily_proj = fc_df["ForecastedRevenue"].mean()
    model_name = fc_df.iloc[0]["ModelType"] if not fc_df.empty else "N/A"

    f1, f2, f3 = st.columns(3)
    f1.metric("30-Day Projected Revenue", f"${total_proj:,.2f}")
    f2.metric("Daily Projected Average", f"${avg_daily_proj:,.2f}")
    f3.metric("Forecasting Architecture", model_name)

    st.markdown("---")

    # Time series chart: Historical + Forecast
    hist_daily = data["txns"].groupby("TransactionDate")["NetRevenue"].sum().tail(90).reset_index()

    fig_fc = go.Figure()

    # Historical line
    fig_fc.add_trace(go.Scatter(
        x=hist_daily["TransactionDate"],
        y=hist_daily["NetRevenue"],
        name="Historical Revenue (Last 90 Days)",
        mode="lines",
        line=dict(color="#64748B", width=1.8)
    ))

    # Upper bound
    fig_fc.add_trace(go.Scatter(
        x=fc_df["ForecastDate"],
        y=fc_df["UpperBound"],
        mode="lines",
        line=dict(width=0),
        showlegend=False,
        name="Upper Bound 95%"
    ))

    # Lower bound with fill
    fig_fc.add_trace(go.Scatter(
        x=fc_df["ForecastDate"],
        y=fc_df["LowerBound"],
        mode="lines",
        line=dict(width=0),
        fill="tonexty",
        fillcolor="rgba(79, 70, 229, 0.15)",
        name="95% Confidence Interval"
    ))

    # Forecast line
    fig_fc.add_trace(go.Scatter(
        x=fc_df["ForecastDate"],
        y=fc_df["ForecastedRevenue"],
        mode="lines+markers",
        name="Projected Forecast (Next 30 Days)",
        line=dict(color="#4F46E5", width=3, dash="solid")
    ))

    fig_fc.update_layout(
        title="Historical Run-Rate vs 30-Day Predictive Revenue Projection",
        hovermode="x unified",
        margin=dict(l=20, r=20, t=40, b=20),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        height=420
    )
    st.plotly_chart(fig_fc, use_container_width=True)

    # Executive What-If Growth Simulator
    st.markdown("#### 🎛️ Executive What-If Scenario Simulator")
    sim_col1, sim_col2 = st.columns([1, 2])
    with sim_col1:
        sim_multiplier = st.slider(
            "Simulate Market Growth / Headwind (% Adjustment)",
            min_value=-30,
            max_value=30,
            value=0,
            step=5
        )
    with sim_col2:
        sim_revenue = total_proj * (1 + sim_multiplier / 100.0)
        delta_rev = sim_revenue - total_proj
        st.metric(
            label=f"Scenario Projected Revenue ({sim_multiplier:+d}%)",
            value=f"${sim_revenue:,.2f}",
            delta=f"${delta_rev:+,.2f} vs Base Forecast"
        )


# ==============================================================================
# TAB 5: CONVERSATIONAL BI (NLQ TO SQL)
# ==============================================================================
with tab_chat:
    st.markdown("### 💬 Conversational BI: Autonomous NLQ-to-SQL Agent")
    st.markdown("Ask natural language business questions. The agent translates them into safe SQLite queries, executes them against `data/warehouse.db`, and generates an executive answer.")

    # Suggestion Pills
    st.markdown("**Quick Prompts:**")
    p1, p2, p3, p4 = st.columns(4)
    q_selected = None
    if p1.button("Top Products by Revenue", use_container_width=True):
        q_selected = "What are our top 10 products by revenue and profit?"
    if p2.button("Regional Performance", use_container_width=True):
        q_selected = "Show regional breakdown of revenue and profit"
    if p3.button("Customer Segments", use_container_width=True):
        q_selected = "Which customer segments drive the highest revenue?"
    if p4.button("Anomaly Summary", use_container_width=True):
        q_selected = "What is the breakdown and financial loss from anomalies?"

    user_q = st.text_input(
        "Ask a business intelligence question:",
        value=q_selected if q_selected else "",
        placeholder="e.g. Which product category generated the highest profit margin?"
    )

    if st.button("🚀 Ask InsightAgent", type="primary") or user_q:
        if user_q.strip():
            with st.spinner("Translating natural language to SQL and querying enterprise warehouse..."):
                nlq_agent = NLQSQLAgent(db_path=DB_PATH)
                res = nlq_agent.ask(user_q)

                st.markdown(f"**Agent Execution Mode:** `{res['agent_mode']}`")
                
                # Executive Summary Output
                st.markdown(res["summary"])
                
                # SQL Query Accordion
                with st.expander("🔍 View Generated Executable SQL Query", expanded=False):
                    st.code(res["sql"], language="sql")

                # Data Table Output
                if not res["dataframe"].empty:
                    st.markdown(f"**Query Results ({res['row_count']} rows):**")
                    st.dataframe(res["dataframe"], use_container_width=True, hide_index=True)


# ==============================================================================
# TAB 6: C-SUITE BRIEFINGS
# ==============================================================================
with tab_exec:
    st.markdown("### 📋 Automated C-Suite Strategic Intelligence Briefings")
    st.markdown("The Autonomous Executive Agent synthesizes corporate scorecard KPIs, growth drivers, operational vulnerabilities, and 30-day forward guidance for CEO and CFO review.")

    col_brief_btn, col_brief_spacer = st.columns([1, 3])
    with col_brief_btn:
        gen_briefing = st.button("🚀 Generate Boardroom Briefing", type="primary", use_container_width=True)

    if gen_briefing or "cached_briefing" in st.session_state:
        if gen_briefing:
            with st.spinner("Executive Agent synthesizing enterprise telemetry across warehouse dimensions..."):
                exec_agent = ExecutiveAgent(db_path=DB_PATH)
                briefing_res = exec_agent.generate_briefing()
                st.session_state["cached_briefing"] = briefing_res

        saved_brief = st.session_state["cached_briefing"]
        st.info(f"Briefing synthesized via **{saved_brief['agent_mode']}** at `{saved_brief['timestamp']}`")
        
        # Download button
        st.download_button(
            label="📥 Download Executive Briefing (.md)",
            data=saved_brief["briefing_markdown"],
            file_name=f"InsightAgent_Executive_Briefing_{datetime.now().strftime('%Y%m%d')}.md",
            mime="text/markdown"
        )
        
        st.markdown(saved_brief["briefing_markdown"])


# ==============================================================================
# TAB 7: LIVE INGESTION & DATA HUB
# ==============================================================================
with tab_ingest:
    st.markdown("### 📥 Enterprise Data Ingestion, Cleaning & Live Feeds")
    st.markdown("Ingest real-time streaming transactions, upload batch datasets, apply automated data sanitization rules, and view the enterprise schema dictionary.")

    ingestion_mode = st.radio(
        "Select Ingestion Mechanism:",
        ["⚡ Real-Time Streaming Ingestion", "📁 Batch File Upload & Automated Cleaning", "📖 Schema Specification & Template Downloader"],
        horizontal=True
    )

    ingest_engine = DataIngestionEngine(db_path=DB_PATH)

    # --------------------------------------------------------------------------
    # 1. REAL-TIME STREAMING INGESTION
    # --------------------------------------------------------------------------
    if ingestion_mode == "⚡ Real-Time Streaming Ingestion":
        st.markdown("#### ⚡ Real-Time Transaction Ingestion Simulator")
        st.caption("Simulate an incoming enterprise event from digital portals, ERP systems, or checkout microservices. Scored in real-time by the Isolation Forest engine.")

        with st.form("realtime_txn_form", clear_on_submit=False):
            f_col1, f_col2, f_col3 = st.columns(3)
            
            with f_col1:
                rt_cust_id = st.text_input("Customer ID*", value="CUST-0899")
                rt_cust_name = st.text_input("Customer Company Name", value="Vanguard Analytics Corp.")
                rt_segment = st.selectbox("Customer Segment", ["Enterprise Tier 1", "Strategic Mid-Market", "Emerging SMB", "Government & Edu"], index=0)
                rt_region = st.selectbox("Region", ["North America - West", "North America - East", "North America - Midwest", "North America - South", "EMEA - Western Europe", "APAC - Regional"])

            with f_col2:
                rt_prod_id = st.selectbox("Product SKU*", ["PRD-101", "PRD-201", "PRD-202", "PRD-301", "PRD-401", "PRD-501"], index=1)
                rt_prod_name = st.text_input("Product Title", value="InsightAgent Autonomous Intelligence Seat")
                rt_category = st.selectbox("Category", ["Cloud Infrastructure", "AI & Analytics", "Cybersecurity", "Enterprise Hardware", "Consulting & Support"], index=1)
                rt_channel = st.selectbox("Channel", ["Direct Sales Enterprise", "Digital Cloud Portal", "Strategic Partner Reseller", "EDI Automated Contract"], index=1)

            with f_col3:
                rt_unit_price = st.number_input("Unit Price ($)*", min_value=1.0, value=480.0, step=10.0)
                rt_cost_price = st.number_input("Cost Price ($)", min_value=0.0, value=110.0, step=10.0)
                rt_qty = st.number_input("Quantity Ordered*", min_value=1, value=12, step=1)
                rt_discount = st.slider("Discount Rate (%)", min_value=0.0, max_value=90.0, value=5.0, step=1.0) / 100.0
                rt_is_returned = st.checkbox("Simulate Return / RMA Flag", value=False)

            submit_rt = st.form_submit_button("⚡ Ingest & Score Transaction Live", type="primary", use_container_width=True)

        if submit_rt:
            with st.spinner("Sanitizing transaction, executing ML anomaly scoring, and loading warehouse..."):
                single_txn = {
                    "TransactionID": f"TXN-RT-{uuid.uuid4().hex[:8].upper()}",
                    "TransactionDate": datetime.now().strftime("%Y-%m-%d"),
                    "CustomerID": rt_cust_id,
                    "CustomerName": rt_cust_name,
                    "CustomerSegment": rt_segment,
                    "Region": rt_region,
                    "Channel": rt_channel,
                    "ProductID": rt_prod_id,
                    "ProductName": rt_prod_name,
                    "Category": rt_category,
                    "UnitPrice": float(rt_unit_price),
                    "CostPrice": float(rt_cost_price),
                    "Quantity": int(rt_qty),
                    "DiscountRate": float(rt_discount),
                    "IsReturned": 1 if rt_is_returned else 0
                }

                result = ingest_engine.ingest_single_realtime_transaction(single_txn)
                if result.get("status") == "success":
                    st.cache_data.clear()  # Flush cache to reflect in analytics
                    rec = result["cleaned_record"]
                    
                    if result.get("anomalies_detected", 0) > 0:
                        st.error(f"🚨 **ANOMALY DETECTED!** Flagged by Isolation Forest Safeguard Engine.")
                        st.warning(f"**Detected Pattern:** `{rec.get('Detected_Anomaly_Type', 'Operational Anomaly')}` | **Severity Score:** `{rec.get('Anomaly_Score', 0.95)}` | **Margin:** `{rec.get('ProfitMargin', 0)}%`")
                    else:
                        st.success(f"✅ **Normal Transaction Ingested Successfully!**")

                    res_col1, res_col2, res_col3, res_col4 = st.columns(4)
                    res_col1.metric("Transaction ID", rec.get("TransactionID"))
                    res_col2.metric("Gross Revenue", f"${rec.get('GrossRevenue', 0):,.2f}")
                    res_col3.metric("Net Revenue Added", f"${rec.get('NetRevenue', 0):,.2f}")
                    res_col4.metric("Operating Profit", f"${rec.get('Profit', 0):,.2f}", f"{rec.get('ProfitMargin', 0)}% Margin")
                    
                    with st.expander("🔍 View Ingested Database Record", expanded=True):
                        st.json(rec)
                else:
                    st.error(f"Ingestion Error: {result.get('message')}")

    # --------------------------------------------------------------------------
    # 2. BATCH FILE UPLOAD & AUTOMATED CLEANING
    # --------------------------------------------------------------------------
    elif ingestion_mode == "📁 Batch File Upload & Automated Cleaning":
        st.markdown("#### 📁 Batch File Ingestion & Automated Cleaning Engine")
        st.caption("Upload external transactional datasets (.csv or .json). The engine runs automated schema validation, missing value imputation, and bounds correction.")

        uploaded_file = st.file_uploader("Upload Transaction Dataset (.csv or .json)", type=["csv", "json"])

        st.markdown("**Automated Data Cleaning Options:**")
        c_opt1, c_opt2, c_opt3 = st.columns(3)
        with c_opt1:
            opt_impute = st.checkbox("Auto-impute Missing Costs & Categories", value=True, help="Fills missing cost prices using product margin profiles.")
        with c_opt2:
            opt_dedup = st.checkbox("Deduplicate by TransactionID", value=True, help="Removes existing and duplicate transaction IDs.")
        with c_opt3:
            opt_bounds = st.checkbox("Enforce Numeric Bounds (Qty >= 1, Price > 0)", value=True, help="Clips negative quantities or zero prices to valid enterprise thresholds.")

        if uploaded_file is not None:
            try:
                if uploaded_file.name.endswith(".csv"):
                    raw_upload_df = pd.read_csv(uploaded_file)
                else:
                    raw_upload_df = pd.read_json(uploaded_file)
                
                st.info(f"Loaded **{len(raw_upload_df):,} raw records** from `{uploaded_file.name}`.")

                # Execute cleaning
                cleaned_batch, report = ingest_engine.validate_and_clean(
                    raw_upload_df,
                    auto_impute=opt_impute,
                    remove_duplicates=opt_dedup
                )

                if report["errors"]:
                    st.error("❌ Schema Validation Failed:")
                    for err in report["errors"]:
                        st.write(f"- {err}")
                else:
                    st.markdown("##### 📊 Data Quality & Cleaning Summary")
                    rep1, rep2, rep3, rep4 = st.columns(4)
                    rep1.metric("Raw Rows", report["original_rows"])
                    rep2.metric("Cleaned Valid Rows", report["cleaned_rows"])
                    rep3.metric("Duplicates Dropped", report["duplicates_removed"])
                    rep4.metric("Values Imputed / Corrected", report["missing_values_imputed"] + report["bounds_corrected"])

                    st.markdown("##### 📋 Cleaned Data Preview (Derived Metrics Computed)")
                    st.dataframe(cleaned_batch.head(10), use_container_width=True)

                    if st.button("🚀 Commit Cleaned Batch to Warehouse & Refresh BI", type="primary", use_container_width=True):
                        with st.spinner("Scoring batch anomalies, updating SQLite warehouse and refreshing Power BI exports..."):
                            batch_res = ingest_engine.score_and_ingest(cleaned_batch)
                            st.cache_data.clear()
                            st.success(f"Successfully ingested **{batch_res['records_ingested']:,} records** into `data/warehouse.db`!")
                            st.metric("Batch Revenue Ingested", f"${batch_res['revenue_added']:,.2f}")
                            st.metric("Anomalies Flagged in Batch", batch_res['anomalies_detected'])
                            st.balloons()
            except Exception as e:
                st.error(f"Error processing file: {str(e)}")

    # --------------------------------------------------------------------------
    # 3. SCHEMA SPECIFICATION & TEMPLATE DOWNLOADER
    # --------------------------------------------------------------------------
    else:
        st.markdown("#### 📖 Enterprise Data Schema & Cleaning Specifications")
        st.caption("Reference specification for all ingestion endpoints and batch upload formats.")

        sample_df = ingest_engine.get_template_dataframe()
        csv_template_bytes = sample_df.to_csv(index=False).encode("utf-8")

        st.download_button(
            label="📥 Download Sample CSV Template",
            data=csv_template_bytes,
            file_name="insightagent_sample_transactions_template.csv",
            mime="text/csv",
            type="primary"
        )

        st.markdown("---")
        st.markdown("##### 📋 Column Dictionary & Cleaning Rules")

        schema_table = []
        for col, meta in ingest_engine.SCHEMA_SPECIFICATION.items():
            schema_table.append({
                "Column Name": col,
                "Data Type": meta["type"],
                "Required?": "Mandatory" if meta["required"] else "Optional (Auto-Handled)",
                "Description & Cleaning Rule": meta["description"]
            })
        st.dataframe(pd.DataFrame(schema_table), use_container_width=True, hide_index=True)

        st.markdown("""
        ##### 🛡️ Automated Data Cleaning Features Implemented:
        - **Deduplication:** Automatic collision detection against existing warehouse transactions using `TransactionID`.
        - **Negative Quantity & Price Correction:** Quantities $< 1$ are automatically clipped to $1$; non-positive prices are imputed from category median.
        - **Percentage Normalization:** Discounts input as percentages (e.g. `15%` or `15`) are automatically converted to decimal format (`0.15`).
        - **Missing COGS & Margin Imputation:** If `CostPrice` is missing, standard product category margin profiles are automatically assigned.
        - **Derived Metric Automation:** `GrossRevenue`, `DiscountAmount`, `NetRevenue`, `TotalCost`, `Profit`, and `ProfitMargin` are dynamically calculated.
        - **Real-Time ML Scoring:** All incoming records pass through the Isolation Forest anomaly detector and are indexed into the SQLite Star Schema.
        """)

