# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Nevoya SalesOps CA/AZ Performance Dashboard — a Streamlit app that visualizes drayage load performance data from the PortPro TMS API. Built to replace manual Excel reporting for weekly Tuesday sales meetings. Mirrors the structure of an existing Metabase TX dashboard.

## Running the Dashboard

```bash
pip install -r requirements.txt
streamlit run dashboard/app.py
```

The app runs on port 8501. A Dev Container config is included for Codespaces (auto-starts Streamlit on attach).

## Architecture

Three-layer pipeline in `dashboard/`:

1. **`portpro_api.py`** — API client for PortPro REST API v1 (`api1.app.portpro.io`). Handles Bearer token auth with auto-refresh on 401. Paginates loads via skip-based params (max 50/page). Credentials loaded from: environment vars → `st.secrets` → `dashboard/.env.json`.

2. **`data_engineering.py`** — Transforms raw API load objects into dashboard-ready DataFrames. Key pipeline: `flatten_loads()` → `transform_loads()` which produces weekly/monthly customer aggregations, lane breakdowns, and risk flags. Important logic:
   - Address parsing uses `TERMINAL_CITY_MAP` to resolve port terminal names to cities
   - Customer names are normalized (strip punctuation, uppercase) for reliable joins
   - Revenue only counted for loads with a `loadCompletedAt`/`loadCompletedDate` value
   - "Always-visible" customer logic: LEFT JOIN from customer master ensures all customers appear even with 0 loads
   - Risk flags: STALE ACCOUNT, HIGH REVENUE + POOR SERVICE, SHARP WOW DROP, BELOW TRAILING AVERAGE

3. **`app.py`** — Streamlit UI with 7 tabs: Weekly Summary, Monthly Summary, Performance by Lane, Performance by BCO, Trends, Risks & Follow-Ups, Methodology. Dark theme styled to match Metabase. Falls back to `sample_data.py` when API credentials are not configured.

4. **`sample_data.py`** — Generates realistic fake load data for development/demo when no API credentials are available.

## Data Model

Loads flow through: raw API JSON → `flatten_loads()` → flat DataFrame → `transform_loads()` which outputs a dict:
- `cleaned` — all load records with resolved dates
- `weekly` / `monthly` — customer aggregations with WoW/MoM change, volume trends, service risk
- `lanes` — customer x lane x week aggregation
- `customer_master` — deduplicated customer list for skeleton joins

## Credentials

API tokens go in `dashboard/.env.json` (gitignored) or Streamlit secrets (`dashboard/.streamlit/secrets.toml`, also gitignored). Keys: `PORTPRO_ACCESS_TOKEN`, `PORTPRO_REFRESH_TOKEN`. Access tokens expire ~30 days.

## Key Conventions

- Status values from the API are inconsistent in casing; always normalize with `.strip().upper()` before comparison
- Week boundaries use ISO Monday starts (`dt - timedelta(days=dt.weekday())`)
- The PortPro customers endpoint is singular: `/v1/customer` (not `/customers`)
- CSV files in the repo root (e.g., `LOAD-*.csv`) are periodic data exports used for diagnostics
- `tmp/` contains throwaway diagnostic/test scripts, not part of the app
