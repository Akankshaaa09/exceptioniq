-- ExceptionIQ — Core Relational Model
-- Run AFTER 04_create_staging.sql.
--
-- Core is the trusted relational business layer.
-- It enforces keys and relationships, while preserving rows that can
-- legitimately participate in exception analysis.
--
-- IMPORTANT:
-- The intentionally duplicated / orphaned raw records are NOT silently
-- inserted into core when doing so would violate a primary/foreign key.
-- Core is therefore a constrained business model; staging remains the
-- evidence layer for source-quality problems.

DROP TABLE IF EXISTS core.payments CASCADE;
DROP TABLE IF EXISTS core.invoices CASCADE;
DROP TABLE IF EXISTS core.shipments CASCADE;
DROP TABLE IF EXISTS core.order_items CASCADE;
DROP TABLE IF EXISTS core.orders CASCADE;
DROP TABLE IF EXISTS core.contracts CASCADE;
DROP TABLE IF EXISTS core.products CASCADE;
DROP TABLE IF EXISTS core.customers CASCADE;


-- ================================================================
-- 1. CUSTOMERS
-- ================================================================

CREATE TABLE core.customers (
    customer_id TEXT PRIMARY KEY,
    customer_name TEXT,
    region TEXT NOT NULL,
    segment TEXT NOT NULL,
    signup_date DATE,
    created_at TIMESTAMP,
    CONSTRAINT customers_segment_chk
        CHECK (segment IN ('Standard', 'Strategic'))
);


INSERT INTO core.customers (
    customer_id,
    customer_name,
    region,
    segment,
    signup_date,
    created_at
)
SELECT
    customer_id,
    customer_name,
    region,
    segment,
    signup_date,
    created_at
FROM staging.customers
WHERE source_row_number = 1
  AND customer_id IS NOT NULL
  AND customer_name IS NOT NULL
  AND region IS NOT NULL
  AND segment IN ('Standard', 'Strategic');


-- ================================================================
-- 2. PRODUCTS
-- ================================================================

CREATE TABLE core.products (
    product_id TEXT PRIMARY KEY,
    product_name TEXT NOT NULL,
    category TEXT NOT NULL,
    list_price NUMERIC(14,2) NOT NULL,
    created_at TIMESTAMP,
    CONSTRAINT products_price_chk CHECK (list_price >= 0)
);


INSERT INTO core.products (
    product_id,
    product_name,
    category,
    list_price,
    created_at
)
SELECT
    product_id,
    product_name,
    category,
    list_price,
    created_at
FROM staging.products
WHERE source_row_number = 1
  AND product_id IS NOT NULL
  AND product_name IS NOT NULL
  AND category IS NOT NULL
  AND list_price IS NOT NULL
  AND list_price >= 0;


-- ================================================================
-- 3. CONTRACTS
-- ================================================================

CREATE TABLE core.contracts (
    contract_id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL REFERENCES core.customers(customer_id),
    contract_start_date DATE,
    contract_end_date DATE,
    payment_terms_days INTEGER NOT NULL,
    max_discount_pct NUMERIC(8,2) NOT NULL,
    sla_fulfillment_days INTEGER NOT NULL,
    status TEXT NOT NULL,

    CONSTRAINT contracts_terms_chk CHECK (payment_terms_days > 0),
    CONSTRAINT contracts_discount_chk CHECK (
        max_discount_pct >= 0 AND max_discount_pct <= 100
    ),
    CONSTRAINT contracts_sla_chk CHECK (sla_fulfillment_days > 0)
);


INSERT INTO core.contracts (
    contract_id,
    customer_id,
    contract_start_date,
    contract_end_date,
    payment_terms_days,
    max_discount_pct,
    sla_fulfillment_days,
    status
)
SELECT
    c.contract_id,
    c.customer_id,
    c.contract_start_date,
    c.contract_end_date,
    c.payment_terms_days::INTEGER,
    c.max_discount_pct,
    c.sla_fulfillment_days::INTEGER,
    c.status
FROM staging.contracts c
WHERE c.contract_id IS NOT NULL
  AND c.customer_id IS NOT NULL
  AND c.payment_terms_days IS NOT NULL
  AND c.max_discount_pct IS NOT NULL
  AND c.sla_fulfillment_days IS NOT NULL
  AND c.payment_terms_days::NUMERIC > 0
  AND c.max_discount_pct BETWEEN 0 AND 100
  AND c.sla_fulfillment_days::NUMERIC > 0
  AND EXISTS (
      SELECT 1
      FROM core.customers cu
      WHERE cu.customer_id = c.customer_id
  );


-- ================================================================
-- 4. ORDERS
-- ================================================================

CREATE TABLE core.orders (
    order_id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL REFERENCES core.customers(customer_id),
    contract_id TEXT NOT NULL REFERENCES core.contracts(contract_id),
    order_date DATE NOT NULL,
    discount_pct_applied NUMERIC(8,2) NOT NULL,
    promised_ship_date DATE NOT NULL,
    order_status TEXT NOT NULL,
    created_at TIMESTAMP,

    CONSTRAINT orders_discount_chk
        CHECK (discount_pct_applied >= 0),
    CONSTRAINT orders_promised_date_chk
        CHECK (promised_ship_date >= order_date)
);


INSERT INTO core.orders (
    order_id,
    customer_id,
    contract_id,
    order_date,
    discount_pct_applied,
    promised_ship_date,
    order_status,
    created_at
)
SELECT
    o.order_id,
    o.customer_id,
    o.contract_id,
    o.order_date,
    o.discount_pct_applied,
    o.promised_ship_date,
    o.order_status,
    o.created_at
FROM staging.orders o
WHERE o.exact_row_number = 1
  AND o.order_id IS NOT NULL
  AND o.customer_id IS NOT NULL
  AND o.contract_id IS NOT NULL
  AND o.order_date IS NOT NULL
  AND o.discount_pct_applied IS NOT NULL
  AND o.promised_ship_date IS NOT NULL
  AND o.order_status IS NOT NULL
  AND o.discount_pct_applied >= 0
  AND o.promised_ship_date >= o.order_date
  AND EXISTS (
      SELECT 1 FROM core.customers c
      WHERE c.customer_id = o.customer_id
  )
  AND EXISTS (
      SELECT 1 FROM core.contracts c
      WHERE c.contract_id = o.contract_id
        AND c.customer_id = o.customer_id
  );


-- ================================================================
-- 5. ORDER ITEMS
-- ================================================================

CREATE TABLE core.order_items (
    order_item_id TEXT PRIMARY KEY,
    order_id TEXT NOT NULL REFERENCES core.orders(order_id),
    product_id TEXT NOT NULL REFERENCES core.products(product_id),
    quantity_ordered NUMERIC(14,2) NOT NULL,
    unit_price_at_order NUMERIC(14,2) NOT NULL,
    line_total NUMERIC(16,2) NOT NULL,

    CONSTRAINT order_items_quantity_chk CHECK (quantity_ordered > 0),
    CONSTRAINT order_items_price_chk CHECK (unit_price_at_order >= 0),
    CONSTRAINT order_items_total_chk CHECK (line_total >= 0)
);


INSERT INTO core.order_items (
    order_item_id,
    order_id,
    product_id,
    quantity_ordered,
    unit_price_at_order,
    line_total
)
SELECT
    oi.order_item_id,
    oi.order_id,
    oi.product_id,
    oi.quantity_ordered,
    oi.unit_price_at_order,
    oi.line_total
FROM staging.order_items oi
WHERE oi.source_row_number = 1
  AND oi.order_item_id IS NOT NULL
  AND oi.order_id IS NOT NULL
  AND oi.product_id IS NOT NULL
  AND oi.quantity_ordered IS NOT NULL
  AND oi.unit_price_at_order IS NOT NULL
  AND oi.line_total IS NOT NULL
  AND oi.quantity_ordered > 0
  AND oi.unit_price_at_order >= 0
  AND oi.line_total >= 0
  AND EXISTS (
      SELECT 1 FROM core.orders o
      WHERE o.order_id = oi.order_id
  )
  AND EXISTS (
      SELECT 1 FROM core.products p
      WHERE p.product_id = oi.product_id
  );


-- ================================================================
-- 6. SHIPMENTS
-- ================================================================

CREATE TABLE core.shipments (
    shipment_id TEXT PRIMARY KEY,
    order_id TEXT NOT NULL REFERENCES core.orders(order_id),
    fulfillment_center TEXT NOT NULL,
    ship_date DATE NOT NULL,
    quantity_shipped NUMERIC(14,2) NOT NULL,
    status TEXT NOT NULL,

    CONSTRAINT shipments_quantity_chk CHECK (quantity_shipped > 0)
);


INSERT INTO core.shipments (
    shipment_id,
    order_id,
    fulfillment_center,
    ship_date,
    quantity_shipped,
    status
)
SELECT
    s.shipment_id,
    s.order_id,
    s.fulfillment_center,
    s.ship_date,
    s.quantity_shipped,
    s.status
FROM staging.shipments s
WHERE s.source_row_number = 1
  AND s.shipment_id IS NOT NULL
  AND s.order_id IS NOT NULL
  AND s.fulfillment_center IS NOT NULL
  AND s.ship_date IS NOT NULL
  AND s.quantity_shipped IS NOT NULL
  AND s.quantity_shipped > 0
  AND EXISTS (
      SELECT 1 FROM core.orders o
      WHERE o.order_id = s.order_id
  );


-- ================================================================
-- 7. INVOICES
-- ================================================================

CREATE TABLE core.invoices (
    invoice_id TEXT PRIMARY KEY,
    order_id TEXT NOT NULL REFERENCES core.orders(order_id),
    invoice_date DATE NOT NULL,
    invoice_amount NUMERIC(16,2) NOT NULL,
    expected_amount NUMERIC(16,2) NOT NULL,
    due_date DATE NOT NULL,
    status TEXT NOT NULL,

    CONSTRAINT invoices_amount_chk CHECK (invoice_amount >= 0),
    CONSTRAINT invoices_expected_chk CHECK (expected_amount >= 0),
    CONSTRAINT invoices_due_date_chk CHECK (due_date >= invoice_date)
);


INSERT INTO core.invoices (
    invoice_id,
    order_id,
    invoice_date,
    invoice_amount,
    expected_amount,
    due_date,
    status
)
SELECT
    i.invoice_id,
    i.order_id,
    i.invoice_date,
    i.invoice_amount,
    i.expected_amount,
    i.due_date,
    i.status
FROM staging.invoices i
WHERE i.invoice_id IS NOT NULL
  AND i.order_id IS NOT NULL
  AND i.invoice_date IS NOT NULL
  AND i.invoice_amount IS NOT NULL
  AND i.expected_amount IS NOT NULL
  AND i.due_date IS NOT NULL
  AND i.invoice_amount >= 0
  AND i.expected_amount >= 0
  AND i.due_date >= i.invoice_date
  AND EXISTS (
      SELECT 1 FROM core.orders o
      WHERE o.order_id = i.order_id
  );


-- ================================================================
-- 8. PAYMENTS
-- ================================================================

CREATE TABLE core.payments (
    payment_id TEXT PRIMARY KEY,
    invoice_id TEXT NOT NULL REFERENCES core.invoices(invoice_id),
    payment_date DATE NOT NULL,
    payment_amount NUMERIC(16,2) NOT NULL,
    status TEXT NOT NULL,

    CONSTRAINT payments_amount_chk CHECK (payment_amount >= 0)
);


INSERT INTO core.payments (
    payment_id,
    invoice_id,
    payment_date,
    payment_amount,
    status
)
SELECT
    p.payment_id,
    p.invoice_id,
    p.payment_date,
    p.payment_amount,
    p.status
FROM staging.payments p
WHERE p.source_row_number = 1
  AND p.payment_id IS NOT NULL
  AND p.invoice_id IS NOT NULL
  AND p.payment_date IS NOT NULL
  AND p.payment_amount IS NOT NULL
  AND p.payment_amount >= 0
  AND EXISTS (
      SELECT 1 FROM core.invoices i
      WHERE i.invoice_id = p.invoice_id
  );


-- ================================================================
-- CORE VALIDATION SUMMARY
-- ================================================================

SELECT 'customers' AS table_name, COUNT(*) AS rows FROM core.customers
UNION ALL
SELECT 'contracts', COUNT(*) FROM core.contracts
UNION ALL
SELECT 'products', COUNT(*) FROM core.products
UNION ALL
SELECT 'orders', COUNT(*) FROM core.orders
UNION ALL
SELECT 'order_items', COUNT(*) FROM core.order_items
UNION ALL
SELECT 'shipments', COUNT(*) FROM core.shipments
UNION ALL
SELECT 'invoices', COUNT(*) FROM core.invoices
UNION ALL
SELECT 'payments', COUNT(*) FROM core.payments
ORDER BY table_name;
