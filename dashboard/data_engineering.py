"""
Data Engineering Layer — CA/AZ Performance Dashboard (V2)
==========================================================
Transforms raw PortPro API load objects into dashboard-ready DataFrames.

Outputs:
  - cleaned_df:       Flat load-level DataFrame
  - weekly_customer:  Weekly aggregation with always-visible customers
  - monthly_customer: Monthly aggregation with run-rate projection
  - lane_df:          Lane-level weekly aggregation
  - lane_customer_df: Lane x Customer aggregation (for lane-level risk)
  - risk_df:          Flagged risk accounts with lane attribution
"""

import re
import pandas as pd
import numpy as np
from datetime import datetime, timedelta


# ------------------------------------------------------------------
# 1. ADDRESS PARSING
# ------------------------------------------------------------------

TERMINAL_CITY_MAP = {
    "ITS LONG BEACH": ("Long Beach", "CA"),
    "TTI": ("Long Beach", "CA"),
    "TRAPAC WILMINGTON": ("Wilmington", "CA"),
    "LBCT": ("Long Beach", "CA"),
    "WBCT": ("Long Beach", "CA"),
    "APM LOS ANGELES": ("Los Angeles", "CA"),
    "FENIX": ("Terminal Island", "CA"),
    "YTI": ("Long Beach", "CA"),
    "EVERPORT TERMINAL ISLAND": ("Terminal Island", "CA"),
    "PIER A": ("Long Beach", "CA"),
    "MATSON": ("Long Beach", "CA"),
    "OOCL": ("Long Beach", "CA"),
    "SSA": ("Long Beach", "CA"),
    "ITS CARSON": ("Carson", "CA"),
    "SHIPPERS TRANSPORT CARSON": ("Carson", "CA"),
    "ODW LOGISTICS": ("Long Beach", "CA"),
    "BNSF SAN BERNARDINO": ("San Bernardino", "CA"),
}

US_STATES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
    "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
    "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
    "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
}


def parse_city_state_from_address(address_str):
    if not address_str or pd.isna(address_str):
        return ("Unknown", "??")
    parts = [p.strip() for p in str(address_str).split(",")]
    for i, part in enumerate(parts):
        match = re.match(r"^([A-Z]{2})\s+\d{5}", part)
        if match and match.group(1) in US_STATES and i > 0:
            return (parts[i - 1].strip().title(), match.group(1))
    return ("Unknown", "??")


def resolve_pickup_city(load):
    city, state = parse_city_state_from_address(load.get("shipperAddress", ""))
    if city != "Unknown":
        return city, state
    shipper_name = str(load.get("shipperName", "")).upper().strip()
    if shipper_name in TERMINAL_CITY_MAP:
        return TERMINAL_CITY_MAP[shipper_name]
    if " - " in shipper_name:
        return (shipper_name.split(" - ", 1)[1].strip().title(), "CA")
    return ("Unknown", "CA")


def resolve_delivery_city(load):
    city, state = parse_city_state_from_address(load.get("consigneeAddress", ""))
    if city != "Unknown":
        return city, state
    consignee_name = str(load.get("consigneeName", "")).upper().strip()
    if " - " in consignee_name:
        return (consignee_name.split(" - ", 1)[1].strip().title(), "CA")
    return ("Unknown", "??")


# ------------------------------------------------------------------
# 2. BCO MAPPING & EXCEPTION CLASSIFICATION
# ------------------------------------------------------------------

def derive_bco(load):
    ref = str(load.get("reference_number", ""))
    load_type = load.get("type_of_load", "")
    if load_type == "IMPORT" or "_M" in ref:
        return load.get("consigneeName", "") or "Unknown BCO"
    elif load_type == "ROAD" or "_R" in ref:
        return load.get("shipperName", "") or "Unknown BCO"
    return "Direct"


def classify_exception(load):
    if load.get("terminalHold", False) or str(load.get("custom", "")).upper() == "HOLD":
        return "Uncontrollable Event"
    return ""


# ------------------------------------------------------------------
# 3. FLATTEN RAW API → DataFrame
# ------------------------------------------------------------------

def flatten_loads(raw_loads):
    """Flatten raw API load dicts into a DataFrame.

    Critical design decisions:
      - Date: uses ``loadCompletedAt`` (not ``createdAt``) so a load
        created in January but delivered in February counts in February.
      - Revenue: uses ``totalAmount`` (the all-in rate) — **not** the sum
        of individual ``pricing`` charge-code line items.
      - Only loads with a ``loadCompletedAt`` value are included (those
        are the ones that have actually been delivered).
    """
    records = []
    for load in raw_loads:
        # --- Completion date (source of truth) ---
        completed_at = load.get("loadCompletedAt") or load.get("loadCompletedDate") or ""
        if not completed_at:
            continue  # skip loads that haven't been completed yet

        completed_date = completed_at[:10]
        week_start = ""
        month_start = ""
        try:
            dt = datetime.strptime(completed_date, "%Y-%m-%d")
            week_start = (dt - timedelta(days=dt.weekday())).strftime("%Y-%m-%d")
            month_start = dt.strftime("%Y-%m-01")
        except ValueError:
            continue

        pickup_city, pickup_state = resolve_pickup_city(load)
        delivery_city, delivery_state = resolve_delivery_city(load)

        # --- Revenue: flat totalAmount (all-in rate) ---
        total_revenue = float(load.get("totalAmount", 0) or 0)

        records.append({
            "load_id": load.get("reference_number", ""),
            "customer_name": load.get("callerName", "Unknown"),
            "customer_id": load.get("caller", {}).get("_id", "") if isinstance(load.get("caller"), dict) else "",
            "shipper_name": load.get("shipperName", ""),
            "consignee_name": load.get("consigneeName", ""),
            "pickup_city": pickup_city,
            "pickup_state": pickup_state,
            "delivery_city": delivery_city,
            "delivery_state": delivery_state,
            "lane": f"{pickup_city}, {pickup_state} \u2192 {delivery_city}, {delivery_state}",
            "bco_derived": derive_bco(load),
            "pricing_total": total_revenue,
            "total_weight": float(load.get("totalWeight", 0) or 0),
            "status": load.get("status", ""),
            "type_of_load": load.get("type_of_load", ""),
            "completed_date": completed_date,
            "week_start": week_start,
            "month_start": month_start,
            "container_no": load.get("containerNo", ""),
            "distance_miles": float(load.get("totalMiles", 0) or 0),
            "exception_label": classify_exception(load),
            "on_time_pickup": 1,
            "on_time_delivery": 1,
        })
    return pd.DataFrame(records)


def build_customer_master(raw_customers):
    records = []
    for cust in raw_customers:
        records.append({
            "id": cust.get("_id", ""),
            "name": cust.get("company_name", "Unknown"),
            "tier": 2,
            "is_broker": True,
        })
    return pd.DataFrame(records)


# ------------------------------------------------------------------
# 4. ALWAYS-VISIBLE CUSTOMERS (LEFT JOIN)
# ------------------------------------------------------------------

def _skeleton_join(load_df, customer_master, period_col):
    """LEFT JOIN from customer master onto aggregated load data by period."""
    if load_df.empty or customer_master.empty:
        return pd.DataFrame()

    periods = sorted(load_df[period_col].unique())
    skeleton_rows = []
    for period in periods:
        for _, cust in customer_master.iterrows():
            skeleton_rows.append({
                "customer_name": cust["name"],
                "customer_id": cust.get("id", ""),
                "customer_tier": cust.get("tier", 2),
                period_col: period,
            })
    skeleton = pd.DataFrame(skeleton_rows)

    agg = load_df.groupby(["customer_name", period_col]).agg(
        loads=("load_id", "count"),
        revenue=("pricing_total", "sum"),
        avg_revenue=("pricing_total", "mean"),
        otp=("on_time_pickup", "mean"),
        otd=("on_time_delivery", "mean"),
        uncontrollable_events=("exception_label", lambda x: (x == "Uncontrollable Event").sum()),
    ).reset_index()

    merged = skeleton.merge(agg, on=["customer_name", period_col], how="left")
    merged["loads"] = merged["loads"].fillna(0).astype(int)
    merged["revenue"] = merged["revenue"].fillna(0.0)
    merged["avg_revenue"] = merged["avg_revenue"].fillna(0.0)
    merged["otp"] = merged["otp"].fillna(np.nan)
    merged["otd"] = merged["otd"].fillna(np.nan)
    merged["uncontrollable_events"] = merged["uncontrollable_events"].fillna(0).astype(int)
    return merged


def _add_wow_and_flags(df, period_col, loads_col="loads"):
    """Add period-over-period change %, volume trend, and service risk."""
    df = df.sort_values(["customer_name", period_col])

    df["prev_loads"] = df.groupby("customer_name")[loads_col].shift(1)
    df["change_pct"] = df.apply(
        lambda r: round((r[loads_col] - r["prev_loads"]) / r["prev_loads"] * 100, 1)
        if pd.notna(r["prev_loads"]) and r["prev_loads"] > 0 else np.nan,
        axis=1,
    )
    # Mark NEW if previous period had no data
    df["change_label"] = df.apply(
        lambda r: "NEW" if pd.isna(r["prev_loads"]) else (f"{r['change_pct']:+.1f}" if pd.notna(r["change_pct"]) else "0"),
        axis=1,
    )

    # Volume Trend: compare to trailing 4-period average
    df["trailing_4_avg"] = df.groupby("customer_name")[loads_col].transform(
        lambda x: x.shift(1).rolling(4, min_periods=1).mean()
    )
    df["volume_trend"] = df.apply(
        lambda r: "UP" if pd.notna(r["trailing_4_avg"]) and r["trailing_4_avg"] > 0 and r[loads_col] > r["trailing_4_avg"] * 1.10
        else ("DOWN" if pd.notna(r["trailing_4_avg"]) and r["trailing_4_avg"] > 0 and r[loads_col] < r["trailing_4_avg"] * 0.90
              else ("N/A" if r[loads_col] == 0 and (pd.isna(r["trailing_4_avg"]) or r["trailing_4_avg"] == 0) else "STABLE")),
        axis=1,
    )

    # Service Risk
    df["service_risk"] = df["otd"].apply(
        lambda x: "AT RISK" if pd.notna(x) and x < 0.90 else ("N/A" if pd.isna(x) else "OK")
    )

    return df


# ------------------------------------------------------------------
# 5. MONTHLY AGGREGATION + RUN-RATE
# ------------------------------------------------------------------

def _add_run_rate(monthly_df):
    """
    For the current (incomplete) month, project month-end totals
    based on daily rate so far.
    """
    if monthly_df.empty:
        return monthly_df

    today = datetime.now()
    current_month = today.strftime("%Y-%m-01")
    days_elapsed = today.day
    days_in_month = 28  # conservative estimate

    # Determine actual days in current month
    if today.month == 12:
        next_month = datetime(today.year + 1, 1, 1)
    else:
        next_month = datetime(today.year, today.month + 1, 1)
    days_in_month = (next_month - datetime(today.year, today.month, 1)).days

    monthly_df["is_current_month"] = monthly_df["month_start"] == current_month

    if days_elapsed > 0:
        monthly_df["run_rate_loads"] = monthly_df.apply(
            lambda r: int(r["loads"] / days_elapsed * days_in_month) if r["is_current_month"] else r["loads"],
            axis=1,
        )
        monthly_df["run_rate_revenue"] = monthly_df.apply(
            lambda r: round(r["revenue"] / days_elapsed * days_in_month, 0) if r["is_current_month"] else r["revenue"],
            axis=1,
        )
    else:
        monthly_df["run_rate_loads"] = monthly_df["loads"]
        monthly_df["run_rate_revenue"] = monthly_df["revenue"]

    return monthly_df


# ------------------------------------------------------------------
# 6. RISK FLAG ENGINE
# ------------------------------------------------------------------

def compute_risk_flags(weekly_customer, completed_df, selected_week):
    """
    Compute risk flags matching Metabase logic:
      - STALE ACCOUNT (0 LOADS): 0 loads this week, had loads in trailing 12 weeks
      - HIGH REVENUE + POOR SERVICE: Revenue share >= 5% AND OTD < 90%
      - HIGH REVENUE + DECLINING VOLUME: Revenue share >= 5% AND WoW change < -20%
      - SHARP WOW DROP: WoW load change < -30%
      - BELOW TRAILING AVERAGE: Current loads < 70% of trailing 4-week avg
    """
    if weekly_customer.empty:
        return pd.DataFrame()

    current = weekly_customer[weekly_customer["week_start"] == selected_week].copy()
    if current.empty:
        return pd.DataFrame()

    total_revenue = current["revenue"].sum()
    current["revenue_share"] = current["revenue"] / total_revenue * 100 if total_revenue > 0 else 0

    # Trailing 12-week history for stale detection
    all_weeks = sorted(weekly_customer["week_start"].unique())
    week_idx = all_weeks.index(selected_week) if selected_week in all_weeks else -1
    trailing_weeks = all_weeks[max(0, week_idx - 12):week_idx] if week_idx > 0 else []

    trailing = weekly_customer[weekly_customer["week_start"].isin(trailing_weeks)]
    trailing_loads_by_cust = trailing.groupby("customer_name")["loads"].sum()

    risks = []
    for _, row in current.iterrows():
        flags = []
        cust = row["customer_name"]
        loads = row["loads"]
        rev_share = row["revenue_share"]
        otd = row["otd"]
        change = row["change_pct"] if pd.notna(row.get("change_pct")) else 0
        trailing_had_loads = trailing_loads_by_cust.get(cust, 0) > 0

        # STALE ACCOUNT
        if loads == 0 and trailing_had_loads:
            flags.append("STALE ACCOUNT (0 LOADS)")

        # HIGH REVENUE + POOR SERVICE
        if rev_share >= 5 and pd.notna(otd) and otd < 0.90:
            flags.append("HIGH REVENUE + POOR SERVICE")

        # HIGH REVENUE + DECLINING VOLUME
        if rev_share >= 5 and pd.notna(change) and change < -20:
            flags.append("HIGH REVENUE + DECLINING VOLUME")

        # SHARP WOW DROP
        if pd.notna(change) and change < -30:
            flags.append("SHARP WOW DROP")

        # BELOW TRAILING AVERAGE
        t4 = row.get("trailing_4_avg", 0)
        if pd.notna(t4) and t4 > 0 and loads < t4 * 0.70:
            flags.append("BELOW TRAILING AVERAGE")

        if flags:
            risks.append({
                "customer_name": cust,
                "weekly_revenue": row["revenue"],
                "weekly_loads": loads,
                "wow_change_pct": change,
                "on_time_delivery_pct": round(otd * 100, 1) if pd.notna(otd) else None,
                "risk_flag": " | ".join(flags),
            })

    return pd.DataFrame(risks) if risks else pd.DataFrame()


def compute_lane_risks(completed_df, selected_week):
    """
    Lane-level risk attribution: which lanes are driving risk
    for each flagged customer.
    """
    if completed_df.empty:
        return pd.DataFrame()

    week_loads = completed_df[completed_df["week_start"] == selected_week]
    if week_loads.empty:
        return pd.DataFrame()

    lane_cust = week_loads.groupby(["customer_name", "lane"]).agg(
        volume=("load_id", "count"),
        revenue=("pricing_total", "sum"),
        otd=("on_time_delivery", "mean"),
    ).reset_index()

    lane_cust["otd_pct"] = (lane_cust["otd"] * 100).round(1)
    lane_cust = lane_cust.sort_values(["customer_name", "revenue"], ascending=[True, False])
    return lane_cust


# ------------------------------------------------------------------
# 7. FULL TRANSFORM PIPELINE
# ------------------------------------------------------------------

def transform_loads(raw_loads_or_df, customer_master_or_df):
    """
    Full transform pipeline.
    Returns dict with all DataFrames needed by the dashboard.
    """
    if isinstance(raw_loads_or_df, list):
        df = flatten_loads(raw_loads_or_df)
    else:
        df = raw_loads_or_df.copy()
        if "lane" not in df.columns and "pickup_city" in df.columns:
            df["lane"] = (
                df["pickup_city"].fillna("Unknown") + ", " +
                df.get("pickup_state", pd.Series("CA", index=df.index)).fillna("??") +
                " \u2192 " +
                df["delivery_city"].fillna("Unknown") + ", " +
                df.get("delivery_state", pd.Series("CA", index=df.index)).fillna("??")
            )
        if "bco_derived" not in df.columns:
            df["bco_derived"] = df.get("bco", "Direct")
        if "exception_label" not in df.columns:
            if "exception_code" in df.columns:
                df["exception_label"] = df["exception_code"].apply(
                    lambda x: "Uncontrollable Event" if x and str(x).strip() else ""
                )
            else:
                df["exception_label"] = ""
        if "month_start" not in df.columns:
            for date_col in ["completed_date", "created_date", "week_start"]:
                if date_col in df.columns:
                    df["month_start"] = pd.to_datetime(df[date_col], errors="coerce").dt.strftime("%Y-%m-01")
                    break

    if isinstance(customer_master_or_df, list):
        customer_master = build_customer_master(customer_master_or_df)
    else:
        customer_master = customer_master_or_df.copy()

    # For live API data, flatten_loads() already filters to loads with
    # loadCompletedAt, so every row here is a delivered load.
    # For sample data (DataFrame input), fall back to status filtering.
    if isinstance(raw_loads_or_df, list):
        completed_df = df.copy()  # already filtered by flatten_loads
    else:
        completed_statuses = {"COMPLETED", "BILLING", "APPROVED", "Delivered"}
        completed_df = df[df["status"].isin(completed_statuses)].copy() if "status" in df.columns else df.copy()
        if completed_df.empty:
            completed_df = df.copy()

    # Weekly aggregation
    weekly_customer = _skeleton_join(completed_df, customer_master, "week_start")
    if not weekly_customer.empty:
        weekly_customer = _add_wow_and_flags(weekly_customer, "week_start")

    # Monthly aggregation
    monthly_customer = _skeleton_join(completed_df, customer_master, "month_start")
    if not monthly_customer.empty:
        monthly_customer = _add_wow_and_flags(monthly_customer, "month_start")
        monthly_customer = _add_run_rate(monthly_customer)

    # Lane performance (weekly)
    lane_df = pd.DataFrame()
    if not completed_df.empty and "lane" in completed_df.columns:
        lane_df = completed_df.groupby(["customer_name", "lane", "week_start"]).agg(
            volume=("load_id", "count"),
            revenue=("pricing_total", "sum"),
            otd=("on_time_delivery", "mean"),
        ).reset_index()
        lane_df["otd_pct"] = (lane_df["otd"] * 100).round(1)

    return {
        "cleaned": completed_df,
        "weekly": weekly_customer,
        "monthly": monthly_customer,
        "lanes": lane_df,
        "customer_master": customer_master,
    }
