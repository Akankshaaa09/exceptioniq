"""
inject_data_quality_issues.py

The last mutation to data/raw/ before it gets frozen and handed to
the ingestion/validation layer. Deliberately separate from
inject_exceptions.py: these are TECHNICAL pipeline problems (a messy
extract), not business process failures. Testing different things -
this script tests whether ingestion validation catches malformed
data; inject_exceptions.py tests whether the detection engine catches
business rule violations.

Per 03_data_generation_spec.md, Section 5:
  - Duplicate raw row (exact row appears twice - an extract glitch,
    NOT the same thing as the business duplicate_invoice exception,
    which creates a NEW invoice_id. This is the SAME id, SAME every
    field, literally copy-pasted.)
  - Orphan reference (a foreign key pointing at nothing)
  - Malformed/missing required field
  - Near-duplicate customer record - SUBSTITUTED for the spec's
    original "cross-system naming inconsistency" example, which
    assumed customer_name exists in two source systems. It doesn't -
    the locked schema (02_data_model_and_dictionary.md) has
    customer_name in exactly one table. A near-duplicate customer
    (same real business, two different customer_id values, slightly
    different name formatting) is the schema-honest substitute, and
    arguably a more common real-world data-quality problem anyway.

All ~25-30 issues avoid order_ids already used by inject_exceptions.py
(where an order-level anchor applies), for the same reason exception
injection enforced its own exclusivity: keeping every planted problem
attributable to exactly one root cause, not stacking a technical
extract glitch on top of an already-planted business exception.

Ground truth is appended to the SAME ground_truth_exceptions.csv from
inject_exceptions.py (category='data_quality_issue'), per the unified
log design in 03_data_generation_spec.md, Section 6 - not a separate
file.
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
ORDERS_PATH = os.path.join(BASE, "data", "raw", "commercial", "orders.csv")
ORDER_ITEMS_PATH = os.path.join(BASE, "data", "raw", "operations", "order_items.csv")
INVOICES_PATH = os.path.join(BASE, "data", "raw", "finance", "invoices.csv")
GROUND_TRUTH_PATH = os.path.join(BASE, "data", "ground_truth", "ground_truth_exceptions.csv")

used_order_ids_dq = set()
ground_truth_rows = []


def load_inputs():
    # Deliberately NOT using parse_dates here - this script injects a
    # malformed date string into one column, which is impossible to do
    # cleanly on an already-typed datetime64 column. Everything stays
    # as plain strings/objects, which is fine since no date arithmetic
    # happens in this script.
    customers = pd.read_csv(CUSTOMERS_PATH)
    orders = pd.read_csv(ORDERS_PATH)
    order_items = pd.read_csv(ORDER_ITEMS_PATH)
    invoices = pd.read_csv(INVOICES_PATH)
    shipments = pd.read_csv(os.path.join(BASE, "data", "raw", "operations", "shipments.csv"))
    payments = pd.read_csv(os.path.join(BASE, "data", "raw", "finance", "payments.csv"))
    ground_truth = pd.read_csv(GROUND_TRUTH_PATH)
    return customers, orders, order_items, invoices, shipments, payments, ground_truth


def next_gt_id(existing_gt):
    existing_nums = existing_gt["ground_truth_id"].str.replace("GT", "", regex=False).astype(int)
    return existing_nums.max() + 1


def log_ground_truth(counter, issue_type, source_table, source_record_id, planted_condition):
    counter[0] += 1
    ground_truth_rows.append({
        "ground_truth_id": f"GT{counter[0]:05d}",
        "category": "data_quality_issue",
        "exception_type": issue_type,
        "source_table": source_table,
        "source_record_id": source_record_id,
        "planted_condition": planted_condition,
        "expected_financial_impact": None,  # data-quality issues have no dollar impact, per Section 6
        "generation_timestamp": pd.Timestamp.now(),
    })


def pick_eligible_orders(order_ids, n, exclude=used_order_ids_dq):
    pool = [oid for oid in order_ids if oid not in exclude]
    return list(np.random.choice(pool, size=n, replace=False))


def main():
    customers, orders, order_items, invoices, shipments, payments, ground_truth = load_inputs()
    gt_counter = [next_gt_id(ground_truth) - 1]  # log_ground_truth increments before using

    # source_record_id is a MIX of order_id/invoice_id/shipment_id/payment_id
    # depending on exception type - map every one back to its order_id
    # properly, not just the invoice-anchored ones, or shipment- and
    # payment-anchored exceptions (late_fulfillment, partial_shipment,
    # partial_payment, overdue_payment, duplicate_payment) would leak
    # through unexcluded.
    biz = ground_truth[ground_truth["category"] == "business_exception"]
    invoice_to_order = invoices.set_index("invoice_id")["order_id"]
    shipment_to_order = shipments.set_index("shipment_id")["order_id"]
    payment_to_invoice = payments.set_index("payment_id")["invoice_id"]

    business_exception_order_ids = set()
    for _, row in biz.iterrows():
        rid, table = row["source_record_id"], row["source_table"]
        if table == "orders":
            business_exception_order_ids.add(rid)
        elif table == "invoices" and rid in invoice_to_order.index:
            business_exception_order_ids.add(invoice_to_order.loc[rid])
        elif table == "shipments" and rid in shipment_to_order.index:
            business_exception_order_ids.add(shipment_to_order.loc[rid])
        elif table == "payments" and rid in payment_to_invoice.index:
            inv_id = payment_to_invoice.loc[rid]
            if inv_id in invoice_to_order.index:
                business_exception_order_ids.add(invoice_to_order.loc[inv_id])

    eligible_order_ids = [oid for oid in orders["order_id"] if oid not in business_exception_order_ids]
    print(f"Eligible orders for DQ injection (excluding {len(business_exception_order_ids)} business-exception orders): {len(eligible_order_ids)}")

    # ---------------------------------------------------------------
    # 1. Duplicate raw row - 5 orders + 5 invoices, exact copy-paste
    # ---------------------------------------------------------------
    targets = pick_eligible_orders(eligible_order_ids, 5)
    dup_order_rows = []
    for order_id in targets:
        row = orders[orders["order_id"] == order_id].iloc[0].to_dict()
        dup_order_rows.append(row)
        log_ground_truth(gt_counter, "duplicate_raw_row", "orders", order_id,
                          f"order_id {order_id} appears twice in the raw extract, identical in every field")
        used_order_ids_dq.add(order_id)
    orders = pd.concat([orders, pd.DataFrame(dup_order_rows)], ignore_index=True)

    remaining_eligible = [oid for oid in eligible_order_ids if oid not in used_order_ids_dq]
    targets = pick_eligible_orders(remaining_eligible, 5)
    dup_invoice_rows = []
    for order_id in targets:
        inv_row = invoices[invoices["order_id"] == order_id].iloc[0].to_dict()
        dup_invoice_rows.append(inv_row)
        log_ground_truth(gt_counter, "duplicate_raw_row", "invoices", inv_row["invoice_id"],
                          f"invoice_id {inv_row['invoice_id']} appears twice in the raw extract, identical in every field - "
                          f"NOT the same thing as a business duplicate_invoice, which has a different invoice_id")
        used_order_ids_dq.add(order_id)
    invoices = pd.concat([invoices, pd.DataFrame(dup_invoice_rows)], ignore_index=True)
    print(f"1. Duplicate raw rows: {len(dup_order_rows)} orders + {len(dup_invoice_rows)} invoices")

    # ---------------------------------------------------------------
    # 2. Orphan reference - 4 order_items (bad product_id) + 4 invoices (bad order_id)
    # ---------------------------------------------------------------
    remaining_eligible = [oid for oid in eligible_order_ids if oid not in used_order_ids_dq]
    targets = pick_eligible_orders(remaining_eligible, 4)
    for order_id in targets:
        item_idx = order_items.index[order_items["order_id"] == order_id][0]
        old_product_id = order_items.at[item_idx, "product_id"]
        order_items.at[item_idx, "product_id"] = "PROD99999"
        log_ground_truth(gt_counter, "orphan_reference", "order_items", order_items.at[item_idx, "order_item_id"],
                          f"product_id changed from {old_product_id} to PROD99999, which does not exist in products.csv")
        used_order_ids_dq.add(order_id)

    remaining_eligible = [oid for oid in eligible_order_ids if oid not in used_order_ids_dq]
    targets = pick_eligible_orders(remaining_eligible, 4)
    for order_id in targets:
        inv_idx = invoices.index[invoices["order_id"] == order_id][0]
        invoice_id = invoices.at[inv_idx, "invoice_id"]
        invoices.at[inv_idx, "order_id"] = "ORD999999"
        log_ground_truth(gt_counter, "orphan_reference", "invoices", invoice_id,
                          f"order_id changed from {order_id} to ORD999999, which does not exist in orders.csv")
        used_order_ids_dq.add(order_id)
    print("2. Orphan references: 4 order_items + 4 invoices")

    # ---------------------------------------------------------------
    # 3. Malformed/missing field - 3 customers (null name), 3 order_items
    #    (negative qty), 2 orders (malformed date string)
    # ---------------------------------------------------------------
    null_name_customers = np.random.choice(customers["customer_id"], size=3, replace=False)
    for cust_id in null_name_customers:
        cust_idx = customers.index[customers["customer_id"] == cust_id][0]
        customers.at[cust_idx, "customer_name"] = ""
        log_ground_truth(gt_counter, "missing_required_field", "customers", cust_id,
                          "customer_name set to empty string - becomes null/NaN on CSV read-back, "
                          "which is actually the more realistic representation of a missing required field")

    remaining_eligible = [oid for oid in eligible_order_ids if oid not in used_order_ids_dq]
    targets = pick_eligible_orders(remaining_eligible, 3)
    for order_id in targets:
        item_idx = order_items.index[order_items["order_id"] == order_id][0]
        old_qty = order_items.at[item_idx, "quantity_ordered"]
        order_items.at[item_idx, "quantity_ordered"] = -abs(int(old_qty))
        log_ground_truth(gt_counter, "malformed_field", "order_items", order_items.at[item_idx, "order_item_id"],
                          f"quantity_ordered set to {-abs(int(old_qty))} (was {old_qty}) - negative quantity, impossible value")
        used_order_ids_dq.add(order_id)

    remaining_eligible = [oid for oid in eligible_order_ids if oid not in used_order_ids_dq]
    targets = pick_eligible_orders(remaining_eligible, 2)
    for order_id in targets:
        order_idx = orders.index[orders["order_id"] == order_id][0]
        orders.at[order_idx, "order_date"] = "0000-00-00"
        log_ground_truth(gt_counter, "malformed_field", "orders", order_id,
                          "order_date set to '0000-00-00' - unparseable, a common legacy-system placeholder for a missing date")
        used_order_ids_dq.add(order_id)
    print("3. Malformed/missing fields: 3 customers + 3 order_items + 2 orders")

    # ---------------------------------------------------------------
    # 4. Near-duplicate customer record (schema-honest substitute for
    #    the spec's cross-system naming inconsistency example)
    # ---------------------------------------------------------------
    name_variants = [
        lambda n: n.replace(" Inc", "").replace(" LLC", "").strip(),  # drop legal suffix
        lambda n: n.upper(),  # case difference
        lambda n: n + "  ",  # trailing whitespace
    ]
    source_customers = customers[~customers["customer_id"].isin(null_name_customers)].sample(3, random_state=SEED)
    next_cust_num = int(customers["customer_id"].str.replace("CUST", "", regex=False).astype(int).max()) + 1
    new_customer_rows = []
    for i, (_, row) in enumerate(source_customers.iterrows()):
        new_id = f"CUST{next_cust_num:05d}"
        next_cust_num += 1
        near_dup_name = name_variants[i % len(name_variants)](row["customer_name"])
        new_customer_rows.append({
            "customer_id": new_id,
            "customer_name": near_dup_name,
            "region": row["region"],
            "segment": row["segment"],
            "signup_date": row["signup_date"],
            "created_at": pd.Timestamp.now(),
        })
        log_ground_truth(gt_counter, "near_duplicate_customer", "customers", new_id,
                          f"likely the same business as {row['customer_id']} ('{row['customer_name']}'), "
                          f"entered again as '{near_dup_name}' - no cross-system field exists to test spelling "
                          f"inconsistency directly, so this substitutes an equally realistic entity-resolution problem")
    customers = pd.concat([customers, pd.DataFrame(new_customer_rows)], ignore_index=True)
    print(f"4. Near-duplicate customer records: {len(new_customer_rows)}")

    # ---- write everything out ----
    orders.to_csv(ORDERS_PATH, index=False)
    order_items.to_csv(ORDER_ITEMS_PATH, index=False)
    invoices.to_csv(INVOICES_PATH, index=False)
    customers.to_csv(CUSTOMERS_PATH, index=False)

    new_gt = pd.DataFrame(ground_truth_rows)
    full_gt = pd.concat([ground_truth, new_gt], ignore_index=True)
    full_gt.to_csv(GROUND_TRUTH_PATH, index=False)

    # ---- validation ----
    print(f"\n{'='*60}\nDATA QUALITY INJECTION SUMMARY\n{'='*60}")
    print(f"New data-quality ground truth rows: {len(new_gt)}")
    print(f"Total ground truth rows now (business + DQ): {len(full_gt)}")
    print("\nBy type:")
    print(new_gt["exception_type"].value_counts())

    print("\nDirect re-checks against the actual written files:")
    orders_check = pd.read_csv(ORDERS_PATH)
    invoices_check = pd.read_csv(INVOICES_PATH)
    order_items_check = pd.read_csv(ORDER_ITEMS_PATH)
    customers_check = pd.read_csv(CUSTOMERS_PATH)
    products_ids = pd.read_csv(os.path.join(BASE, "data", "raw", "commercial", "products.csv"))["product_id"]

    print(f"  Exact duplicate order rows: {orders_check.duplicated().sum()} (expect 5)")
    print(f"  Exact duplicate invoice rows: {invoices_check.duplicated().sum()} (expect 5)")
    print(f"  order_items with orphan product_id: {(~order_items_check['product_id'].isin(products_ids)).sum()} (expect 4)")
    print(f"  invoices with orphan order_id: {(~invoices_check['order_id'].isin(orders_check['order_id'])).sum()} (expect 4, "
          f"note: these will ALSO show up as unmatched joins generally, that's the point)")
    print(f"  customers with missing name: {customers_check['customer_name'].isna().sum()} (expect 3 - "
          f"shows as NaN, not empty string, because CSV round-trips a blank field to null by default)")
    print(f"  order_items with negative quantity: {(order_items_check['quantity_ordered'] < 0).sum()} (expect 3)")
    print(f"  orders with unparseable order_date: {(orders_check['order_date'] == '0000-00-00').sum()} (expect 2)")
    print(f"  customers total (expect original + 3 near-dup): {len(customers_check)}")


if __name__ == "__main__":
    main()
