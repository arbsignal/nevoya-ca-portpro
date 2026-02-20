# Overview: CA/AZ Performance Dashboard (PortPro)

This document provides a summary of the new **CA/AZ Performance Dashboard**, designed to mirror the Metabase TX dashboard. Use this guide to review current functionality and the remaining data requirements needed for live deployment for Tuesday meetings.

---

## 1. Dashboard Sections: What You're Seeing

### A. Executive Snapshot (The "Big Numbers")
- **Total Loads / Revenue:** High-level summary of volume and dollars for the selected week.
- **On-Time Pickup (OTP) & Delivery (OTD):** Service percentage metrics.
- **Uncontrollable Events:** Total count of delays caused by external factors (Port congestion, etc.).
- **Deltas:** Compares current week performance against the previous week.

### B. Customer Performance Table (The "Main Table")
- **Always-Visible Logic:** Shows every active customer, even if they moved **0 loads** that week.
- **Service Risk:** Automatically flags customers as "At Risk" if their on-time delivery falls below 90%.
- **Tiers:** Groups customers by importance (Tier 1 = Strategic, Tier 2 = Growth, Tier 3 = Transactional).

### C. Performance by Lane (City-to-City)
- **Simplified Views:** Aggregates data by "City, State" (e.g., Los Angeles, CA).
- **Facility Stripping:** Removes messy terminal/warehouse names to show total volume between regions.

### D. Performance by BCO (Beneficial Cargo Owner)
- **Broker Analysis:** Specifically identifies loads from broker accounts (like CHR) and breaks down performance by the actual cargo owner.

---

## 2. Interactive Filters
To keep the view clean and accurate, all filters are **dropdown menus** only:
- **Select Week:** View data for any of the last 12 weeks.
- **Filter by Customer:** Drill down into specific accounts.
- **Filter by Tier:** View all strategic (Tier 1) accounts at once.
- **Filter by Lane/BCO:** Deep dive into specific geographies or cargo owners.

---

## 3. What Is Currently Missing
While the prototype is functional, the following data points are currently obscured or inconsistent:
- **Pickup City:** Not currently flowing through standard PortPro reports. We need to backfill this using the "Shippers" API.
- **Weight:** Data is inconsistent/empty for many CA/AZ loads.
- **Accurate Revenue:** Some loads show partial totals (e.g., only fuel surcharges). We need to verify if the dashboard should pull from "Invoices" rather than "Loads."

---

## 4. Immediate Action Items (The "Need")
To move from a prototype to a live, automated tool, we need the following from the tech team:
1. **API Access Tokens:** We need a live Access & Refresh token from the PortPro Developer Portal.
2. **Revenue Logic Confirmation:** Confirm which field in PortPro represents the "all-in" revenue.
3. **BCO Data Entry:** Standardize using the "Reference Number" or similar field to ensure the BCO mapping is 100% accurate.

---

**Goal:** Have live data flowing for the upcoming Tuesday meeting to eliminate manual Excel backfilling.
