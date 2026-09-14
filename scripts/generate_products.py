"""
generate_products.py

Generates the shared product catalogue for Meridian Supply Co.
Table definition: docs/02_data_model_and_dictionary.md, Section 3
Output: data/raw/commercial/products.csv

Price tiers and their split are locked in
docs/03_data_generation_spec.md, Section 2 — the long tail (few
expensive equipment SKUs, many cheap consumables) is deliberate,
it's what makes order value vary realistically later.
"""

import os
import random

import numpy as np
import pandas as pd
from faker import Faker

# ---- reproducibility ----
SEED = 42
random.seed(SEED)
np.random.seed(SEED)
fake = Faker("en_US")
Faker.seed(SEED)

# ---- locked parameters ----
N_PRODUCTS = 130  # midpoint of the locked 100-150 range

TIERS = ["Consumable", "Component", "Equipment"]
TIER_WEIGHTS = [0.60, 0.30, 0.10]
TIER_PRICE_RANGES = {
    "Consumable": (15, 150),
    "Component": (150, 1200),
    "Equipment": (1200, 15000),
}

CATEGORY_WORDS = {
    "Consumable": ["Fastener", "Gasket", "Filter", "Bearing", "Seal", "Fitting", "Hose", "Connector"],
    "Component": ["Motor", "Pump", "Valve", "Controller", "Sensor", "Actuator", "Gearbox", "Relay"],
    "Equipment": ["Compressor", "Generator", "Conveyor System", "Hydraulic Press", "Industrial Chiller", "CNC Unit"],
}

# Technical-sounding modifiers instead of fake.word() - a generic English
# dictionary produces nonsense like "Sensor Brother-350" for a catalog name.
MODIFIERS = ["Standard", "Premium", "Precision", "Compact", "Industrial", "Reinforced", "HD", "XT", "Pro"]

OUT_PATH = os.path.join(
    os.path.dirname(__file__), "..", "data", "raw", "commercial", "products.csv"
)


def generate_products(n=N_PRODUCTS):
    rows = []
    for i in range(1, n + 1):
        tier = np.random.choice(TIERS, p=TIER_WEIGHTS)
        low, high = TIER_PRICE_RANGES[tier]
        list_price = round(float(np.random.uniform(low, high)), 2)
        product_name = f"{random.choice(CATEGORY_WORDS[tier])} {random.choice(MODIFIERS)}-{random.randint(100, 999)}"
        rows.append(
            {
                "product_id": f"PROD{i:05d}",
                "product_name": product_name,
                "category": tier,
                "list_price": list_price,
                "created_at": pd.Timestamp.now(),
            }
        )
    return pd.DataFrame(rows)


if __name__ == "__main__":
    df = generate_products()
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    df.to_csv(OUT_PATH, index=False)

    print(f"Generated {len(df)} products -> {OUT_PATH}\n")
    print("Tier distribution (target: 60% Consumable / 30% Component / 10% Equipment):")
    print(df["category"].value_counts(normalize=True).round(3))
    print("\nPrice range by tier:")
    print(df.groupby("category")["list_price"].describe()[["min", "mean", "max"]].round(2))
    print("\nUnique product names:", df["product_name"].nunique(), "/", len(df))
    print("\nSample rows:")
    print(df.head())
