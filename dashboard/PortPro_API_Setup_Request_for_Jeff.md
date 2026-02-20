# PortPro API Access & Data Setup Request

**From:** Riley Barrow (Sales Ops)
**To:** Jeff
**Date:** February 18, 2026
**Re:** Steps needed to automate the CA/AZ Performance Dashboard

---

Hey Jeff,

Following up from the conversation with Serena — I've built a working prototype of the CA/AZ Performance Dashboard that mirrors what we have in Metabase for Texas. It's functional with sample data right now, but I need a few things from you / the PortPro side to connect it to live data and get it ready for Serena's Tuesday meetings.

---

## What I Need

### 1. API Access Token (Priority: Urgent)

I need a **Bearer Token** (Access Token + Refresh Token) generated from PortPro's Developer Portal.

- **Who can do this:** Only a **super-admin** account can generate API tokens
- **Where:** PortPro Developer Portal → [https://developer.portpro.io/](https://developer.portpro.io/)
- **What I need back:** Two strings — an `access_token` and a `refresh_token`
- **Security:** These will be stored locally and not shared. The access token expires every 24 hours and auto-refreshes.

If you're not sure how to generate these, PortPro's docs are here: [https://documentation.app.portpro.io/](https://documentation.app.portpro.io/) — look under the Authentication section for "Retrieve Token."

---

### 2. Confirm Pickup City Data in the API (Priority: High)

Serena and I noticed the custom report doesn't have a **Pickup City** field — only Delivery City. I believe the pickup city data *does* exist in the API under the **Shippers** endpoint (`GET /v1/shippers`), which should return city/state for each shipper record.

**Can you confirm:**
- When a load is created, does it get linked to a shipper record that includes the pickup city and state?
- Or is pickup location stored somewhere else in the load object (e.g., `pickup_location`, `origin`, or a terminal reference)?

If the data is there, I can pull it automatically. If it's genuinely missing, we may need to look at how loads are being created.

---

### 3. Clarify Revenue / Charge Code Structure (Priority: Medium)

We noticed some loads showing low dollar amounts (like $178) that look like they might be just the fuel surcharge rather than the full rate. A few questions:

- Is `pricing_total` on the load object the **all-in revenue** (base + FSC + chassis + accessorials)?
- Or do I need to pull from the **Invoices** endpoint (`GET /v1/invoices`) to get the accurate total?
- What's the best way to get total revenue per load via the API?

---

### 5. Bad / Incomplete Load IDs (Priority: Medium)

We found a few loads with missing or incomplete Load IDs. Serena shared some specific examples with you already. Two questions:
- Is `reference_number` the canonical unique ID I should use as the primary key when pulling from the API?
- Should loads ever be created without a reference number, or is that a data entry issue we need to clean up?

---

### 6. Airtable Integration Status (Priority: Info)

I saw Doug set up an Airtable trial with some initial PortPro data. Just want to make sure we're not duplicating work:
- Is the Airtable connection pulling from the same API I'd be using?
- Is there a plan for what Airtable will own vs. what the dashboard will own?

Happy to coordinate with Doug on this — just want to make sure we're aligned.

---

## What's Already Done

For context, here's what the dashboard prototype already handles:

| Feature | Status |
|---------|--------|
| Executive Snapshot (Total Loads, Revenue, OTP/OTD) | Built |
| Customer Performance Table (all active customers, WoW trends) | Built |
| Lane Performance (City-to-City, facility names stripped) | Built |
| BCO Breakdown (broker load identification) | Built |
| 12-Week Trend Charts | Built |
| Uncontrollable Events tracking | Built |
| Always-Visible Customers (0-load weeks shown) | Built |
| Dropdown filters (Customer, Lane, BCO, Tier) | Built |
| PortPro API client (ready for credentials) | Built — just needs tokens |

Once I get the API token, I can have live data flowing within a day.

---

## TL;DR — Action Items for Jeff

| # | What I Need | How Long It Takes | Urgency |
|---|-------------|-------------------|---------|
| 1 | Generate API Access + Refresh Token from Developer Portal | ~5 min | **Urgent** |
| 3 | Clarify if `pricing_total` = full revenue or just base rate | Quick answer | Medium |
| 5 | Confirm `reference_number` is the right primary key | Quick answer | Medium |
| 6 | Airtable sync — are we overlapping? | FYI / coordination | Low |

Happy to jump on a quick call if it's easier to walk through any of this. Thanks Jeff.

— Riley
