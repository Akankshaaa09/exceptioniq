-- ExceptionIQ — Staging Layer
-- Run this AFTER:
--   01_create_schemas.sql
--   02_create_raw_tables.sql
--   raw CSV loading
--
-- Purpose:
--   raw     = faithful landing zone; everything is TEXT and nothing is silently fixed
--   staging = typed/normalized working layer; suspicious values become NULL and receive
--             explicit quality flags so downstream logic can distinguish "missing" from
--             "valid zero" and "bad source value".
--
-- IMPORTANT:
--   Staging does NOT remove duplicate rows or orphan records.
--   Those are intentionally retained and flagged.

DROP TABLE IF EXISTS staging.ground_truth_exceptions;
DROP TABLE IF EXISTS staging.payments;
DROP TABLE IF EXISTS staging.invoices;
DROP TABLE IF EXISTS staging.shipments;
DROP TABLE IF EXISTS staging.order_items;
DROP TABLE IF EXISTS staging.orders;
DROP TABLE IF EXISTS staging.products;
DROP TABLE IF EXISTS staging.contracts;
DROP TABLE IF EXISTS staging.customers;


-- ================================================================
-- 1. CUSTOMERS
-- ================================================================

CREATE TABLE staging.customers AS
SELECT
    customer_id,
    NULLIF(TRIM(customer_name), '') AS customer_name,
    NULLIF(TRIM(region), '') AS region,
    NULLIF(TRIM(segment), '') AS segment,

    CASE
        WHEN signup_date ~ '^\d{4}-\d{2}-\d{2}$'
             AND signup_date <> '0000-00-00'
        THEN signup_date::DATE
        ELSE NULL
    END AS signup_date,

    CASE
        WHEN created_at ~ '^\d{4}-\d{2}-\d{2}'
             AND LEFT(created_at, 10) <> '0000-00-00'
        THEN created_at::TIMESTAMP
        ELSE NULL
    END AS created_at,

    CASE WHEN NULLIF(TRIM(customer_name), '') IS NULL
         THEN TRUE ELSE FALSE END AS dq_missing_customer_name,

    CASE WHEN signup_date IS NOT NULL
              AND signup_date !~ '^\d{4}-\d{2}-\d{2}$'
         THEN TRUE ELSE FALSE END AS dq_invalid_signup_date,

    ROW_NUMBER() OVER (
        PARTITION BY customer_id
        ORDER BY customer_id
    ) AS source_row_number

FROM raw.customers;


-- ================================================================
-- 2. CONTRACTS
-- ================================================================

CREATE TABLE staging.contracts AS
SELECT
    contract_id,
    customer_id,

    CASE
        WHEN contract_start_date ~ '^\d{4}-\d{2}-\d{2}$'
             AND contract_start_date <> '0000-00-00'
        THEN contract_start_date::DATE
        ELSE NULL
    END AS contract_start_date,

    CASE
        WHEN contract_end_date ~ '^\d{4}-\d{2}-\d{2}$'
             AND contract_end_date <> '0000-00-00'
        THEN contract_end_date::DATE
        ELSE NULL
    END AS contract_end_date,

    CASE
        WHEN payment_terms_days ~ '^-?\d+(\.\d+)?$'
        THEN payment_terms_days::NUMERIC
        ELSE NULL
    END AS payment_terms_days,

    CASE
        WHEN max_discount_pct ~ '^-?\d+(\.\d+)?$'
        THEN max_discount_pct::NUMERIC
        ELSE NULL
    END AS max_discount_pct,

    CASE
        WHEN sla_fulfillment_days ~ '^-?\d+(\.\d+)?$'
        THEN sla_fulfillment_days::NUMERIC
        ELSE NULL
    END AS sla_fulfillment_days,

    NULLIF(TRIM(status), '') AS status,

    CASE WHEN payment_terms_days !~ '^-?\d+(\.\d+)?$'
         THEN TRUE ELSE FALSE END AS dq_invalid_payment_terms,

    CASE WHEN max_discount_pct !~ '^-?\d+(\.\d+)?$'
         THEN TRUE ELSE FALSE END AS dq_invalid_discount,

    CASE WHEN sla_fulfillment_days !~ '^-?\d+(\.\d+)?$'
         THEN TRUE ELSE FALSE END AS dq_invalid_sla,

    ROW_NUMBER() OVER (
        PARTITION BY contract_id
        ORDER BY contract_id
    ) AS source_row_number

FROM raw.contracts;


-- ================================================================
-- 3. PRODUCTS
-- ================================================================

CREATE TABLE staging.products AS
SELECT
    product_id,
    NULLIF(TRIM(product_name), '') AS product_name,
    NULLIF(TRIM(category), '') AS category,

    CASE
        WHEN list_price ~ '^-?\d+(\.\d+)?$'
        THEN list_price::NUMERIC(14,2)
        ELSE NULL
    END AS list_price,

    CASE
        WHEN created_at ~ '^\d{4}-\d{2}-\d{2}'
             AND LEFT(created_at, 10) <> '0000-00-00'
        THEN created_at::TIMESTAMP
        ELSE NULL
    END AS created_at,

    CASE WHEN list_price !~ '^-?\d+(\.\d+)?$'
         THEN TRUE ELSE FALSE END AS dq_invalid_list_price,

    ROW_NUMBER() OVER (
        PARTITION BY product_id
        ORDER BY product_id
    ) AS source_row_number

FROM raw.products;


-- ================================================================
-- 4. ORDERS
-- ================================================================

CREATE TABLE staging.orders AS
SELECT
    order_id,
    customer_id,
    contract_id,

    CASE
        WHEN order_date ~ '^\d{4}-\d{2}-\d{2}$'
             AND order_date <> '0000-00-00'
        THEN order_date::DATE
        ELSE NULL
    END AS order_date,

    CASE
        WHEN discount_pct_applied ~ '^-?\d+(\.\d+)?$'
        THEN discount_pct_applied::NUMERIC(8,2)
        ELSE NULL
    END AS discount_pct_applied,

    CASE
        WHEN promised_ship_date ~ '^\d{4}-\d{2}-\d{2}$'
             AND promised_ship_date <> '0000-00-00'
        THEN promised_ship_date::DATE
        ELSE NULL
    END AS promised_ship_date,

    NULLIF(TRIM(order_status), '') AS order_status,

    CASE
        WHEN created_at ~ '^\d{4}-\d{2}-\d{2}'
             AND LEFT(created_at, 10) <> '0000-00-00'
        THEN created_at::TIMESTAMP
        ELSE NULL
    END AS created_at,

    CASE WHEN order_date IS NOT NULL
              AND order_date !~ '^\d{4}-\d{2}-\d{2}$'
         THEN TRUE ELSE FALSE END AS dq_invalid_order_date,

    CASE WHEN discount_pct_applied IS NOT NULL
              AND discount_pct_applied !~ '^-?\d+(\.\d+)?$'
         THEN TRUE ELSE FALSE END AS dq_invalid_discount,

    ROW_NUMBER() OVER (
        PARTITION BY
            order_id, customer_id, contract_id, order_date,
            discount_pct_applied, promised_ship_date, order_status, created_at
        ORDER BY order_id
    ) AS exact_row_number

FROM raw.orders;


-- ================================================================
-- 5. ORDER ITEMS
-- ================================================================

CREATE TABLE staging.order_items AS
SELECT
    order_item_id,
    order_id,
    product_id,

    CASE
        WHEN quantity_ordered ~ '^-?\d+(\.\d+)?$'
        THEN quantity_ordered::NUMERIC(14,2)
        ELSE NULL
    END AS quantity_ordered,

    CASE
        WHEN unit_price_at_order ~ '^-?\d+(\.\d+)?$'
        THEN unit_price_at_order::NUMERIC(14,2)
        ELSE NULL
    END AS unit_price_at_order,

    CASE
        WHEN line_total ~ '^-?\d+(\.\d+)?$'
        THEN line_total::NUMERIC(16,2)
        ELSE NULL
    END AS line_total,

    CASE
        WHEN quantity_ordered ~ '^-?\d+(\.\d+)?$'
             AND quantity_ordered::NUMERIC < 0
        THEN TRUE ELSE FALSE
    END AS dq_negative_quantity,

    CASE WHEN product_id IS NOT NULL
              AND NOT EXISTS (
                  SELECT 1
                  FROM raw.products p
                  WHERE p.product_id = raw.order_items.product_id
              )
         THEN TRUE ELSE FALSE END AS dq_orphan_product,

    ROW_NUMBER() OVER (
        PARTITION BY order_item_id
        ORDER BY order_item_id
    ) AS source_row_number

FROM raw.order_items;


-- ================================================================
-- 6. SHIPMENTS
-- ================================================================

CREATE TABLE staging.shipments AS
SELECT
    shipment_id,
    order_id,
    NULLIF(TRIM(fulfillment_center), '') AS fulfillment_center,

    CASE
        WHEN ship_date ~ '^\d{4}-\d{2}-\d{2}$'
             AND ship_date <> '0000-00-00'
        THEN ship_date::DATE
        ELSE NULL
    END AS ship_date,

    CASE
        WHEN quantity_shipped ~ '^-?\d+(\.\d+)?$'
        THEN quantity_shipped::NUMERIC(14,2)
        ELSE NULL
    END AS quantity_shipped,

    NULLIF(TRIM(status), '') AS status,

    CASE WHEN quantity_shipped ~ '^-?\d+(\.\d+)?$'
              AND quantity_shipped::NUMERIC < 0
         THEN TRUE ELSE FALSE END AS dq_negative_quantity,

    ROW_NUMBER() OVER (
        PARTITION BY shipment_id
        ORDER BY shipment_id
    ) AS source_row_number

FROM raw.shipments;


-- ================================================================
-- 7. INVOICES
-- ================================================================

CREATE TABLE staging.invoices AS
SELECT
    invoice_id,
    order_id,

    CASE
        WHEN invoice_date ~ '^\d{4}-\d{2}-\d{2}$'
             AND invoice_date <> '0000-00-00'
        THEN invoice_date::DATE
        ELSE NULL
    END AS invoice_date,

    CASE
        WHEN invoice_amount ~ '^-?\d+(\.\d+)?$'
        THEN invoice_amount::NUMERIC(16,2)
        ELSE NULL
    END AS invoice_amount,

    CASE
        WHEN expected_amount ~ '^-?\d+(\.\d+)?$'
        THEN expected_amount::NUMERIC(16,2)
        ELSE NULL
    END AS expected_amount,

    CASE
        WHEN due_date ~ '^\d{4}-\d{2}-\d{2}$'
             AND due_date <> '0000-00-00'
        THEN due_date::DATE
        ELSE NULL
    END AS due_date,

    NULLIF(TRIM(status), '') AS status,

    CASE WHEN order_id IS NOT NULL
              AND NOT EXISTS (
                  SELECT 1
                  FROM raw.orders o
                  WHERE o.order_id = raw.invoices.order_id
              )
         THEN TRUE ELSE FALSE END AS dq_orphan_order,

    ROW_NUMBER() OVER (
        PARTITION BY
            invoice_id, order_id, invoice_date,
            invoice_amount, expected_amount, due_date, status
        ORDER BY invoice_id
    ) AS exact_row_number

FROM raw.invoices;


-- ================================================================
-- 8. PAYMENTS
-- ================================================================

CREATE TABLE staging.payments AS
SELECT
    payment_id,
    invoice_id,

    CASE
        WHEN payment_date ~ '^\d{4}-\d{2}-\d{2}$'
             AND payment_date <> '0000-00-00'
        THEN payment_date::DATE
        ELSE NULL
    END AS payment_date,

    CASE
        WHEN payment_amount ~ '^-?\d+(\.\d+)?$'
        THEN payment_amount::NUMERIC(16,2)
        ELSE NULL
    END AS payment_amount,

    NULLIF(TRIM(status), '') AS status,

    CASE WHEN invoice_id IS NOT NULL
              AND NOT EXISTS (
                  SELECT 1
                  FROM raw.invoices i
                  WHERE i.invoice_id = raw.payments.invoice_id
              )
         THEN TRUE ELSE FALSE END AS dq_orphan_invoice,

    ROW_NUMBER() OVER (
        PARTITION BY payment_id
        ORDER BY payment_id
    ) AS source_row_number

FROM raw.payments;


-- ================================================================
-- 9. GROUND TRUTH
-- ================================================================

CREATE TABLE staging.ground_truth_exceptions AS
SELECT
    ground_truth_id,
    NULLIF(TRIM(category), '') AS category,
    NULLIF(TRIM(exception_type), '') AS exception_type,
    NULLIF(TRIM(source_table), '') AS source_table,
    NULLIF(TRIM(source_record_id), '') AS source_record_id,
    NULLIF(TRIM(planted_condition), '') AS planted_condition,

    CASE
        WHEN expected_financial_impact ~ '^-?\d+(\.\d+)?$'
        THEN expected_financial_impact::NUMERIC(16,2)
        ELSE NULL
    END AS expected_financial_impact,

    CASE
        WHEN generation_timestamp ~ '^\d{4}-\d{2}-\d{2}'
             AND LEFT(generation_timestamp, 10) <> '0000-00-00'
        THEN generation_timestamp::TIMESTAMP
        ELSE NULL
    END AS generation_timestamp

FROM raw.ground_truth_exceptions;


-- ================================================================
-- STAGING SUMMARY
-- ================================================================

SELECT 'customers' AS table_name, COUNT(*) AS rows FROM staging.customers
UNION ALL
SELECT 'contracts', COUNT(*) FROM staging.contracts
UNION ALL
SELECT 'products', COUNT(*) FROM staging.products
UNION ALL
SELECT 'orders', COUNT(*) FROM staging.orders
UNION ALL
SELECT 'order_items', COUNT(*) FROM staging.order_items
UNION ALL
SELECT 'shipments', COUNT(*) FROM staging.shipments
UNION ALL
SELECT 'invoices', COUNT(*) FROM staging.invoices
UNION ALL
SELECT 'payments', COUNT(*) FROM staging.payments
UNION ALL
SELECT 'ground_truth_exceptions', COUNT(*) FROM staging.ground_truth_exceptions
ORDER BY table_name;
