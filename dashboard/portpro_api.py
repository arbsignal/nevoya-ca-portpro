"""
PortPro API Client for Nevoya Sales Ops Dashboard
==================================================
Connects to PortPro's REST API (Carrier) to pull loads and customers.

API Base: https://api1.app.portpro.io/v1
Auth:     Bearer Token (access token valid ~30 days)
Docs:     https://documentation.app.portpro.io/

Endpoint notes (discovered via probing):
  - Loads:     GET /v1/loads      (pagination via ?limit=N&skip=N)
  - Customers: GET /v1/customer   (singular, NOT /customers)
  - Invoices:  GET /v1/invoices
  - /v1/shippers, /v1/consignees, /v1/terminals all return 404
    -> shipper/consignee data is embedded in the load object instead
"""

import os
import json
import time
import requests
from datetime import datetime, timedelta
from pathlib import Path

BASE_URL = "https://api1.app.portpro.io/v1"
CONFIG_PATH = Path(__file__).parent / ".env.json"


def load_config():
    """Load API credentials from .env.json, environment variables, or st.secrets."""
    config = {
        "access_token": os.environ.get("PORTPRO_ACCESS_TOKEN", ""),
        "refresh_token": os.environ.get("PORTPRO_REFRESH_TOKEN", ""),
    }
    # Streamlit Cloud stores secrets via st.secrets (TOML-based)
    try:
        import streamlit as st
        if hasattr(st, "secrets"):
            config["access_token"] = config["access_token"] or st.secrets.get("PORTPRO_ACCESS_TOKEN", "")
            config["refresh_token"] = config["refresh_token"] or st.secrets.get("PORTPRO_REFRESH_TOKEN", "")
    except Exception:
        pass
    # Local .env.json overrides everything when present
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH) as f:
            file_config = json.load(f)
            config.update({k: v for k, v in file_config.items() if v})
    return config


def save_config(config):
    """Persist tokens to .env.json (skipped on read-only filesystems like Vercel)."""
    try:
        with open(CONFIG_PATH, "w") as f:
            json.dump(config, f, indent=2)
    except OSError:
        pass


class PortProClient:
    """Thin wrapper around PortPro REST API v1."""

    def __init__(self, access_token=None, refresh_token=None):
        config = load_config()
        self.access_token = access_token or config.get("access_token", "")
        self.refresh_token = refresh_token or config.get("refresh_token", "")
        self.base_url = BASE_URL
        self._session = requests.Session()
        self._session.headers.update({
            "Content-Type": "application/json",
            "Accept": "application/json",
        })
        if self.access_token:
            self._session.headers["Authorization"] = f"Bearer {self.access_token}"

    @property
    def is_configured(self):
        return bool(self.access_token)

    def _refresh_access_token(self):
        """Use refresh token to get a new access token."""
        if not self.refresh_token:
            raise ValueError("No refresh token available.")
        resp = self._session.get(
            f"{self.base_url}/token",
            headers={"Authorization": f"Bearer {self.refresh_token}"},
        )
        resp.raise_for_status()
        data = resp.json()
        self.access_token = data.get("accessToken", data.get("access_token", ""))
        self._session.headers["Authorization"] = f"Bearer {self.access_token}"
        save_config({
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
        })

    def _request(self, method, endpoint, params=None, json_body=None, retry=True):
        """Make an authenticated API request with auto-refresh on 401."""
        url = f"{self.base_url}{endpoint}"
        resp = self._session.request(method, url, params=params, json=json_body, timeout=30)
        if resp.status_code == 401 and retry and self.refresh_token:
            self._refresh_access_token()
            resp = self._session.request(method, url, params=params, json=json_body, timeout=30)
        resp.raise_for_status()
        return resp.json()

    # ------------------------------------------------------------------
    # Core Endpoints
    # ------------------------------------------------------------------

    def get_loads(self, limit=50, skip=0):
        """GET /v1/loads — Retrieve loads. Pagination uses skip, not page."""
        params = {"limit": limit, "skip": skip}
        return self._request("GET", "/loads", params=params)

    def get_all_loads(self, page_size=50):
        """Paginate through ALL loads using skip-based pagination.

        The API caps at 50 per page, so we use that as default and keep
        paginating until an empty page is returned.
        """
        all_loads = []
        skip = 0
        while True:
            data = self.get_loads(limit=page_size, skip=skip)
            loads = data.get("data", [])
            if not loads:
                break
            all_loads.extend(loads)
            skip += len(loads)
            if len(loads) < page_size:
                break
            time.sleep(0.3)
        return all_loads

    def get_customers(self):
        """GET /v1/customer (singular) — Retrieve customer master list."""
        data = self._request("GET", "/customer")
        return data.get("data", [])

    def get_invoices(self, limit=50, skip=0):
        """GET /v1/invoices"""
        params = {"limit": limit, "skip": skip}
        return self._request("GET", "/invoices", params=params)

    # ------------------------------------------------------------------
    # Connectivity Test
    # ------------------------------------------------------------------

    def test_connection(self):
        """Quick connectivity check — pulls first 5 loads."""
        try:
            data = self.get_loads(limit=5, skip=0)
            count = data.get("count", 0)
            sample = data.get("data", [])
            return {
                "status": "connected",
                "total_loads": count,
                "sample_refs": [l.get("reference_number") for l in sample[:3]],
            }
        except requests.exceptions.HTTPError as e:
            return {"status": "auth_error", "code": e.response.status_code, "detail": str(e)}
        except requests.exceptions.ConnectionError as e:
            return {"status": "connection_failed", "detail": str(e)}
        except Exception as e:
            return {"status": "error", "detail": str(e)}


if __name__ == "__main__":
    client = PortProClient()
    if not client.is_configured:
        print("No credentials found.")
        print("Create dashboard/.env.json with:")
        print('  {"access_token": "YOUR_TOKEN", "refresh_token": "YOUR_REFRESH_TOKEN"}')
    else:
        result = client.test_connection()
        print(json.dumps(result, indent=2, default=str))
