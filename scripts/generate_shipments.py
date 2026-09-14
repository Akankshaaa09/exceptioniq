"""
generate_shipments.py

Generates exactly one clean shipment per order.
Source system: Operations
Output: data/raw/operations/shipments.csv

Clean baseline (03_data_generation_spec.md, Section 3):
  quantity_shipped = quantity_ordered (summed across order_items)
  order_date < ship_date <= promised_ship_date
  status = shipped

Fulfillment center assignment is regionally weighted - not because
an exact number was locked anywhere before this script, but because
"use the four fulfillment centers" needed an actual assignment rule,
and a regional baseline is what makes the later concentration-bias
injection (late fulfillment weighted onto FC-Reno/FC-Newark, per
03_data_generation_spec.md Section 4a) land on a realistic base
instead of a uniform one.
"""

import os
import random

import numpy as np
import pandas as pd

SEED = 42
random.seed(SEED)
np.random.seed(SEED)

BASE = os.path.join(os.path.dirname(__file__), "..")
ORDERS_PATH = os.path.join(BASE, "data", "raw", "commercial", "orders.csv")
ORDER_ITEMS_PATH = os.path.join(BASE, "data", "raw", "operations", "order_items.csv")
CUSTOMERS_PATH = os.path.join(BASE, "data", "raw", "commercial", "customers.csv")
OUT_PATH = os.path.join(BASE, "data", "raw", "operations", "shipments.csv")

FULFILLMENT_CENTERS = ["FC-Dallas", "FC-Columbus", "FC-Reno", "FC-Newark"]

# Each region has a primary/nearest center - most orders ship from
# there, a minority get routed elsewhere (inventory availability,
# ordinary logistics noise). New assumption, added here because it
# wasn't needed until this script.
REGION_TO_PRIMARY_FC = {
    "Northeast": "FC-Newark",
    "Midwest": "FC-Columbus",
    "South": "FC-Dallas",
    "West": "FC-Reno",
}
PRIMARY_FC_PROB = 0.85  # 15% of orders route to a non-primary center


def load_inputs():
    orders = pd.read_csv(ORDERS_PATH, parse_dates=["order_date", "promised_ship_date"])
    order_items = pd.read_csv(ORDER_ITEMS_PATH)
    customers = pd.read_csv(CUSTOMERS_PATH)
    return orders, order_items, customers


def pick_fulfillment_center(region):
    primary = REGION_TO_PRIMARY_FC[region]
    if random.random() < PRIMARY_FC_PROB:
        return primary
    return random.choice([fc for fc in FULFILLMENT_CENTERS if fc != primary])


def generate_shipments(orders, order_items, customers):
    qty_by_order = order_items.groupby("order_id")["quantity_ordered"].sum()
    region_by_customer = customers.set_index("customer_id")["region"]

    rows = []
    for i, order in enumerate(orders.itertuples(), start=1):
        region = region_by_customer.loc[order.customer_id]
        fc = pick_fulfillment_center(region)

        sla_days = max((order.promised_ship_date - order.order_date).days, 1)
        ship_date = order.order_date + pd.Timedelta(days=random.randint(1, sla_days))

        rows.append(
            {
                "shipment_id": f"SHP{i:06d}",
                "order_id": order.order_id,
                "fulfillment_center": fc,
                "ship_date": ship_date,
                "quantity_shipped": int(qty_by_order.get(order.order_id, 0)),
                "status": "shipped",
            }
        )
    return pd.DataFrame(rows)


if __name__ == "__main__":
    orders, order_items, customers = load_inputs()
    df = generate_shipments(orders, order_items, customers)

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    df.to_csv(OUT_PATH, index=False)

    print(f"Generated {len(df)} shipments -> {OUT_PATH}\n")

    print("Fulfillment center distribution:")
    print(df["fulfillment_center"].value_counts(normalize=True).round(3))

    print("\nStatus distribution (should be 100% shipped in the clean baseline):")
    print(df["status"].value_counts())

    check = orders.merge(df, on="order_id")
    late = (check["ship_date"] > check["promised_ship_date"]).sum()
    not_after_order = (check["ship_date"] <= check["order_date"]).sum()
    print(f"\nShipments after promised_ship_date (must be 0): {late}")
    print(f"Shipments on/before order_date (must be 0): {not_after_order}")

    qty_check = order_items.groupby("order_id")["quantity_ordered"].sum().rename("total_ordered")
    qty_merged = df.merge(qty_check, on="order_id")
    mismatches = (qty_merged["quantity_shipped"] != qty_merged["total_ordered"]).sum()
    print(f"Shipments where quantity_shipped != total quantity_ordered (must be 0): {mismatches}")

    check2 = check.merge(customers[["customer_id", "region"]], on="customer_id")
    routing = pd.crosstab(check2["region"], check2["fulfillment_center"], normalize="index").round(3)
    print("\nRegional routing (rows should mostly favor their primary FC):")
    print(routing)

    print("\nSample rows:")
    print(df.head())
