"""
inject_exceptions.py

Takes the clean baseline (orders, order_items, shipments, invoices,
payments) and deliberately mutates a sampled subset of records to
create each of the 10 business exceptions, per the exact rules locked
in 03_data_generation_spec.md, Section 4.

Every mutation is logged to ground_truth_exceptions.csv in the same
step that creates it - this is what makes precision/recall/F1
evaluation possible later (Section 6), instead of a hand-wavy
"accuracy" number.

Design principle enforced throughout: GLOBAL ORDER-ID EXCLUSIVITY.
Once an order_id has been used for one exception type, it's excluded
from every other exception type. This keeps every planted case
attributable to exactly one root cause, and it prevents one mutation
from accidentally faking a second, unintended exception (e.g. a stale
payment amount left over from a price-mismatch mutation looking like
a partial payment that was never planted).

Reads (clean baseline):
  data/raw/commercial/{customers,contracts,products,orders}.csv
  data/raw/operations/{order_items,shipments}.csv
  data/raw/finance/{invoices,payments}.csv

Overwrites (the injected data IS the final "as extracted from a messy
real system" state - per 01_business_specification.md Section 16,
these mutations must actually manifest in the data, not sit as a
separate flag):
  same 5 mutable tables

Writes (kept OUTSIDE data/raw/ deliberately - this is the answer key,
not something the fictional company's source systems would contain):
  data/ground_truth/ground_truth_exceptions.csv

To regenerate the clean baseline from scratch: re-run generators 1-7
in order (customers -> products -> contracts -> orders -> shipments ->
invoices -> payments) before running this script again. Data-quality
issues (duplicate rows, orphan references) are a separate script,
inject_data_quality_issues.py, not part of this one.
"""

import os
import random

import numpy as np
import pandas as pd

SEED = 42
random.seed(SEED)
np.random.seed(SEED)

BASE = os.path.join(os.path.dirname(__file__), "..")
CUSTOMERS_PATH = os.path.join(BASE, "data", "raw", "commercial", "customers.csv")
CONTRACTS_PATH = os.path.join(BASE, "data", "raw", "commercial", "contracts.csv")
PRODUCTS_PATH = os.path.join(BASE, "data", "raw", "commercial", "products.csv")
ORDERS_PATH = os.path.join(BASE, "data", "raw", "commercial", "orders.csv")
ORDER_ITEMS_PATH = os.path.join(BASE, "data", "raw", "operations", "order_items.csv")
SHIPMENTS_PATH = os.path.join(BASE, "data", "raw", "operations", "shipments.csv")
INVOICES_PATH = os.path.join(BASE, "data", "raw", "finance", "invoices.csv")
PAYMENTS_PATH = os.path.join(BASE, "data", "raw", "finance", "payments.csv")
GROUND_TRUTH_PATH = os.path.join(BASE, "data", "ground_truth", "ground_truth_exceptions.csv")

# locked in 03_data_generation_spec.md, Section 4
RATES = {
    "unauthorized_discount": 0.015,
    "price_mismatch": 0.015,
    "late_fulfillment": 0.05,
    "partial_shipment": 0.025,
    "underbilling": 0.015,
    "missing_invoice": 0.0075,
    "duplicate_invoice": 0.0075,
    "partial_payment": 0.04,
    "overdue_payment": 0.075,
    "duplicate_payment": 0.0075,
}
CONCENTRATION_FRACTION = 0.60  # locked in Section 4a

used_order_ids = set()
ground_truth_rows = []
_gt_counter = [0]


def load_inputs():
    customers = pd.read_csv(CUSTOMERS_PATH)
    contracts = pd.read_csv(CONTRACTS_PATH, parse_dates=["contract_start_date", "contract_end_date"])
    products = pd.read_csv(PRODUCTS_PATH)
    orders = pd.read_csv(ORDERS_PATH, parse_dates=["order_date", "promised_ship_date", "created_at"])
    order_items = pd.read_csv(ORDER_ITEMS_PATH)
    shipments = pd.read_csv(SHIPMENTS_PATH, parse_dates=["ship_date"])
    invoices = pd.read_csv(INVOICES_PATH, parse_dates=["invoice_date", "due_date"])
    payments = pd.read_csv(PAYMENTS_PATH, parse_dates=["payment_date"])
    return customers, contracts, products, orders, order_items, shipments, invoices, payments


def log_ground_truth(exception_type, source_table, source_record_id, planted_condition,
                      expected_financial_impact=None):
    _gt_counter[0] += 1
    ground_truth_rows.append({
        "ground_truth_id": f"GT{_gt_counter[0]:05d}",
        "category": "business_exception",
        "exception_type": exception_type,
        "source_table": source_table,
        "source_record_id": source_record_id,
        "planted_condition": planted_condition,
        "expected_financial_impact": (
            round(float(expected_financial_impact), 2) if expected_financial_impact is not None else None
        ),
        "generation_timestamp": pd.Timestamp.now(),
    })


def sample_eligible_orders(all_ids, n, biased_subset=None, fraction=CONCENTRATION_FRACTION):
    """Filters out anything already used, then samples n order_ids.
    If biased_subset is given, `fraction` of the sample is drawn from
    it (per Section 4a's concentration bias), with graceful fallback
    if either pool is too small."""
    eligible = [oid for oid in all_ids if oid not in used_order_ids]

    if biased_subset is None:
        if len(eligible) < n:
            print(f"  [warning] only {len(eligible)} eligible, requested {n} - taking all available")
            n = len(eligible)
        return list(np.random.choice(eligible, size=n, replace=False)) if n > 0 else []

    biased_pool = [oid for oid in biased_subset if oid in eligible]
    other_pool = [oid for oid in eligible if oid not in biased_pool]

    n_biased = round(n * fraction)
    n_other = n - n_biased

    if len(biased_pool) < n_biased:
        print(f"  [warning] biased pool only has {len(biased_pool)}, wanted {n_biased} - backfilling from general pool")
        n_other += n_biased - len(biased_pool)
        n_biased = len(biased_pool)
    if len(other_pool) < n_other:
        print(f"  [warning] general pool only has {len(other_pool)}, wanted {n_other} - taking all available")
        n_other = len(other_pool)

    picked_biased = list(np.random.choice(biased_pool, size=n_biased, replace=False)) if n_biased > 0 else []
    picked_other = list(np.random.choice(other_pool, size=n_other, replace=False)) if n_other > 0 else []
    return picked_biased + picked_other


def sync_payment_to_invoice(order_id, invoices, payments):
    """After mutating an invoice_amount, keep the payment 'clean' by
    matching it to whatever the invoice now actually says - otherwise
    a stale payment amount would accidentally look like a second,
    unintended partial-payment exception that was never planted."""
    inv = invoices[invoices["order_id"] == order_id].iloc[0]
    payments.loc[payments["invoice_id"] == inv["invoice_id"], "payment_amount"] = inv["invoice_amount"]


def main():
    customers, contracts, products, orders, order_items, shipments, invoices, payments = load_inputs()

    total_orders = len(orders)
    products_by_id = products.set_index("product_id")
    contracts_by_id = contracts.set_index("contract_id")
    customer_segment = customers.set_index("customer_id")["segment"]

    order_segment = orders["customer_id"].map(customer_segment)
    strategic_order_ids = orders.loc[order_segment == "Strategic", "order_id"].tolist()

    net60_contract_ids = set(contracts.loc[contracts["payment_terms_days"] == 60, "contract_id"])
    net60_order_ids = orders.loc[orders["contract_id"].isin(net60_contract_ids), "order_id"].tolist()

    reno_newark_order_ids = shipments.loc[
        shipments["fulfillment_center"].isin(["FC-Reno", "FC-Newark"]), "order_id"
    ].tolist()

    all_order_ids = orders["order_id"].tolist()

    # 1. Unauthorized discount - full cascade: order -> order_items -> invoice -> payment
    n = round(RATES["unauthorized_discount"] * total_orders)
    targets = sample_eligible_orders(all_order_ids, n, biased_subset=strategic_order_ids)
    print(f"1. Unauthorized discount: injecting {len(targets)}")
    for order_id in targets:
        order_idx = orders.index[orders["order_id"] == order_id][0]
        contract_id = orders.at[order_idx, "contract_id"]
        max_discount = contracts_by_id.at[contract_id, "max_discount_pct"]
        new_discount = round(float(max_discount) + random.uniform(2, 15), 2)
        orders.at[order_idx, "discount_pct_applied"] = new_discount

        item_mask = order_items["order_id"] == order_id
        old_expected = order_items.loc[item_mask, "line_total"].sum()
        for idx in order_items.index[item_mask]:
            product_id = order_items.at[idx, "product_id"]
            list_price = float(products_by_id.at[product_id, "list_price"])
            qty = order_items.at[idx, "quantity_ordered"]
            new_unit_price = round(list_price * (1 - new_discount / 100), 2)
            order_items.at[idx, "unit_price_at_order"] = new_unit_price
            order_items.at[idx, "line_total"] = round(new_unit_price * qty, 2)
        new_expected = order_items.loc[item_mask, "line_total"].sum()

        inv_mask = invoices["order_id"] == order_id
        invoices.loc[inv_mask, "expected_amount"] = round(new_expected, 2)
        invoices.loc[inv_mask, "invoice_amount"] = round(new_expected, 2)
        sync_payment_to_invoice(order_id, invoices, payments)

        log_ground_truth(
            "unauthorized_discount", "orders", order_id,
            f"discount_pct_applied set to {new_discount}% vs contract ceiling {max_discount}%",
            expected_financial_impact=old_expected - new_expected,
        )
        used_order_ids.add(order_id)

    # 2. Price mismatch - invoice overstates vs expected
    n = round(RATES["price_mismatch"] * total_orders)
    targets = sample_eligible_orders(all_order_ids, n, biased_subset=strategic_order_ids)
    print(f"2. Price mismatch: injecting {len(targets)}")
    for order_id in targets:
        inv_idx = invoices.index[invoices["order_id"] == order_id][0]
        expected = invoices.at[inv_idx, "expected_amount"]
        new_amount = round(float(expected) * random.uniform(1.05, 1.20), 2)
        invoices.at[inv_idx, "invoice_amount"] = new_amount
        sync_payment_to_invoice(order_id, invoices, payments)
        log_ground_truth(
            "price_mismatch", "invoices", invoices.at[inv_idx, "invoice_id"],
            f"invoice_amount set to {new_amount} vs expected_amount {expected}",
            expected_financial_impact=new_amount - expected,
        )
        used_order_ids.add(order_id)

    # 3. Late fulfillment - concentrated on FC-Reno / FC-Newark
    n = round(RATES["late_fulfillment"] * total_orders)
    targets = sample_eligible_orders(all_order_ids, n, biased_subset=reno_newark_order_ids)
    print(f"3. Late fulfillment: injecting {len(targets)}")
    for order_id in targets:
        ship_idx = shipments.index[shipments["order_id"] == order_id][0]
        promised = orders.loc[orders["order_id"] == order_id, "promised_ship_date"].iloc[0]
        new_ship_date = promised + pd.Timedelta(days=random.randint(1, 10))
        shipments.at[ship_idx, "ship_date"] = new_ship_date
        log_ground_truth(
            "late_fulfillment", "shipments", shipments.at[ship_idx, "shipment_id"],
            f"ship_date set to {new_ship_date.date()} vs promised_ship_date {promised.date()}",
            expected_financial_impact=None,  # no direct $ figure from this mutation alone
        )
        used_order_ids.add(order_id)

    # 4. Partial shipment
    # Orders with quantity_ordered < 2 can't be meaningfully "partial" -
    # shipping 1 of 1 is binary, not partial. Excluding them from
    # eligibility instead of letting the fraction round back to the
    # original (which is exactly the bug review caught: 2 of 151 cases
    # had quantity_shipped == ordered because round(1 * 0.4-0.85) can
    # equal 1).
    qty_by_order = order_items.groupby("order_id")["quantity_ordered"].sum()
    eligible_for_partial = [oid for oid in all_order_ids if qty_by_order.get(oid, 0) >= 2]
    n = round(RATES["partial_shipment"] * total_orders)
    targets = sample_eligible_orders(eligible_for_partial, n)
    print(f"4. Partial shipment: injecting {len(targets)}")
    for order_id in targets:
        ship_idx = shipments.index[shipments["order_id"] == order_id][0]
        item_rows = order_items[order_items["order_id"] == order_id]
        ordered_qty = item_rows["quantity_ordered"].sum()
        # Guarantee strict reduction - min() against ordered_qty-1 means
        # the fraction can never round back to the original value.
        new_qty = min(ordered_qty - 1, int(round(ordered_qty * random.uniform(0.4, 0.85))))
        new_qty = max(new_qty, 0)
        shipments.at[ship_idx, "quantity_shipped"] = new_qty
        shipments.at[ship_idx, "status"] = "partial"

        avg_unit_price = (item_rows["line_total"].sum() / ordered_qty) if ordered_qty else 0
        shortfall_value = (ordered_qty - new_qty) * avg_unit_price
        log_ground_truth(
            "partial_shipment", "shipments", shipments.at[ship_idx, "shipment_id"],
            f"quantity_shipped set to {new_qty} vs quantity_ordered {ordered_qty}",
            expected_financial_impact=shortfall_value,
        )
        used_order_ids.add(order_id)

    # 5. Underbilling
    n = round(RATES["underbilling"] * total_orders)
    targets = sample_eligible_orders(all_order_ids, n)
    print(f"5. Underbilling: injecting {len(targets)}")
    for order_id in targets:
        inv_idx = invoices.index[invoices["order_id"] == order_id][0]
        expected = invoices.at[inv_idx, "expected_amount"]
        new_amount = round(float(expected) * random.uniform(0.7, 0.95), 2)
        invoices.at[inv_idx, "invoice_amount"] = new_amount
        sync_payment_to_invoice(order_id, invoices, payments)
        log_ground_truth(
            "underbilling", "invoices", invoices.at[inv_idx, "invoice_id"],
            f"invoice_amount set to {new_amount} vs expected_amount {expected}",
            expected_financial_impact=expected - new_amount,
        )
        used_order_ids.add(order_id)

    # 6. Missing invoice - delete the invoice AND its now-orphaned payment
    n = round(RATES["missing_invoice"] * total_orders)
    targets = sample_eligible_orders(all_order_ids, n)
    print(f"6. Missing invoice: injecting {len(targets)}")
    for order_id in targets:
        inv_row = invoices[invoices["order_id"] == order_id].iloc[0]
        invoice_id = inv_row["invoice_id"]
        expected = inv_row["expected_amount"]
        payments = payments[payments["invoice_id"] != invoice_id]
        invoices = invoices[invoices["order_id"] != order_id]
        log_ground_truth(
            "missing_invoice", "orders", order_id,
            f"order fulfilled but no invoice generated (would-have-been {invoice_id})",
            expected_financial_impact=expected,
        )
        used_order_ids.add(order_id)

    # 7. Duplicate invoice - second invoice row for the same order, left unpaid
    # (a duplicate/erroneous invoice going unpaid is the realistic case - a
    # matching duplicate PAYMENT is exception #10's job, not this one's)
    n = round(RATES["duplicate_invoice"] * total_orders)
    targets = sample_eligible_orders(all_order_ids, n)
    print(f"7. Duplicate invoice: injecting {len(targets)}")
    order_contract_terms = orders.set_index("order_id")["contract_id"].map(contracts_by_id["payment_terms_days"])
    next_invoice_num = int(invoices["invoice_id"].str.replace("INV", "", regex=False).astype(int).max()) + 1
    new_invoice_rows = []
    for order_id in targets:
        orig = invoices[invoices["order_id"] == order_id].iloc[0]
        dup_id = f"INV{next_invoice_num:06d}"
        next_invoice_num += 1
        dup_invoice_date = orig["invoice_date"] + pd.Timedelta(days=random.randint(2, 7))
        dup_due_date = dup_invoice_date + pd.Timedelta(days=int(order_contract_terms.loc[order_id]))
        new_invoice_rows.append({
            "invoice_id": dup_id, "order_id": order_id, "invoice_date": dup_invoice_date,
            "invoice_amount": orig["expected_amount"], "expected_amount": orig["expected_amount"],
            "due_date": dup_due_date, "status": "issued",
        })
        log_ground_truth(
            "duplicate_invoice", "invoices", dup_id,
            f"second invoice generated for order {order_id}, same amount {orig['expected_amount']} as the original",
            expected_financial_impact=orig["expected_amount"],
        )
        used_order_ids.add(order_id)
    if new_invoice_rows:
        invoices = pd.concat([invoices, pd.DataFrame(new_invoice_rows)], ignore_index=True)

    # 8. Partial payment
    n = round(RATES["partial_payment"] * total_orders)
    targets = sample_eligible_orders(all_order_ids, n)
    print(f"8. Partial payment: injecting {len(targets)}")
    for order_id in targets:
        inv_rows = invoices[invoices["order_id"] == order_id]
        if inv_rows.empty:
            continue
        inv_row = inv_rows.iloc[0]
        pay_idx = payments.index[payments["invoice_id"] == inv_row["invoice_id"]]
        if len(pay_idx) == 0:
            continue
        pay_idx = pay_idx[0]
        invoice_amount = inv_row["invoice_amount"]
        new_payment = round(float(invoice_amount) * random.uniform(0.3, 0.85), 2)
        payments.at[pay_idx, "payment_amount"] = new_payment
        log_ground_truth(
            "partial_payment", "payments", payments.at[pay_idx, "payment_id"],
            f"payment_amount set to {new_payment} vs invoice_amount {invoice_amount}",
            expected_financial_impact=float(invoice_amount) - new_payment,
        )
        used_order_ids.add(order_id)

    # 9. Overdue payment - concentrated on Net 60 contracts
    n = round(RATES["overdue_payment"] * total_orders)
    targets = sample_eligible_orders(all_order_ids, n, biased_subset=net60_order_ids)
    print(f"9. Overdue payment: injecting {len(targets)}")
    for order_id in targets:
        inv_rows = invoices[invoices["order_id"] == order_id]
        if inv_rows.empty:
            continue
        inv_row = inv_rows.iloc[0]
        pay_idx = payments.index[payments["invoice_id"] == inv_row["invoice_id"]]
        if len(pay_idx) == 0:
            continue
        pay_idx = pay_idx[0]
        due_date = inv_row["due_date"]
        new_payment_date = due_date + pd.Timedelta(days=random.randint(5, 45))
        payments.at[pay_idx, "payment_date"] = new_payment_date
        log_ground_truth(
            "overdue_payment", "payments", payments.at[pay_idx, "payment_id"],
            f"payment_date set to {new_payment_date.date()} vs due_date {due_date.date()}",
            expected_financial_impact=inv_row["invoice_amount"],
        )
        used_order_ids.add(order_id)

    # 10. Duplicate payment - second payment against the same invoice
    n = round(RATES["duplicate_payment"] * total_orders)
    targets = sample_eligible_orders(all_order_ids, n)
    print(f"10. Duplicate payment: injecting {len(targets)}")
    next_payment_num = int(payments["payment_id"].str.replace("PAY", "", regex=False).astype(int).max()) + 1
    new_payment_rows = []
    for order_id in targets:
        inv_rows = invoices[invoices["order_id"] == order_id]
        if inv_rows.empty:
            continue
        invoice_id = inv_rows.iloc[0]["invoice_id"]
        due_date = inv_rows.iloc[0]["due_date"]
        orig_pay_rows = payments[payments["invoice_id"] == invoice_id]
        if orig_pay_rows.empty:
            continue
        orig_pay = orig_pay_rows.iloc[0]
        dup_id = f"PAY{next_payment_num:06d}"
        next_payment_num += 1
        # Capped at due_date - otherwise the +1..5 day offset can push a
        # duplicate past due_date when the original payment was already
        # close to it, accidentally creating an overdue-payment signal
        # that was never planted as one. Found via review: 4 of 45
        # duplicate_payment cases were doing this before the cap.
        dup_date = min(orig_pay["payment_date"] + pd.Timedelta(days=random.randint(1, 5)), due_date)
        new_payment_rows.append({
            "payment_id": dup_id, "invoice_id": invoice_id, "payment_date": dup_date,
            "payment_amount": orig_pay["payment_amount"], "status": "posted",
        })
        log_ground_truth(
            "duplicate_payment", "payments", dup_id,
            f"second payment of {orig_pay['payment_amount']} recorded against invoice {invoice_id}",
            expected_financial_impact=orig_pay["payment_amount"],
        )
        used_order_ids.add(order_id)
    if new_payment_rows:
        payments = pd.concat([payments, pd.DataFrame(new_payment_rows)], ignore_index=True)

    # ---- write everything out ----
    os.makedirs(os.path.dirname(GROUND_TRUTH_PATH), exist_ok=True)
    orders.to_csv(ORDERS_PATH, index=False)
    order_items.to_csv(ORDER_ITEMS_PATH, index=False)
    shipments.to_csv(SHIPMENTS_PATH, index=False)
    invoices.to_csv(INVOICES_PATH, index=False)
    payments.to_csv(PAYMENTS_PATH, index=False)

    ground_truth_df = pd.DataFrame(ground_truth_rows)
    ground_truth_df.to_csv(GROUND_TRUTH_PATH, index=False)

    # ---- validation summary ----
    print(f"\n{'='*60}\nINJECTION SUMMARY\n{'='*60}")
    print(f"Orders touched by an exception: {len(used_order_ids)} / {total_orders} ({len(used_order_ids)/total_orders:.1%})")
    print(f"Ground truth rows logged: {len(ground_truth_df)}")

    print("\nInjected counts by type (target vs actual):")
    actual_counts = ground_truth_df["exception_type"].value_counts()
    for etype, rate in RATES.items():
        target_n = round(rate * total_orders)
        print(f"  {etype:24s} target={target_n:4d}  actual={actual_counts.get(etype, 0):4d}")

    dup_within_type = ground_truth_df.groupby("exception_type")["source_record_id"].apply(lambda x: x.duplicated().sum())
    print(f"\nDuplicate source_record_id within any single exception type (must be 0): {dup_within_type.sum()}")

    print(f"\nOutput written to data/raw/ (5 tables) and:\n  {GROUND_TRUTH_PATH}")


if __name__ == "__main__":
    main()
