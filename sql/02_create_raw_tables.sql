-- ExceptionIQ — Raw landing tables
-- Raw is intentionally permissive: source fields are TEXT so malformed
-- source values can be loaded and assessed by the staging layer.

DROP TABLE IF EXISTS raw.ground_truth_exceptions;
DROP TABLE IF EXISTS raw.payments;
DROP TABLE IF EXISTS raw.invoices;
DROP TABLE IF EXISTS raw.shipments;
DROP TABLE IF EXISTS raw.order_items;
DROP TABLE IF EXISTS raw.orders;
DROP TABLE IF EXISTS raw.products;
DROP TABLE IF EXISTS raw.contracts;
DROP TABLE IF EXISTS raw.customers;

CREATE TABLE raw.customers (
    customer_id TEXT,
    customer_name TEXT,
    region TEXT,
    segment TEXT,
    signup_date TEXT,
    created_at TEXT
);

CREATE TABLE raw.contracts (
    contract_id TEXT,
    customer_id TEXT,
    contract_start_date TEXT,
    contract_end_date TEXT,
    payment_terms_days TEXT,
    max_discount_pct TEXT,
    sla_fulfillment_days TEXT,
    status TEXT
);

CREATE TABLE raw.products (
    product_id TEXT,
    product_name TEXT,
    category TEXT,
    list_price TEXT,
    created_at TEXT
);

CREATE TABLE raw.orders (
    order_id TEXT,
    customer_id TEXT,
    contract_id TEXT,
    order_date TEXT,
    discount_pct_applied TEXT,
    promised_ship_date TEXT,
    order_status TEXT,
    created_at TEXT
);

CREATE TABLE raw.order_items (
    order_item_id TEXT,
    order_id TEXT,
    product_id TEXT,
    quantity_ordered TEXT,
    unit_price_at_order TEXT,
    line_total TEXT
);

CREATE TABLE raw.shipments (
    shipment_id TEXT,
    order_id TEXT,
    fulfillment_center TEXT,
    ship_date TEXT,
    quantity_shipped TEXT,
    status TEXT
);

CREATE TABLE raw.invoices (
    invoice_id TEXT,
    order_id TEXT,
    invoice_date TEXT,
    invoice_amount TEXT,
    expected_amount TEXT,
    due_date TEXT,
    status TEXT
);

CREATE TABLE raw.payments (
    payment_id TEXT,
    invoice_id TEXT,
    payment_date TEXT,
    payment_amount TEXT,
    status TEXT
);

CREATE TABLE raw.ground_truth_exceptions (
    ground_truth_id TEXT,
    category TEXT,
    exception_type TEXT,
    source_table TEXT,
    source_record_id TEXT,
    planted_condition TEXT,
    expected_financial_impact TEXT,
    generation_timestamp TEXT
);
