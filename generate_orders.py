"""
generate_orders.py

Generates orders (source: Commercial/CRM) and order_items (source:
Operations) together in one pass. They're two tables from two
different source systems, but generated in the same script rather
than split into generate_orders.py + generate_order_items.py,
because an order without its line items isn't inspectable on its
own, and splitting them would mean re-running the same
customer/contract iteration loop twice for no reason.

Output:
  data/raw/commercial/orders.csv
  data/raw/operations/order_items.csv

Every distribution below traces to 03_data_generation_spec.md,
Section 2, and the "Normal O2C Behavior" table in Section 3:
  discount_pct_applied <= contracts.max_discount_pct   (always true here -
  this is the CLEAN baseline; violations only get introduced later by
  inject_exceptions.py, per the locked causal-structure principle)

v1 scope note: order_status is always "confirmed". Cancelled orders
are not modeled in v1 - no locked spec covers what a cancellation
should do to downstream shipment/invoice/payment generation, and
adding that now is exactly the kind of unpriced complexity this
project has been deliberately cutting elsewhere. Flagging it here so
it's a documented decision, not a silent gap.
"""

import os
import random
from datetime import date

import numpy as np
import pandas as pd
from dateutil.relativedelta import relativedelta

# ---- reproducibility - same seed as every prior generator ----
SEED = 42
random.seed(SEED)
np.random.seed(SEED)

HISTORY_MONTHS = 15
HISTORY_END = pd.Timestamp(date(2026, 8, 31))
HISTORY_START = HISTORY_END - relativedelta(months=HISTORY_MONTHS)

BASE = os.path.join(os.path.dirname(__file__), "..")
CUSTOMERS_PATH = os.path.join(BASE, "data", "raw", "commercial", "customers.csv")
CONTRACTS_PATH = os.path.join(BASE, "data", "raw", "commercial", "contracts.csv")
PRODUCTS_PATH = os.path.join(BASE, "data", "raw", "commercial", "products.csv")
ORDERS_OUT_PATH = os.path.join(BASE, "data", "raw", "commercial", "orders.csv")
ORDER_ITEMS_OUT_PATH = os.path.join(BASE, "data", "raw", "operations", "order_items.csv")

# locked in 03_data_generation_spec.md, Section 2
ORDER_RATE_BY_SEGMENT = {  # orders per month, sampled once per customer as their persistent rate
    "Standard": (0.4, 1.1),
    "Strategic": (1.8, 3.8),
}
ITEMS_PER_ORDER_BY_SEGMENT = {  # (min, max) line items on a given order
    "Standard": (1, 3),
    "Strategic": (3, 8),
}
# How often each product tier shows up on a given line item. This is
# NOT the same as the catalog's tier composition (60/30/10) - sampling
# uniformly across all SKUs made Equipment items appear on ~half of
# Strategic orders just by chance, which broke the "occasional large
# equipment order" intent from the business spec. Weighting it directly
# is the fix.
ITEM_TIER_WEIGHTS = {"Consumable": 0.75, "Component": 0.23, "Equipment": 0.02}
# Quantity ranges by product tier - tightened a second time after review
# showed the first pass still produced too many $10K-$97K orders. The
# comment above (2-40/1-10/1-3) was the first correction; this is the
# second, smaller ranges especially on Equipment (1-2 units, not 1-3).
QUANTITY_RANGE_BY_TIER = {
    "Consumable": (1, 20),
    "Component": (1, 6),
    "Equipment": (1, 2),
}


def load_inputs():
    customers = pd.read_csv(CUSTOMERS_PATH, parse_dates=["signup_date"])
    contracts = pd.read_csv(
        CONTRACTS_PATH, parse_dates=["contract_start_date", "contract_end_date"]
    )
    products = pd.read_csv(PRODUCTS_PATH)
    return customers, contracts, products


def generate_orders_and_items(customers, contracts, products):
    order_rows = []
    item_rows = []
    order_counter = 0
    item_counter = 0

    contracts_by_customer = contracts.set_index("customer_id")
    products_by_tier = {tier: products[products["category"] == tier] for tier in products["category"].unique()}

    for cust in customers.itertuples():
        contract = contracts_by_customer.loc[cust.customer_id]
        segment = cust.segment

        effective_start = max(pd.Timestamp(contract.contract_start_date), HISTORY_START)
        if effective_start >= HISTORY_END:
            continue  # signed up too late in the window to have placed any orders

        window_months = (HISTORY_END - effective_start).days / 30.44

        rate_lo, rate_hi = ORDER_RATE_BY_SEGMENT[segment]
        monthly_rate = random.uniform(rate_lo, rate_hi)  # this customer's persistent ordering rate
        n_orders = np.random.poisson(monthly_rate * window_months)

        window_days = (HISTORY_END - effective_start).days

        for _ in range(n_orders):
            order_counter += 1
            order_id = f"ORD{order_counter:06d}"

            order_date = effective_start + pd.Timedelta(days=random.randint(0, window_days))
            promised_ship_date = order_date + pd.Timedelta(days=int(contract.sla_fulfillment_days))

            # Clean baseline: discount is always within ceiling. Modeled as
            # uniform(0, ceiling) rather than always maxing it out - most
            # orders get a modest discount, some get close to the max.
            discount_pct_applied = round(random.uniform(0, contract.max_discount_pct), 2)

            order_rows.append(
                {
                    "order_id": order_id,
                    "customer_id": cust.customer_id,
                    "contract_id": contract.contract_id,
                    "order_date": order_date,
                    "discount_pct_applied": discount_pct_applied,
                    "promised_ship_date": promised_ship_date,
                    "order_status": "confirmed",
                    "created_at": pd.Timestamp.now(),
                }
            )

            lo, hi = ITEMS_PER_ORDER_BY_SEGMENT[segment]
            n_items = random.randint(lo, hi)

            for _ in range(n_items):
                item_counter += 1
                item_id = f"OI{item_counter:07d}"

                tier = np.random.choice(
                    list(ITEM_TIER_WEIGHTS.keys()), p=list(ITEM_TIER_WEIGHTS.values())
                )
                product = products_by_tier[tier].sample(1).iloc[0]
                q_lo, q_hi = QUANTITY_RANGE_BY_TIER[tier]
                quantity_ordered = random.randint(q_lo, q_hi)

                unit_price_at_order = round(
                    float(product["list_price"]) * (1 - discount_pct_applied / 100), 2
                )
                line_total = round(unit_price_at_order * quantity_ordered, 2)

                item_rows.append(
                    {
                        "order_item_id": item_id,
                        "order_id": order_id,
                        "product_id": product["product_id"],
                        "quantity_ordered": quantity_ordered,
                        "unit_price_at_order": unit_price_at_order,
                        "line_total": line_total,
                    }
                )

    return pd.DataFrame(order_rows), pd.DataFrame(item_rows)


if __name__ == "__main__":
    customers, contracts, products = load_inputs()
    orders_df, items_df = generate_orders_and_items(customers, contracts, products)

    os.makedirs(os.path.dirname(ORDERS_OUT_PATH), exist_ok=True)
    os.makedirs(os.path.dirname(ORDER_ITEMS_OUT_PATH), exist_ok=True)
    orders_df.to_csv(ORDERS_OUT_PATH, index=False)
    items_df.to_csv(ORDER_ITEMS_OUT_PATH, index=False)

    print(f"Generated {len(orders_df)} orders -> {ORDERS_OUT_PATH}")
    print(f"Generated {len(items_df)} order_items -> {ORDER_ITEMS_OUT_PATH}\n")

    print(f"Target was 5,000-8,000 orders. Actual: {len(orders_df)}")

    merged = orders_df.merge(customers[["customer_id", "segment"]], on="customer_id")
    print("\nOrders by segment:")
    print(merged["segment"].value_counts())

    print("\nItems per order by segment:")
    items_per_order = items_df.groupby("order_id").size().rename("n_items")
    check = merged.set_index("order_id").join(items_per_order)
    print(check.groupby("segment")["n_items"].describe()[["min", "mean", "max"]].round(2))

    order_value = items_df.groupby("order_id")["line_total"].sum().rename("order_value")
    print("\nOrder value distribution overall:")
    print(order_value.describe()[["min", "mean", "50%", "max"]].round(2))

    ov_by_segment = merged.set_index("order_id").join(order_value)
    print("\nOrder value by segment (target: Standard ~$200-3,000 typical, Strategic higher but not routinely $15K+):")
    print(ov_by_segment.groupby("segment")["order_value"].describe()[["50%", "mean", "max"]].round(2))

    print("\nDiscount applied vs contract ceiling (spot check - should always be <=):")
    dcheck = orders_df.merge(contracts[["contract_id", "max_discount_pct"]], on="contract_id")
    violations = (dcheck["discount_pct_applied"] > dcheck["max_discount_pct"]).sum()
    print(f"Orders exceeding their contract's discount ceiling: {violations} (must be 0 in the clean baseline)")

    print("\nSample order rows:")
    print(orders_df.head())
    print("\nSample order_item rows:")
    print(items_df.head())
