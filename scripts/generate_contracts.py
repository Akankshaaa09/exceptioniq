"""
generate_contracts.py

Generates one active contract per customer for Meridian Supply Co.
Source system: Commercial/CRM
Output: data/raw/commercial/contracts.csv

This is the table every downstream exception rule checks against:
- max_discount_pct -> unauthorized discount (exception #1)
- sla_fulfillment_days -> late fulfillment (exception #3)
- payment_terms_days -> overdue payment (exception #9)

v1 scope note: exactly one contract per customer is generated. The
data model (02_data_model_and_dictionary.md) supports renewal history
(one customer -> many contracts), but multiple contracts per customer
is deferred - added complexity with no analytical payoff for v1.

Every distribution below traces to 03_data_generation_spec.md, Section 2.
"""

import os
import random
from datetime import date

import numpy as np
import pandas as pd
from dateutil.relativedelta import relativedelta

# ---- reproducibility - same seed as customers/products, same population ----
SEED = 42
random.seed(SEED)
np.random.seed(SEED)

HISTORY_MONTHS = 15
HISTORY_END = date(2026, 8, 31)
HISTORY_START = HISTORY_END - relativedelta(months=HISTORY_MONTHS)

CUSTOMERS_PATH = os.path.join(
    os.path.dirname(__file__), "..", "data", "raw", "commercial", "customers.csv"
)
OUT_PATH = os.path.join(
    os.path.dirname(__file__), "..", "data", "raw", "commercial", "contracts.csv"
)

# locked in 03_data_generation_spec.md, Section 2
PAYMENT_TERMS_BY_SEGMENT = {
    "Standard": {"terms": [30, 45, 60], "weights": [0.70, 0.25, 0.05]},
    "Strategic": {"terms": [30, 45, 60], "weights": [0.30, 0.30, 0.40]},
}
SLA_RANGE_BY_SEGMENT = {
    "Standard": (5, 7),
    "Strategic": (3, 5),
}
DISCOUNT_RANGE_BY_SEGMENT = {
    "Standard": (3, 12),
    "Strategic": (10, 25),
}


def generate_contracts(customers_df):
    rows = []
    for i, cust in enumerate(customers_df.itertuples(), start=1):
        segment = cust.segment
        signup_date = pd.Timestamp(cust.signup_date)

        contract_start = signup_date + pd.Timedelta(days=random.randint(0, 14))
        # 4-6 year duration, deliberately long relative to the 12-18 month
        # order window - guarantees the contract is still active for the
        # entire order-generation period regardless of signup timing.
        contract_end = contract_start + relativedelta(months=random.randint(48, 72))

        terms_cfg = PAYMENT_TERMS_BY_SEGMENT[segment]
        payment_terms_days = int(np.random.choice(terms_cfg["terms"], p=terms_cfg["weights"]))

        sla_lo, sla_hi = SLA_RANGE_BY_SEGMENT[segment]
        sla_fulfillment_days = random.randint(sla_lo, sla_hi)

        disc_lo, disc_hi = DISCOUNT_RANGE_BY_SEGMENT[segment]
        max_discount_pct = round(random.uniform(disc_lo, disc_hi), 2)

        status = "active" if contract_end > pd.Timestamp(HISTORY_END) else "expired"

        rows.append(
            {
                "contract_id": f"CTR{i:05d}",
                "customer_id": cust.customer_id,
                "contract_start_date": contract_start,
                "contract_end_date": contract_end,
                "payment_terms_days": payment_terms_days,
                "max_discount_pct": max_discount_pct,
                "sla_fulfillment_days": sla_fulfillment_days,
                "status": status,
            }
        )
    return pd.DataFrame(rows)


if __name__ == "__main__":
    customers_df = pd.read_csv(CUSTOMERS_PATH, parse_dates=["signup_date"])
    df = generate_contracts(customers_df)

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    df.to_csv(OUT_PATH, index=False)

    print(f"Generated {len(df)} contracts -> {OUT_PATH}\n")

    print("Payment terms distribution (target ~60/25/15 Net30/45/60 overall):")
    print(df["payment_terms_days"].value_counts(normalize=True).round(3))

    print("\nStatus distribution (should be ~100% active given the long duration):")
    print(df["status"].value_counts())

    merged = df.merge(customers_df[["customer_id", "segment"]], on="customer_id")

    print("\nMax discount % by segment (target: Standard 3-12, Strategic 10-25):")
    print(merged.groupby("segment")["max_discount_pct"].describe()[["min", "mean", "max"]].round(2))

    print("\nSLA fulfillment days by segment (target: Standard 5-7, Strategic 3-5):")
    print(merged.groupby("segment")["sla_fulfillment_days"].describe()[["min", "mean", "max"]].round(2))

    dur_years = (
        pd.to_datetime(df["contract_end_date"]) - pd.to_datetime(df["contract_start_date"])
    ).dt.days / 365.25
    print("\nContract duration in years:")
    print(dur_years.describe()[["min", "mean", "max"]].round(2))

    print("\nSample rows:")
    print(df.head())
