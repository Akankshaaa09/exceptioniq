"""
generate_customers.py

Generates the customer master for Meridian Supply Co.
Source system: Commercial/CRM
Output: data/raw/commercial/customers.csv

Every constant below traces back to a locked value in
docs/01_business_specification.md (Section 5) or
docs/03_data_generation_spec.md (Section 2) — nothing here is
invented on the spot.
"""

import os
import random
from datetime import date

import numpy as np
import pandas as pd
from dateutil.relativedelta import relativedelta
from faker import Faker

# ---- reproducibility ----
SEED = 42
random.seed(SEED)
np.random.seed(SEED)
fake = Faker("en_US")
Faker.seed(SEED)

# ---- locked parameters ----
N_CUSTOMERS = 400  # midpoint of the locked 300-500 range

HISTORY_MONTHS = 15  # midpoint of the locked 12-18 month window
HISTORY_END = date(2026, 8, 31)
HISTORY_START = HISTORY_END - relativedelta(months=HISTORY_MONTHS)

REGIONS = ["Northeast", "Midwest", "South", "West"]
REGION_WEIGHTS = [0.28, 0.27, 0.24, 0.21]

SEGMENTS = ["Standard", "Strategic"]
SEGMENT_WEIGHTS = [0.78, 0.22]  # locked in 03_data_generation_spec.md, Section 2

OUT_PATH = os.path.join(
    os.path.dirname(__file__), "..", "data", "raw", "commercial", "customers.csv"
)


def random_signup_date():
    """
    Customers can exist up to 24 months before the history window starts,
    but must exist at least 1 month before it ends, so every customer has
    room to actually place orders during the window.
    """
    earliest = pd.Timestamp(HISTORY_START - relativedelta(months=24))
    latest = pd.Timestamp(HISTORY_END - relativedelta(months=1))
    delta_days = (latest - earliest).days
    return earliest + pd.Timedelta(days=random.randint(0, delta_days))


def generate_customers(n=N_CUSTOMERS):
    rows = []
    for i in range(1, n + 1):
        rows.append(
            {
                "customer_id": f"CUST{i:05d}",
                "customer_name": fake.unique.company(),
                "region": np.random.choice(REGIONS, p=REGION_WEIGHTS),
                "segment": np.random.choice(SEGMENTS, p=SEGMENT_WEIGHTS),
                "signup_date": random_signup_date(),
                "created_at": pd.Timestamp.now(),
            }
        )
    return pd.DataFrame(rows)


if __name__ == "__main__":
    df = generate_customers()
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    df.to_csv(OUT_PATH, index=False)

    print(f"Generated {len(df)} customers -> {OUT_PATH}\n")
    print("Segment distribution (target: 78% Standard / 22% Strategic):")
    print(df["segment"].value_counts(normalize=True).round(3))
    print("\nRegion distribution (target: ~28/27/24/21):")
    print(df["region"].value_counts(normalize=True).round(3))
    print("\nSignup date range:", df["signup_date"].min().date(), "to", df["signup_date"].max().date())
    print("\nUnique customer names:", df["customer_name"].nunique(), "/", len(df))
    print("\nSample rows:")
    print(df.head())
