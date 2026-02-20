# Missing Data Research Report: PortPro CA/AZ Data Gaps

**Author:** Riley Barrow (Sales Ops)
**Date:** 2026-02-18
**Status:** Investigation Complete — Awaiting API Credentials for Validation

---

## Executive Summary

Two critical data fields — **Pickup City** and **Weight** — are missing or inconsistent in PortPro's custom reporting interface. This report identifies the root causes and proposes API-based fixes that can be implemented without changes to PortPro's core system.

---

## Issue 1: Missing "Pickup City" Field

### What Serena Reported
The PortPro custom report has a **Delivery City** column but no corresponding **Pickup City** field. This prevents lane-level analysis and forces manual backfilling.

### Root Cause Analysis

PortPro's custom reporting interface exposes a limited subset of fields. However, the **full data exists in the API**. The disconnect is between what PortPro's report builder shows vs. what the database stores.

**Evidence from the API:**
- `GET /v1/loads` returns each load with associated location objects
- `GET /v1/shippers` returns shipper/pickup location records with **full address data** including `city`, `state`, `zip`, `address1`
- `GET /v1/terminals` returns terminal records with location data
- The load object references a `shipper_id` or `pickup_location_id` that can be joined to the shipper/terminal tables

### Proposed Fix

**Approach A — Direct API Pull (Recommended):**
```
1. GET /v1/loads  → extract shipper_id / pickup_location reference
2. GET /v1/shippers → build lookup: shipper_id → {city, state}
3. JOIN on shipper_id to attach pickup_city, pickup_state to each load
```

**Approach B — Webhook-Based Enrichment:**
```
1. Configure webhook on `load#created` and `load#info_updated`
2. On each event, pull the full load object including shipper details
3. Store enriched data in Airtable/database with pickup city populated
```

**Approach C — PortPro Custom Report Enhancement:**
- Ask Jeff/Frank if the custom report builder can be configured to include the `Shipper City` field
- This may require PortPro support to add the field to the report template
- Least effort but depends on PortPro's willingness to update

### Data Flow Diagram

```
PortPro Load Record
    ├── reference_number
    ├── customer_id → GET /v1/customers/{id}
    ├── shipper_id  → GET /v1/shippers/{id}  ← PICKUP CITY IS HERE
    │       ├── city: "Long Beach"
    │       ├── state: "CA"
    │       └── address1: "..."
    ├── consignee_id → GET /v1/consignees/{id}  ← DELIVERY CITY
    │       ├── city: "Ontario"
    │       ├── state: "CA"
    │       └── address1: "..."
    └── terminal_id → GET /v1/terminals/{id}
            ├── name: "Port of Long Beach"
            └── city: "Long Beach"
```

### Validation Steps
Once API credentials are obtained:
1. Pull 10 sample loads via `GET /v1/loads?limit=10`
2. For each, check if `shipper` or `pickup_location` object contains city/state
3. Cross-reference with a known load from Serena's manual data to confirm match

---

## Issue 2: Missing "Weight" Field

### What Was Observed
The `weight` field in PortPro's custom report is mostly empty (~60% missing in our analysis). Serena noted this is "kind of worthless."

### Root Cause Analysis

Weight data in drayage TMS systems is typically:
1. **Entered manually** by dispatch or drivers at pickup
2. **Populated from customer tender/EDI** data (if the shipper provides it)
3. **Updated post-delivery** from BOL (Bill of Lading) scans

The gaps suggest:
- **Driver input gap**: Drivers are not consistently entering weight at pickup
- **No EDI backfill**: Customer tenders may not include weight for all shipments
- **BOL scanning gap**: Post-delivery weight updates are not being captured in PortPro

### Proposed Fix

**Short-term — API-based Backfill:**
```
1. GET /v1/loads → check for loads with null weight
2. GET /v1/loads/{ref}/documents → check if BOL document exists
3. If BOL exists, weight may be in the document metadata
4. Manual/semi-automated extraction from BOL PDFs
```

**Medium-term — Process Change:**
- Work with Frank/Ops to make weight a **required field** at load completion in PortPro
- Add weight entry to the driver's mobile app workflow
- This is the only sustainable fix — API can't create data that doesn't exist

**Long-term — EDI/Tender Integration:**
- If customers provide weight in their tender/EDI data, ensure PortPro captures it
- The `POST /v1/tenders` endpoint accepts weight — verify customer tenders include it

### Impact Assessment

| Use Case | Impact of Missing Weight |
|----------|------------------------|
| Revenue analysis | Low — revenue is rate-based, not weight-based in drayage |
| Compliance (overweight) | High — can't flag overweight loads without data |
| Customer reporting | Medium — some BCOs want weight in their reports |
| Lane analysis | Low — volume and OTD are more critical |

**Recommendation:** Prioritize Pickup City fix (high impact) over Weight fix (medium impact). Weight requires a process change, not just a technical fix.

---

## Issue 3: Inconsistent Pricing/Revenue Data

### What Was Observed
- Some loads show $178 or similar low amounts (likely just the FSC component)
- Charge code fields (FSC, Chassis) appear as separate line items
- Paid amount field is often empty

### Root Cause
PortPro stores charges at the **charge code level**, not as a single "total revenue" field. The custom report may be pulling only the base rate, not the full charge set.

### Proposed Fix
```
GET /v1/loads → check for charge_set or pricing object
GET /v1/get-charge-codes → get all charge code definitions
GET /v1/invoices?reference_number={load_ref} → get invoiced total

Revenue = SUM of all charge codes per load (Base + FSC + Chassis + Accessorials)
```

The `GET /v1/invoices` endpoint is the most reliable source for total revenue per load.

---

## Issue 4: Bad/Incomplete Load IDs

### What Serena Reported
Some loads have incomplete or missing Load IDs, making it impossible to match across systems.

### Investigation
- Load IDs starting with 'M' appear to be broker loads (mapped to BCO logic)
- Some loads may be in "draft" or "pending" status without finalized IDs
- The `GET /v1/loads` endpoint returns `reference_number` which is the canonical ID

### Proposed Fix
- Use `reference_number` from the API as the primary key (not the custom report's Load ID)
- Cross-reference with `GET /v1/audit/load` to check if loads were created with incomplete data
- Flag to Jeff: loads created without reference numbers should be a validation error in PortPro

---

## Action Items

| # | Action | Owner | Priority | Dependency |
|---|--------|-------|----------|------------|
| 1 | Obtain API access token from Jeff/Frank (super-admin required) | Riley | **P0** | None |
| 2 | Validate pickup city exists in API shipper objects | Riley | P0 | #1 |
| 3 | Build automated shipper→city lookup in dashboard pipeline | Riley | P1 | #2 |
| 4 | Ask Jeff: can custom report add Shipper City field? | Riley/Serena | P1 | None |
| 5 | Ask Frank: make weight a required field at load completion | Serena | P2 | None |
| 6 | Validate invoice endpoint for accurate revenue totals | Riley | P1 | #1 |
| 7 | Follow up on Airtable integration status with Doug | Riley | P1 | None |

---

## API Reference Quick Guide

| What You Need | Endpoint | Notes |
|---------------|----------|-------|
| All loads (with filters) | `GET /v1/loads` | Max 50/page, supports date/status filters |
| Customer master list | `GET /v1/customers` | Use for always-visible join |
| Pickup city data | `GET /v1/shippers` | Contains city, state, address |
| Delivery city data | `GET /v1/consignees` | Contains city, state, address |
| Terminal info | `GET /v1/terminals` | Port names → city mapping |
| Revenue/invoices | `GET /v1/invoices` | Most accurate revenue source |
| Charge codes | `GET /v1/get-charge-codes` | FSC, Chassis, Base, etc. |
| Load documents (BOL) | `GET /v1/load-document/` | May contain weight data |
| Webhooks | Settings → Developer Portal | Real-time load event streaming |

**API Docs:** https://documentation.app.portpro.io/
**Auth:** Bearer Token (24hr access, 100-day refresh) — super-admin generates via Developer Portal
