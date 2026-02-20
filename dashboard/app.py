"""
CA/AZ Performance Dashboard — Nevoya Sales Ops (V2)
====================================================
High-fidelity Streamlit dashboard mirroring Metabase TX visual structure.

Run:  streamlit run dashboard/app.py
From: C:/Users/rbarr/OneDrive/Desktop/Nevoya/SalesOps/port_pro/

Tabs:
1. Weekly Summary      — KPIs, OTP/OTD gauges, customer performance table
2. Monthly Summary     — Monthly aggregation with run-rate projection
3. Performance by Lane — Customer x Lane breakdown
4. Performance by BCO  — Customer x BCO breakdown
5. Trends              — 12-week volume, revenue, OTP/OTD charts
6. Risks & Follow-Ups  — Flagged accounts with lane attribution
7. Methodology         — Calculation documentation
"""

import sys
from pathlib import Path

# Ensure sibling modules are importable regardless of working directory
sys.path.insert(0, str(Path(__file__).resolve().parent))

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime

from sample_data import generate_sample_loads, generate_customer_master
from data_engineering import transform_loads, compute_risk_flags, compute_lane_risks
from portpro_api import PortProClient

# ------------------------------------------------------------------
# Page Config
# ------------------------------------------------------------------
st.set_page_config(
    page_title="Nevoya — CA/AZ Performance Dashboard",
    page_icon="🚛",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ------------------------------------------------------------------
# Dark Theme CSS (Metabase-style)
# ------------------------------------------------------------------
st.markdown("""
<style>
    /* KPI cards */
    .kpi-card {
        background: #1a1d23;
        border: 1px solid #2a2d35;
        border-radius: 8px;
        padding: 20px;
        text-align: center;
    }
    .kpi-label {
        color: #8b95a5;
        font-size: 0.8rem;
        font-weight: 500;
        margin-bottom: 6px;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .kpi-value {
        color: #ffffff;
        font-size: 2.2rem;
        font-weight: 700;
        line-height: 1.2;
    }

    /* Section headers matching Metabase card titles */
    .section-header {
        color: #ffffff;
        font-size: 1rem;
        font-weight: 600;
        padding: 10px 0 8px 0;
        margin-bottom: 12px;
    }

    /* Tab styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 0px;
        border-bottom: 2px solid #2a2d35;
    }
    .stTabs [data-baseweb="tab"] {
        color: #8b95a5;
        font-weight: 500;
        padding: 8px 20px;
    }
    .stTabs [aria-selected="true"] {
        color: #4fc3f7 !important;
        border-bottom-color: #4fc3f7 !important;
    }

    /* Methodology cards */
    .method-card {
        background: #1a1d23;
        border: 1px solid #2a2d35;
        border-radius: 8px;
        padding: 20px;
        margin-bottom: 16px;
    }
    .method-card h3 { color: #ffffff; margin-top: 0; }
    .method-card ul { color: #c0c8d4; }
    .method-card p { color: #c0c8d4; }
    .method-card code {
        background: #0e1117;
        color: #4fc3f7;
        padding: 2px 6px;
        border-radius: 3px;
    }
    .method-table {
        width: 100%;
        color: #c0c8d4;
        border-collapse: collapse;
    }
    .method-table th {
        text-align: left;
        padding: 8px;
        color: #4fc3f7;
        border-bottom: 1px solid #2a2d35;
    }
    .method-table td {
        padding: 8px;
        border-bottom: 1px solid #1e2128;
    }

    /* Enough top padding to clear the Streamlit header bar */
    .block-container { padding-top: 3.5rem; }
</style>
""", unsafe_allow_html=True)


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------
CHART_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font_color="white",
    xaxis=dict(gridcolor="#2a2d35"),
    yaxis=dict(gridcolor="#2a2d35"),
)


def kpi_card(label, value):
    return f'<div class="kpi-card"><div class="kpi-label">{label}</div><div class="kpi-value">{value}</div></div>'


def make_gauge(value, title):
    """Semicircular gauge matching Metabase OTP/OTD gauges."""
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=value,
        number={"font": {"size": 44, "color": "white"}},
        gauge={
            "axis": {
                "range": [0, 100],
                "tickwidth": 1,
                "tickcolor": "#555",
                "tickvals": [0, 70, 90, 100],
                "ticktext": ["0", "70", "90", "100"],
                "tickfont": {"color": "#888", "size": 10},
            },
            "bar": {"color": "rgba(255,255,255,0.2)", "thickness": 0.15},
            "bgcolor": "#1a1d23",
            "borderwidth": 0,
            "steps": [
                {"range": [0, 70], "color": "#dc3545"},
                {"range": [70, 90], "color": "#ffc107"},
                {"range": [90, 100], "color": "#28a745"},
            ],
            "threshold": {
                "line": {"color": "white", "width": 3},
                "thickness": 0.8,
                "value": value,
            },
        },
    ))
    fig.add_annotation(x=0.13, y=0.22, text="Poor", showarrow=False,
                       font=dict(color="#dc3545", size=11))
    fig.add_annotation(x=0.87, y=0.35, text="Fair", showarrow=False,
                       font=dict(color="#ffc107", size=11))
    fig.add_annotation(x=0.87, y=0.22, text="Good", showarrow=False,
                       font=dict(color="#28a745", size=11))
    fig.update_layout(
        title={"text": title, "font": {"color": "white", "size": 13}, "x": 0.5},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=210,
        margin=dict(l=20, r=20, t=40, b=5),
    )
    return fig


def style_risk_table(df):
    """Apply Metabase-like row styling to risk/performance tables."""
    def _apply(row):
        styles = [""] * len(row)
        if "SERVICE_RISK" in df.columns:
            idx = df.columns.get_loc("SERVICE_RISK")
            if row.iloc[idx] == "AT RISK":
                styles[idx] = "color: #ff6b6b; font-weight: 700"
            elif row.iloc[idx] == "OK":
                styles[idx] = "color: #51cf66"
        if "VOLUME_TREND" in df.columns:
            idx = df.columns.get_loc("VOLUME_TREND")
            if row.iloc[idx] == "UP":
                styles[idx] = "color: #51cf66"
            elif row.iloc[idx] == "DOWN":
                styles[idx] = "color: #ff6b6b"
        return styles
    return df.style.apply(_apply, axis=1)


# ------------------------------------------------------------------
# Data Loading
# ------------------------------------------------------------------
@st.cache_data(ttl=300)
def load_live_data():
    client = PortProClient()
    raw_loads = client.get_all_loads()
    raw_customers = client.get_customers()
    return raw_loads, raw_customers


@st.cache_data(ttl=300)
def load_sample_data():
    return generate_sample_loads(), generate_customer_master()


# ------------------------------------------------------------------
# Sidebar: Connection + Filters
# ------------------------------------------------------------------
st.sidebar.title("Nevoya Sales Ops")
st.sidebar.markdown("**CA/AZ Performance Dashboard**")
st.sidebar.markdown("---")

client = PortProClient()
if client.is_configured:
    st.sidebar.success("PortPro API: Connected")
    use_api = st.sidebar.checkbox("Use Live API Data", value=True)
else:
    st.sidebar.warning("PortPro API: Not configured")
    st.sidebar.caption("Add credentials to `dashboard/.env.json`")
    use_api = False

if use_api:
    try:
        raw_loads, raw_customers = load_live_data()
        data_source = "live"
    except Exception as e:
        st.sidebar.error(f"API error: {e}")
        raw_loads, raw_customers = load_sample_data()
        data_source = "sample"
else:
    raw_loads, raw_customers = load_sample_data()
    data_source = "sample"

# Transform
data = transform_loads(raw_loads, raw_customers)
cleaned_df = data["cleaned"]
weekly_df = data["weekly"]
monthly_df = data["monthly"]
lane_df = data["lanes"]
customer_master = data["customer_master"]

if data_source == "sample":
    st.sidebar.info("Demo mode (sample data)")
else:
    st.sidebar.success(f"Live: {len(cleaned_df)} completed loads")

st.sidebar.markdown("---")

# Week selector
available_weeks = sorted(weekly_df["week_start"].unique(), reverse=True) if not weekly_df.empty else []
selected_week = st.sidebar.selectbox(
    "Week Start (Monday)",
    options=available_weeks,
    index=0,
) if available_weeks else None

# Customer filter
all_customers = sorted(weekly_df["customer_name"].unique()) if not weekly_df.empty else []
selected_customers = st.sidebar.multiselect(
    "Customer",
    options=all_customers,
    default=all_customers,
)

# BCO filter
all_bcos = sorted(cleaned_df["bco_derived"].unique()) if "bco_derived" in cleaned_df.columns and not cleaned_df.empty else []
selected_bcos = st.sidebar.multiselect("BCO", options=all_bcos, default=[], help="Leave empty for all")

# Lane filter
all_lanes = sorted(lane_df["lane"].unique()) if not lane_df.empty else []
selected_lanes = st.sidebar.multiselect("Lane", options=all_lanes, default=[], help="Leave empty for all")


# ------------------------------------------------------------------
# Title
# ------------------------------------------------------------------
st.markdown("### Customer Success Dashboard")
st.caption(f"{'Live API' if data_source == 'live' else 'Sample Data'} | CA/AZ Operations")


# ==================================================================
# TAB NAVIGATION
# ==================================================================
tab_weekly, tab_monthly, tab_lane, tab_bco, tab_trends, tab_risks, tab_method = st.tabs([
    "Weekly Summary",
    "Monthly Summary",
    "Performance by Lane",
    "Performance by BCO",
    "Trends",
    "Risks & Follow-Ups",
    "Methodology",
])


# ==================================================================
# TAB 1: WEEKLY SUMMARY
# ==================================================================
with tab_weekly:
    if selected_week and not weekly_df.empty:
        week_data = weekly_df[
            (weekly_df["week_start"] == selected_week) &
            (weekly_df["customer_name"].isin(selected_customers))
        ]
        week_loads = cleaned_df[
            (cleaned_df["week_start"] == selected_week) &
            (cleaned_df["customer_name"].isin(selected_customers))
        ]

        total_loads = int(week_data["loads"].sum())
        total_revenue = week_data["revenue"].sum()
        avg_rev = total_revenue / total_loads if total_loads > 0 else 0
        otp_pct = week_loads["on_time_pickup"].mean() * 100 if len(week_loads) > 0 else 0
        otd_pct = week_loads["on_time_delivery"].mean() * 100 if len(week_loads) > 0 else 0

        # KPI Row: 3 cards + 2 gauges
        k1, k2, k3, g1, g2 = st.columns([1, 1, 1, 1.2, 1.2])
        with k1:
            st.markdown(kpi_card("KPI Total Loads", f"{total_loads:,}"), unsafe_allow_html=True)
        with k2:
            st.markdown(kpi_card("KPI Total Revenue", f"${total_revenue:,.0f}"), unsafe_allow_html=True)
        with k3:
            st.markdown(kpi_card("KPI Avg Revenue", f"${avg_rev:,.1f}"), unsafe_allow_html=True)
        with g1:
            st.plotly_chart(make_gauge(round(otp_pct, 1), "KPI OTP"), use_container_width=True)
        with g2:
            st.plotly_chart(make_gauge(round(otd_pct, 1), "KPI OTD"), use_container_width=True)

        # Customer Performance Table
        st.markdown('<div class="section-header">Customer Performance Table</div>', unsafe_allow_html=True)

        if not week_data.empty:
            tbl = week_data[[
                "customer_name", "loads", "revenue", "change_label",
                "uncontrollable_events", "volume_trend", "service_risk"
            ]].copy()
            tbl = tbl.rename(columns={
                "customer_name": "CUSTOMER",
                "loads": "WEEKLY_LOADS",
                "revenue": "WEEKLY_REVENUE",
                "change_label": "WOW_LOAD_CHANGE_PCT",
                "uncontrollable_events": "UNCONTROLLABLE_EVENTS",
                "volume_trend": "VOLUME_TREND",
                "service_risk": "SERVICE_RISK",
            })
            tbl["WEEKLY_REVENUE"] = tbl["WEEKLY_REVENUE"].apply(lambda x: f"{x:,.0f}")
            tbl = tbl.sort_values("WEEKLY_LOADS", ascending=False).reset_index(drop=True)
            st.dataframe(style_risk_table(tbl), use_container_width=True, hide_index=True, height=460)
    else:
        st.info("No weekly data available.")


# ==================================================================
# TAB 2: MONTHLY SUMMARY
# ==================================================================
with tab_monthly:
    if not monthly_df.empty:
        available_months = sorted(monthly_df["month_start"].unique(), reverse=True)
        sel_month = st.selectbox("Select Month", options=available_months, index=0, key="month_sel")

        month_data = monthly_df[
            (monthly_df["month_start"] == sel_month) &
            (monthly_df["customer_name"].isin(selected_customers))
        ]

        is_current = month_data["is_current_month"].any() if "is_current_month" in month_data.columns else False
        total_loads = int(month_data["loads"].sum())
        total_revenue = month_data["revenue"].sum()

        if is_current and "run_rate_loads" in month_data.columns:
            rr_loads = int(month_data["run_rate_loads"].sum())
            rr_revenue = month_data["run_rate_revenue"].sum()
        else:
            rr_loads, rr_revenue = total_loads, total_revenue

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.markdown(kpi_card("Monthly Loads (Actual)", f"{total_loads:,}"), unsafe_allow_html=True)
        with c2:
            st.markdown(kpi_card("Monthly Revenue (Actual)", f"${total_revenue:,.0f}"), unsafe_allow_html=True)
        with c3:
            lbl = "Run-Rate Loads" if is_current else "Total Loads"
            st.markdown(kpi_card(lbl, f"{rr_loads:,}"), unsafe_allow_html=True)
        with c4:
            lbl = "Run-Rate Revenue" if is_current else "Total Revenue"
            st.markdown(kpi_card(lbl, f"${rr_revenue:,.0f}"), unsafe_allow_html=True)

        if is_current:
            st.caption("Current month — run-rate projects month-end totals from daily average so far.")

        st.markdown('<div class="section-header">Monthly Customer Performance</div>', unsafe_allow_html=True)

        cols = ["customer_name", "loads", "revenue"]
        if is_current and "run_rate_loads" in month_data.columns:
            cols += ["run_rate_loads", "run_rate_revenue"]
        cols += [c for c in ["volume_trend", "service_risk"] if c in month_data.columns]

        mtbl = month_data[[c for c in cols if c in month_data.columns]].copy()
        rename = {
            "customer_name": "CUSTOMER", "loads": "MONTHLY_LOADS",
            "revenue": "MONTHLY_REVENUE", "run_rate_loads": "RUN_RATE_LOADS",
            "run_rate_revenue": "RUN_RATE_REVENUE",
            "volume_trend": "VOLUME_TREND", "service_risk": "SERVICE_RISK",
        }
        mtbl = mtbl.rename(columns=rename)
        for col in ["MONTHLY_REVENUE", "RUN_RATE_REVENUE"]:
            if col in mtbl.columns:
                mtbl[col] = mtbl[col].apply(lambda x: f"{x:,.0f}")
        mtbl = mtbl.sort_values("MONTHLY_LOADS", ascending=False).reset_index(drop=True)
        st.dataframe(style_risk_table(mtbl), use_container_width=True, hide_index=True, height=460)
    else:
        st.info("No monthly data available.")


# ==================================================================
# TAB 3: PERFORMANCE BY LANE
# ==================================================================
with tab_lane:
    st.markdown('<div class="section-header">Performance by Lane</div>', unsafe_allow_html=True)

    if not lane_df.empty and selected_week:
        wl = lane_df[lane_df["week_start"] == selected_week].copy()
        if selected_customers:
            wl = wl[wl["customer_name"].isin(selected_customers)]
        if selected_lanes:
            wl = wl[wl["lane"].isin(selected_lanes)]

        if not wl.empty:
            ltbl = wl[["customer_name", "lane", "volume", "revenue", "otd_pct"]].copy()
            ltbl = ltbl.rename(columns={
                "customer_name": "CUSTOMER", "lane": "LANE",
                "volume": "VOLUME", "revenue": "REVENUE", "otd_pct": "OTD_PCT",
            })
            ltbl["REVENUE"] = ltbl["REVENUE"].apply(lambda x: f"{x:,.0f}")
            ltbl = ltbl.sort_values(["CUSTOMER", "VOLUME"], ascending=[True, False]).reset_index(drop=True)
            st.dataframe(ltbl, use_container_width=True, hide_index=True, height=520)
        else:
            st.info("No lane data for selected filters.")
    else:
        st.info("No lane data available.")


# ==================================================================
# TAB 4: PERFORMANCE BY BCO
# ==================================================================
with tab_bco:
    st.markdown('<div class="section-header">Performance by BCO</div>', unsafe_allow_html=True)

    bco_col = "bco_derived" if "bco_derived" in cleaned_df.columns else ("bco" if "bco" in cleaned_df.columns else None)

    if bco_col and not cleaned_df.empty and selected_week:
        wb = cleaned_df[cleaned_df["week_start"] == selected_week].copy()
        if selected_customers:
            wb = wb[wb["customer_name"].isin(selected_customers)]
        if selected_bcos:
            wb = wb[wb[bco_col].isin(selected_bcos)]
        # Exclude empty/Direct BCOs for cleaner display
        wb = wb[wb[bco_col].apply(lambda x: bool(x) and str(x).strip() not in ("", "Direct", "Unknown BCO"))]

        if not wb.empty:
            ba = wb.groupby(["customer_name", bco_col]).agg(
                volume=("load_id", "count"),
                revenue=("pricing_total", "sum"),
                otd=("on_time_delivery", "mean"),
            ).reset_index()
            ba["otd_pct"] = (ba["otd"] * 100).round(1)

            btbl = ba[["customer_name", bco_col, "volume", "revenue", "otd_pct"]].copy()
            btbl = btbl.rename(columns={
                "customer_name": "CUSTOMER", bco_col: "BCO",
                "volume": "VOLUME", "revenue": "REVENUE", "otd_pct": "OTD_PCT",
            })
            btbl["REVENUE"] = btbl["REVENUE"].apply(lambda x: f"{x:,.0f}")
            btbl = btbl.sort_values(["CUSTOMER", "VOLUME"], ascending=[True, False]).reset_index(drop=True)
            st.dataframe(btbl, use_container_width=True, hide_index=True, height=520)
        else:
            st.info("No BCO data for selected filters.")
    else:
        st.info("No BCO data available.")


# ==================================================================
# TAB 5: TRENDS (12-week)
# ==================================================================
with tab_trends:
    if not weekly_df.empty:
        trend = weekly_df[weekly_df["customer_name"].isin(selected_customers)].copy()
        all_wks = sorted(trend["week_start"].unique())
        last_12 = all_wks[-12:] if len(all_wks) > 12 else all_wks
        trend = trend[trend["week_start"].isin(last_12)]

        if not trend.empty:
            # --- Volume Trend (stacked bar by customer) ---
            vol = trend.groupby(["week_start", "customer_name"])["loads"].sum().reset_index()
            vol = vol[vol["loads"] > 0]

            fig_vol = px.bar(
                vol, x="week_start", y="loads", color="customer_name",
                title="Volume Trend",
                labels={"week_start": "Week", "loads": "Load Count", "customer_name": ""},
                barmode="stack",
            )
            fig_vol.update_layout(
                height=440,
                **CHART_LAYOUT,
                legend=dict(orientation="h", y=1.12, x=0, font=dict(size=10)),
                margin=dict(l=40, r=20, t=80, b=40),
            )
            st.plotly_chart(fig_vol, use_container_width=True)

            # --- Revenue Trend (stacked bar by customer) ---
            rev = trend.groupby(["week_start", "customer_name"])["revenue"].sum().reset_index()
            rev = rev[rev["revenue"] > 0]

            fig_rev = px.bar(
                rev, x="week_start", y="revenue", color="customer_name",
                title="Revenue Trend",
                labels={"week_start": "Week", "revenue": "Revenue ($)", "customer_name": ""},
                barmode="stack",
            )
            fig_rev.update_layout(
                height=440,
                **CHART_LAYOUT,
                legend=dict(orientation="h", y=1.12, x=0, font=dict(size=10)),
                margin=dict(l=40, r=20, t=80, b=40),
            )
            st.plotly_chart(fig_rev, use_container_width=True)

            # --- OTP & OTD Trend Lines ---
            trend_loads = cleaned_df[
                (cleaned_df["week_start"].isin(last_12)) &
                (cleaned_df["customer_name"].isin(selected_customers))
            ]
            if not trend_loads.empty:
                otp_otd = trend_loads.groupby("week_start").agg(
                    otp=("on_time_pickup", "mean"),
                    otd=("on_time_delivery", "mean"),
                ).reset_index().sort_values("week_start")
                otp_otd["otp_pct"] = (otp_otd["otp"] * 100).round(1)
                otp_otd["otd_pct"] = (otp_otd["otd"] * 100).round(1)

                otp_col, otd_col = st.columns(2)

                with otp_col:
                    fig_otp = go.Figure()
                    fig_otp.add_trace(go.Scatter(
                        x=otp_otd["week_start"], y=otp_otd["otp_pct"],
                        mode="lines+markers", name="OTP %",
                        line=dict(color="#4fc3f7", width=2),
                        marker=dict(size=7, color="#4fc3f7"),
                    ))
                    fig_otp.add_hline(
                        y=90, line_dash="dot", line_color="#51cf66",
                        annotation_text="90% Target",
                        annotation_position="top right",
                        annotation_font_color="#51cf66",
                    )
                    fig_otp.update_layout(
                        title="OTP Trend (Total)", height=300,
                        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                        font_color="white",
                        xaxis=dict(gridcolor="#2a2d35"),
                        yaxis=dict(range=[0, 105], gridcolor="#2a2d35", title="OTP %"),
                        margin=dict(l=40, r=20, t=40, b=40),
                    )
                    st.plotly_chart(fig_otp, use_container_width=True)

                with otd_col:
                    fig_otd = go.Figure()
                    fig_otd.add_trace(go.Scatter(
                        x=otp_otd["week_start"], y=otp_otd["otd_pct"],
                        mode="lines+markers", name="OTD %",
                        line=dict(color="#b388ff", width=2),
                        marker=dict(size=7, color="#b388ff"),
                    ))
                    fig_otd.add_hline(
                        y=90, line_dash="dot", line_color="#51cf66",
                        annotation_text="90% Target",
                        annotation_position="top right",
                        annotation_font_color="#51cf66",
                    )
                    fig_otd.update_layout(
                        title="OTD Trend (Total)", height=300,
                        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                        font_color="white",
                        xaxis=dict(gridcolor="#2a2d35"),
                        yaxis=dict(range=[0, 105], gridcolor="#2a2d35", title="OTD %"),
                        margin=dict(l=40, r=20, t=40, b=40),
                    )
                    st.plotly_chart(fig_otd, use_container_width=True)
    else:
        st.info("No trend data available.")


# ==================================================================
# TAB 6: RISKS & FOLLOW-UPS
# ==================================================================
with tab_risks:
    st.markdown('<div class="section-header">Risks & Follow-Ups</div>', unsafe_allow_html=True)

    if selected_week and not weekly_df.empty:
        risk_df = compute_risk_flags(weekly_df, cleaned_df, selected_week)

        if not risk_df.empty:
            rtbl = risk_df.rename(columns={
                "customer_name": "CUSTOMER",
                "weekly_revenue": "WEEKLY_REVENUE",
                "weekly_loads": "WEEKLY_LOADS",
                "wow_change_pct": "WOW_CHANGE_PCT",
                "on_time_delivery_pct": "ON_TIME_DELIVERY_PCT",
                "risk_flag": "RISK_FLAG",
            }).copy()
            rtbl["WEEKLY_REVENUE"] = rtbl["WEEKLY_REVENUE"].apply(lambda x: f"{x:,.0f}")
            st.dataframe(rtbl, use_container_width=True, hide_index=True, height=350)

            # Lane-level risk attribution
            st.markdown('<div class="section-header">Lane-Level Risk Attribution</div>', unsafe_allow_html=True)
            lane_risks = compute_lane_risks(cleaned_df, selected_week)

            if not lane_risks.empty:
                flagged = risk_df["customer_name"].unique()
                lr = lane_risks[lane_risks["customer_name"].isin(flagged)].copy()
                if not lr.empty:
                    lr = lr[["customer_name", "lane", "volume", "revenue", "otd_pct"]].rename(columns={
                        "customer_name": "CUSTOMER", "lane": "LANE",
                        "volume": "VOLUME", "revenue": "REVENUE", "otd_pct": "OTD_PCT",
                    })
                    lr["REVENUE"] = lr["REVENUE"].apply(lambda x: f"{x:,.0f}")
                    st.dataframe(lr, use_container_width=True, hide_index=True, height=300)
                else:
                    st.caption("No lane data for flagged customers this week.")
            else:
                st.caption("No lane-level data for this week.")
        else:
            st.success("No risk flags for the selected week.")
    else:
        st.info("Select a week to view risks.")


# ==================================================================
# TAB 7: METHODOLOGY
# ==================================================================
with tab_method:
    st.markdown("## Methodology")
    st.markdown("This document describes how metrics are calculated across all dashboard tabs.")

    col_l, col_r = st.columns(2)

    with col_l:
        st.markdown("""
<div class="method-card">
<h3>Data Sources</h3>
<ul>
    <li><strong>PortPro API <code>/v1/loads</code></strong>: Load-level revenue data including customer, BCO, lane, and completion date</li>
    <li><strong>PortPro API <code>/v1/customer</code></strong>: Customer master list for always-visible LEFT JOIN</li>
</ul>
<h3>Week Definition</h3>
<ul>
    <li><strong>Week:</strong> Monday through Sunday (7 days)</li>
    <li>All weekly metrics use <code>createdAt</code> to determine which week a load belongs to</li>
</ul>
<h3>Always-Visible Customers</h3>
<ul>
    <li>Dashboard uses LEFT JOIN from a Customer Master List (customers active in trailing 12 weeks)</li>
    <li>Ensures customers with <strong>0 loads</strong> in selected week are still visible</li>
    <li>Identifies "stale" accounts or unexpected volume drops</li>
</ul>
</div>
""", unsafe_allow_html=True)

    with col_r:
        st.markdown("""
<div class="method-card">
<h3>Weekly Summary KPIs</h3>
<ul>
    <li><strong>Total Loads:</strong> Count of distinct loads completed in the selected week</li>
    <li><strong>Total Revenue:</strong> Sum of <code>pricing.finalAmount</code> (all charge line items)</li>
    <li><strong>Avg Revenue/Load:</strong> Total Revenue &divide; Total Loads</li>
    <li><strong>OTP %:</strong> % of pickup stops arriving at or before appointment time</li>
    <li><strong>OTD %:</strong> % of delivery stops arriving at or before appointment time</li>
</ul>
<p><em>On-time = actual arrival &le; scheduled appointment (no grace period)</em></p>
</div>
""", unsafe_allow_html=True)

    # Customer Performance Table methodology
    st.markdown("""
<div class="method-card">
<h3>Customer Performance Table</h3>
<table class="method-table">
    <tr><th>Metric</th><th>Calculation</th></tr>
    <tr><td>Weekly Loads</td><td>Distinct loads completed this week (0 if none)</td></tr>
    <tr><td>Weekly Revenue</td><td>Sum of <code>pricing.finalAmount</code> (base rate)</td></tr>
    <tr><td>WoW Load Change %</td><td>(current_week - prior_week) / prior_week &times; 100</td></tr>
    <tr><td>Uncontrollable Events</td><td>Count of non-Nevoya-driven delays (currently counting all delays)</td></tr>
    <tr><td>Volume Trend</td><td><strong>UP</strong> if loads &gt; 110% of trailing 4-week avg, <strong>DOWN</strong> if &lt; 90%, else <strong>STABLE</strong></td></tr>
    <tr><td>Service Risk</td><td><strong>AT RISK</strong> if Controllable OTD &lt; 90% (currently using total OTD), else <strong>OK</strong></td></tr>
</table>
</div>
""", unsafe_allow_html=True)

    col_l2, col_r2 = st.columns(2)

    with col_l2:
        st.markdown("""
<div class="method-card">
<h3>Trends Tab</h3>
<ul>
    <li>Shows <strong>last 12 weeks</strong> (rolling from current date, may include partial current week)</li>
    <li><strong>Volume Trend:</strong> Weekly load count by customer (stacked bars)</li>
    <li><strong>Revenue Trend:</strong> Weekly revenue by customer (stacked bars)</li>
    <li><strong>OTP/OTD Trend (Total):</strong> Weekly average on-time % across all customers</li>
</ul>
<h3>Performance by Lane</h3>
<ul>
    <li>Aggregated at <strong>Origin City, State &rarr; Destination City, State</strong> level</li>
    <li>Facility names, terminal IDs stripped from aggregation</li>
    <li>Shows Volume, Revenue, OTD per lane</li>
</ul>
</div>
""", unsafe_allow_html=True)

    with col_r2:
        st.markdown("""
<div class="method-card">
<h3>Performance by BCO</h3>
<ul>
    <li>Breakdown by Beneficial Cargo Owner</li>
    <li>Specific to CHR/Broker accounts</li>
    <li>Shows Volume, Revenue, OTD per BCO</li>
</ul>
<h3>Risks & Follow-Ups</h3>
<p>Customers are flagged based on:</p>
<ul>
    <li><strong>Stale Account:</strong> 0 loads this week but had loads in trailing 12 weeks</li>
    <li><strong>High Revenue + Declining Volume:</strong> Revenue share &ge; 5% AND WoW load change &lt; -20%</li>
    <li><strong>High Revenue + Poor Service:</strong> Revenue share &ge; 5% AND Controllable OTD &lt; 90% (currently using total OTD)</li>
    <li><strong>Sharp WoW Drops:</strong> WoW load change &lt; -30%</li>
    <li><strong>Below Trailing Average:</strong> Current loads &lt; 70% of trailing 4-week average</li>
</ul>
</div>
""", unsafe_allow_html=True)
