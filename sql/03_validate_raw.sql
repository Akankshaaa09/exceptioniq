-- Raw-layer validation for the intentionally dirty ExceptionIQ dataset.
-- These are diagnostic queries, not constraints. Raw must accept the source
-- extract; staging/core will enforce usable types and business integrity.

-- 1. Row counts
SELECT 'customers' AS table_name, COUNT(*) AS row_count FROM raw.customers
UNION ALL SELECT 'contracts', COUNT(*) FROM raw.contracts
UNION ALL SELECT 'products', COUNT(*) FROM raw.products
UNION ALL SELECT 'orders', COUNT(*) FROM raw.orders
UNION ALL SELECT 'order_items', COUNT(*) FROM raw.order_items
UNION ALL SELECT 'shipments', COUNT(*) FROM raw.shipments
UNION ALL SELECT 'invoices', COUNT(*) FROM raw.invoices
UNION ALL SELECT 'payments', COUNT(*) FROM raw.payments
UNION ALL SELECT 'ground_truth', COUNT(*) FROM qa.ground_truth_exceptions;

-- 2. Exact duplicate source rows (expected: 5 orders + 5 invoices)
SELECT 'orders' AS table_name, COUNT(*) - COUNT(DISTINCT (order_id, customer_id, contract_id,
    order_date, discount_pct_applied, promised_ship_date, order_status, created_at)) AS duplicate_rows
FROM raw.orders
UNION ALL
SELECT 'invoices', COUNT(*) - COUNT(DISTINCT (invoice_id, order_id, invoice_date,
    invoice_amount, expected_amount, due_date, status))
FROM raw.invoices;

-- 3. Orphan product references (expected: 4)
SELECT COUNT(*) AS orphan_product_refs
FROM raw.order_items oi
LEFT JOIN raw.products p ON p.product_id = oi.product_id
WHERE p.product_id IS NULL;

-- 4. Orphan order references in invoices (expected: 4)
SELECT COUNT(*) AS orphan_invoice_order_refs
FROM raw.invoices i
LEFT JOIN raw.orders o ON o.order_id = i.order_id
WHERE o.order_id IS NULL;

-- 5. Missing customer names (expected: 3)
SELECT COUNT(*) AS missing_customer_names
FROM raw.customers
WHERE NULLIF(TRIM(customer_name), '') IS NULL;

-- 6. Negative quantities (expected: 3)
SELECT COUNT(*) AS negative_ordered_qty
FROM raw.order_items
WHERE quantity_ordered ~ '^-?[0-9]+$'
  AND CAST(quantity_ordered AS INTEGER) < 0;

-- 7. Unparseable order dates (expected: 2)
SELECT COUNT(*) AS malformed_order_dates
FROM raw.orders
WHERE order_date = '0000-00-00';

-- 8. Unified ground-truth split
SELECT category, exception_type, COUNT(*) AS planted_count
FROM qa.ground_truth_exceptions
GROUP BY category, exception_type
ORDER BY category, exception_type;

-- 9. Ground-truth total
SELECT COUNT(*) AS total_ground_truth_rows
FROM qa.ground_truth_exceptions;
