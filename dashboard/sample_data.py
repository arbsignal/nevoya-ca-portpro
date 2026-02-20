"""
Sample Data Generator for CA/AZ Performance Dashboard
=====================================================
Generates realistic sample data mirroring PortPro's schema for
development/demo purposes. Replace with live API data once
credentials are configured.

Mirrors the data structure from Serena's custom report:
- Load ID, Completed Date, Customer, Pickup Location, Delivery Location
- Pricing Total, Load Type, Weight, Reference Number
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import random

# ------------------------------------------------------------------
# Reference Data (mirrors PortPro's CA/AZ drayage operations)
# ------------------------------------------------------------------

CUSTOMERS = [
    {"id": "C001", "name": "ITS Logistics", "tier": 1, "is_broker": True},
    {"id": "C002", "name": "CH Robinson", "tier": 1, "is_broker": True},
    {"id": "C003", "name": "Coyote Logistics", "tier": 2, "is_broker": True},
    {"id": "C004", "name": "XPO Logistics", "tier": 2, "is_broker": True},
    {"id": "C005", "name": "Echo Global", "tier": 2, "is_broker": True},
    {"id": "C006", "name": "TQL", "tier": 3, "is_broker": True},
    {"id": "C007", "name": "NFI Industries", "tier": 2, "is_broker": False},
    {"id": "C008", "name": "Target", "tier": 1, "is_broker": False},
    {"id": "C009", "name": "Amazon", "tier": 1, "is_broker": False},
    {"id": "C010", "name": "IMC Logistics", "tier": 3, "is_broker": True},
]

# BCO mapping for broker accounts (derived from Load ID patterns or reference fields)
BCO_MAP = {
    "ITS Logistics": ["Coca-Cola", "PepsiCo", "Procter & Gamble", "Unilever"],
    "CH Robinson": ["Samsung", "LG Electronics", "Nike", "Home Depot"],
    "Coyote Logistics": ["Costco", "Walmart", "Dollar General"],
    "XPO Logistics": ["IKEA", "Wayfair", "Ashley Furniture"],
    "Echo Global": ["Samsung", "Sony", "Panasonic"],
    "TQL": ["General Mills", "Kraft Heinz"],
    "IMC Logistics": ["Various"],
}

# CA/AZ Pickup locations (origin) — these simulate PortPro's pickup_location field
# which contains facility names, not clean city names
PICKUP_LOCATIONS_RAW = [
    ("Port of Long Beach - Pier J", "Long Beach", "CA"),
    ("Port of Long Beach Terminal Island", "Long Beach", "CA"),
    ("Port of Los Angeles - APM Terminal", "Los Angeles", "CA"),
    ("Port of Los Angeles - Everport Terminal", "Los Angeles", "CA"),
    ("LAX Port Facility", "Los Angeles", "CA"),
    ("Port of Oakland - TraPac Terminal", "Oakland", "CA"),
    ("Port of Oakland - SSA Terminal", "Oakland", "CA"),
    ("Phoenix Intermodal Yard", "Phoenix", "AZ"),
    ("Tucson Rail Depot", "Tucson", "AZ"),
    ("ITS Carson Yard", "Carson", "CA"),
    ("Maersk Warehouse Long Beach", "Long Beach", "CA"),
    ("OOCL Terminal Long Beach", "Long Beach", "CA"),
]

# Delivery locations
DELIVERY_LOCATIONS_RAW = [
    ("Amazon Fulfillment Center ONT8", "Ontario", "CA"),
    ("Target DC Fontana", "Fontana", "CA"),
    ("Costco Regional DC Rancho Cucamonga", "Rancho Cucamonga", "CA"),
    ("Home Depot RDC Perris", "Perris", "CA"),
    ("Walmart DC Riverside", "Riverside", "CA"),
    ("IKEA Distribution Center Lebec", "Lebec", "CA"),
    ("Nike Distribution Center San Bernardino", "San Bernardino", "CA"),
    ("Samsung Warehouse Chino", "Chino", "CA"),
    ("Dollar General DC Lebec", "Lebec", "CA"),
    ("Phoenix Distribution Hub", "Phoenix", "AZ"),
    ("Tucson Warehouse District", "Tucson", "AZ"),
    ("FedEx Ground Bloomington", "Bloomington", "CA"),
    ("UPS Freight Ontario", "Ontario", "CA"),
    ("Inland Empire Transload Facility", "Redlands", "CA"),
]

# Uncontrollable event types (matching the Wiki's exception codes)
UNCONTROLLABLE_EVENTS = [
    ("TERM-CLOSE", "Terminal closure (unscheduled)"),
    ("VESSEL-DELAY", "Container not available — vessel delay"),
    ("CHASSIS-NA", "No chassis available at terminal"),
    ("PORT-CONG", "Port congestion — gate delays >2 hours"),
    ("DUAL-OVERAGE", "Dual transaction exceeded appointment window"),
    ("WX-EVENT", "Weather event"),
    ("SHIPPER-DELAY", "Shipper/receiver caused delay"),
]


def generate_load_id(customer_name, index):
    """
    Generate a load ID. IDs starting with 'M' indicate broker loads
    (used for BCO mapping logic).
    """
    prefix = "M" if customer_name in BCO_MAP else "N"
    return f"{prefix}{1000 + index}"


def generate_sample_loads(weeks_back=12, seed=42):
    """
    Generate realistic load data for the past N weeks.
    Returns a DataFrame matching PortPro's export structure.
    """
    rng = np.random.default_rng(seed)
    random.seed(seed)
    records = []
    load_counter = 0

    today = datetime.now()
    # Align to most recent Monday
    start_of_current_week = today - timedelta(days=today.weekday())

    for week_offset in range(weeks_back, 0, -1):
        week_start = start_of_current_week - timedelta(weeks=week_offset)

        for cust in CUSTOMERS:
            # Base weekly volume by tier
            if cust["tier"] == 1:
                base_loads = rng.integers(15, 30)
            elif cust["tier"] == 2:
                base_loads = rng.integers(5, 15)
            else:
                base_loads = rng.integers(0, 6)

            # Add some WoW variance
            variance = rng.normal(0, 0.15)
            num_loads = max(0, int(base_loads * (1 + variance)))

            for i in range(num_loads):
                load_counter += 1
                load_id = generate_load_id(cust["name"], load_counter)

                # Random day within the week
                day_offset = int(rng.integers(0, 7))
                load_date = week_start + timedelta(days=int(day_offset))

                # Pickup and delivery
                pickup = random.choice(PICKUP_LOCATIONS_RAW)
                delivery = random.choice(DELIVERY_LOCATIONS_RAW)

                # Revenue (drayage typically $200-$800 per load)
                base_rate = rng.uniform(250, 750)
                fsc = rng.uniform(20, 80)  # fuel surcharge
                pricing_total = round(base_rate + fsc, 2)

                # On-time flags
                otp = 1 if rng.random() > 0.12 else 0
                otd = 1 if rng.random() > 0.10 else 0

                # Uncontrollable events (~15% of loads)
                has_exception = rng.random() < 0.15
                exception_code = ""
                exception_desc = ""
                if has_exception:
                    exc = random.choice(UNCONTROLLABLE_EVENTS)
                    exception_code = exc[0]
                    exception_desc = exc[1]
                    # Uncontrollable events often cause late delivery
                    if rng.random() < 0.7:
                        otd = 0

                # BCO mapping for broker loads
                bco = ""
                if cust["is_broker"] and cust["name"] in BCO_MAP:
                    bco = random.choice(BCO_MAP[cust["name"]])

                # Weight — intentionally sparse (~40% missing, mirroring PortPro gap)
                weight = round(rng.uniform(20000, 45000), 0) if rng.random() > 0.40 else None

                # Pickup appointment (sometimes different from completed date)
                pickup_appt = load_date - timedelta(days=int(rng.integers(0, 3)))

                records.append({
                    "load_id": load_id,
                    "reference_number": f"REF-{load_counter:05d}",
                    "customer_name": cust["name"],
                    "customer_id": cust["id"],
                    "customer_tier": cust["tier"],
                    "is_broker": cust["is_broker"],
                    "bco": bco,
                    "pickup_location_raw": pickup[0],
                    "pickup_city": pickup[1],
                    "pickup_state": pickup[2],
                    "delivery_location_raw": delivery[0],
                    "delivery_city": delivery[1],
                    "delivery_state": delivery[2],
                    "pickup_appointment": pickup_appt.strftime("%Y-%m-%d"),
                    "completed_date": load_date.strftime("%Y-%m-%d"),
                    "week_start": week_start.strftime("%Y-%m-%d"),
                    "pricing_total": pricing_total,
                    "weight_lbs": weight,
                    "load_type": random.choice(["Import", "Export", "Transload"]),
                    "on_time_pickup": otp,
                    "on_time_delivery": otd,
                    "exception_code": exception_code,
                    "exception_description": exception_desc,
                    "status": "Delivered",
                })

    return pd.DataFrame(records)


def generate_customer_master():
    """
    Generate the Customer Master List for the LEFT JOIN logic.
    This ensures all active customers appear even with 0 loads.
    """
    return pd.DataFrame(CUSTOMERS)


if __name__ == "__main__":
    df = generate_sample_loads()
    print(f"Generated {len(df)} sample loads across {df['week_start'].nunique()} weeks")
    print(f"Customers: {df['customer_name'].nunique()}")
    print(f"\nSample columns: {list(df.columns)}")
    print(f"\nWeight coverage: {df['weight_lbs'].notna().mean():.0%}")
    print(f"Pickup city coverage: {df['pickup_city'].notna().mean():.0%}")
    print(f"\nWeekly load counts:")
    print(df.groupby("week_start")["load_id"].count().to_string())
