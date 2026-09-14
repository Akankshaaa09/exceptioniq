"""
generate_invoices.py

Generates the clean invoice baseline for ExceptionIQ.

Source system: Finance/ERP
Input:
  data/raw/commercial/orders.csv
  data/raw/operations/order_items.csv
  data/raw/operations/shipments.csv
  data/raw/commercial/contracts.csv

Output:
  data/raw/finance/invoices.csv

Clean baseline:
  - exactly one invoice per order
  - invoice amount = expected amount
  - expected amount = shipped quantity valued at the order-line unit price
  - invoice_date = ship_date
  - due_date = invoice_date + contract payment terms
  - status = issued

Exception mutations (price mismatch, underbilling, missing invoice, duplicate invoice)
are NOT introduced here; they belong in the later exception-injection step.
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
SHIPMENTS_PATH = os.path.join(BASE, "data", "raw", "operations", "shipments.csv")
CONTRACTS_PATH = os.path.join(BASE, "data", "raw", "commercial", "contracts.csv")
OUT_PATH = os.path.join(BASE, "data", "raw", "finance", "invoices.csv")


def load_inputs():
    orders = pd.read_csv(
        ORDERS_PATH,
        parse_dates=["order_date", "promised_ship_date", "created_at"],
    )
    order_items = pd.read_csv(ORDER_ITEMS_PATH)
    shipments = pd.read_csv(SHIPMENTS_PATH, parse_dates=["ship_date"])
    contracts = pd.read_csv(
        CONTRACTS_PATH,
        parse_dates=["contract_start_date", "contract_end_date"],
    )
    return orders, order_items, shipments, contracts


def generate_invoices(orders, order_items, shipments, contracts):
    # V1 has exactly one shipment per order, but we still aggregate by order
    # so the calculation remains correct if that model is expanded later.
    shipped_qty = shipments.groupby("order_id")["quantity_shipped"].sum()

    contracts_by_id = contracts.set_index("contract_id")
    rows = []

    for i, order in enumerate(orders.itertuples(), start=1):
        if order.order_id not in shipped_qty.index:
            raise ValueError(f"Order {order.order_id} has no shipment.")

        order_lines = order_items[order_items["order_id"] == order.order_id].copy()
        if order_lines.empty:
            raise ValueError(f"Order {order.order_id} has no order items.")

        total_ordered = int(order_lines["quantity_ordered"].sum())
        total_shipped = int(shipped_qty.loc[order.order_id])

        if total_shipped != total_ordered:
            raise ValueError(
                f"Clean baseline violation for {order.order_id}: "
                f"shipped={total_shipped}, ordered={total_ordered}"
            )

        invoice_date = shipments.loc[
            shipments["order_id"] == order.order_id, "ship_date"
        ].iloc[0]

        contract = contracts_by_id.loc[order.contract_id]
        payment_terms_days = int(contract.payment_terms_days)
        due_date = invoice_date + pd.Timedelta(days=payment_terms_days)

        expected_amount = round(float(order_lines["line_total"].sum()), 2)

        rows.append(
            {
                "invoice_id": f"INV{i:06d}",
                "order_id": order.order_id,
                "invoice_date": invoice_date,
                "invoice_amount": expected_amount,
                "expected_amount": expected_amount,
                "due_date": due_date,
                "status": "issued",
            }
        )

    return pd.DataFrame(rows)


def validate(orders, order_items, shipments, contracts, invoices):
    if len(invoices) != len(orders):
        raise ValueError(
            f"Expected {len(orders)} invoices, generated {len(invoices)}."
        )

    if invoices["invoice_id"].duplicated().any():
        raise ValueError("Duplicate invoice_id values found.")

    if invoices["order_id"].duplicated().any():
        raise ValueError("More than one clean-baseline invoice found for an order.")

    if invoices["invoice_amount"].isna().any():
        raise ValueError("Null invoice amounts found.")

    if (invoices["invoice_amount"] != invoices["expected_amount"]).any():
        raise ValueError("Invoice amount != expected amount in clean baseline.")

    if not (invoices["invoice_amount"] >= 0).all():
        raise ValueError("Negative invoice amounts found.")

    order_ship = shipments[["order_id", "ship_date"]]
    check = invoices.merge(order_ship, on="order_id", how="left", suffixes=("", "_shipment"))

    if check["invoice_date"].isna().any() or check["ship_date"].isna().any():
        raise ValueError("Invoice missing ship-date linkage.")

    if (check["invoice_date"] != check["ship_date"]).any():
        raise ValueError("Invoice date does not equal shipment date in clean baseline.")

    terms = contracts[["contract_id", "payment_terms_days"]]
    check = check.merge(
        orders[["order_id", "contract_id"]],
        on="order_id",
        how="left",
    ).merge(terms, on="contract_id", how="left")

    expected_due = check["invoice_date"] + pd.to_timedelta(
        check["payment_terms_days"], unit="D"
    )
    if (check["due_date"] != expected_due).any():
        raise ValueError("Due date does not match contract payment terms.")

    order_totals = order_items.groupby("order_id")["line_total"].sum().rename("line_total_sum")
    recon = invoices.merge(order_totals, on="order_id", how="left")
    if (recon["invoice_amount"] != recon["line_total_sum"].round(2)).any():
        raise ValueError("Invoice amount does not reconcile to order-line value.")

    print(f"Invoice rows: {len(invoices)}")
    print(f"Unique orders invoiced: {invoices['order_id'].nunique()}")
    print(f"Status distribution:\n{invoices['status'].value_counts()}")
    print(
        "\nInvoice amount distribution:\n"
        + str(invoices["invoice_amount"].describe()[["min", "mean", "50%", "max"]].round(2))
    )
    print("\nValidation: ALL CLEAN-BASELINE CHECKS PASSED.")


if __name__ == "__main__":
    orders, order_items, shipments, contracts = load_inputs()
    invoices = generate_invoices(orders, order_items, shipments, contracts)
    validate(orders, order_items, shipments, contracts, invoices)

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    invoices.to_csv(OUT_PATH, index=False)
    print(f"\nGenerated {len(invoices)} invoices -> {OUT_PATH}")
