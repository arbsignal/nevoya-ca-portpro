# CA/AZ Performance Dashboard — Nevoya Sales Ops

Interactive dashboard mirroring the Metabase V1 structure for PortPro CA/AZ data.

## Quick Start

```bash
cd C:/Users/rbarr/OneDrive/Desktop/Nevoya/SalesOps/port_pro
streamlit run dashboard/app.py
```

Opens in browser at `http://localhost:8501`

## Files

| File | Purpose |
|------|---------|
| `app.py` | Streamlit dashboard (main entry point) |
| `portpro_api.py` | PortPro REST API client (Bearer token auth) |
| `data_engineering.py` | Cleaning: lane aggregation, BCO mapping, exception labeling, LEFT JOIN |
| `sample_data.py` | Realistic sample data for demo (replace with live API) |
| `MISSING_DATA_REPORT.md` | Research on missing Weight/Pickup City fields + API fix proposals |

## Connecting to Live PortPro Data

1. Get API tokens from Jeff or Frank (super-admin required)
2. Create `dashboard/.env.json`:
   ```json
   {
     "access_token": "YOUR_TOKEN",
     "refresh_token": "YOUR_REFRESH_TOKEN"
   }
   ```
3. Restart the dashboard — it will auto-detect credentials and pull live data

## Dashboard Sections

1. **Executive Snapshot** — Total Loads, Revenue, Avg Rev, OTP%, OTD%, Uncontrollable Events
2. **Customer Performance Table** — All active customers (including 0-load weeks), WoW change, service risk
3. **Performance by Lane** — City-to-City aggregation (facility names stripped)
4. **Performance by BCO** — Broker load breakdown by Beneficial Cargo Owner
5. **Weekly Trends** — 12-week time series with customer stacked view

## Data Engineering Rules Applied

- **Lane Aggregation**: "LAX Terminal 4" and "Port of Los Angeles" both map to "Los Angeles, CA"
- **BCO Mapping**: Load IDs starting with 'M' → broker loads → BCO derived from reference fields
- **Uncontrollable Events**: All non-Nevoya exceptions (TERM-CLOSE, PORT-CONG, etc.) standardized
- **Always-Visible Customers**: LEFT JOIN from Customer Master ensures 0-load customers appear
- **Service Risk**: Flagged when Controllable OTD < 90%
- **Weekly Range**: Monday–Sunday
