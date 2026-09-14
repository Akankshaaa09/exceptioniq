-- ExceptionIQ — Exception Detection
-- Run AFTER 05_create_core.sql.
--
-- This is the first analytical layer: independently detect business exceptions
-- from the trusted core model. Ground truth is NOT used by these rules.
--
-- Output:
--   analytics.detected_exceptions
--
-- Standard fields support the later workflow:
--   Exception -> Evidence -> Impact -> Priority -> Action -> Outcome
--
-- Notes:
-- * Rules are deterministic and explainable.
-- * `confidence = 1.00` means the rule condition is deterministically satisfied;
--   it is NOT a probability that the business rule is "true".
-- * Missing-invoice threshold is 7 days after shipment for V1.
-- * Core intentionally excludes records that cannot satisfy core integrity rules.
--   Source-quality issues remain available in raw/staging and will be handled
--   separately in the data-quality analytics layer.


DROP TABLE IF EXISTS analytics.detected_exceptions;


CREATE TABLE analytics.detected_exceptions (
    detection_id BIGSERIAL PRIMARY KEY,
    exception_type TEXT NOT NULL,
    source_table TEXT NOT NULL,
    source_record_id TEXT NOT NULL,
    customer_id TEXT,
    detected_date DATE NOT NULL,

    severity TEXT NOT NULL,
    confidence NUMERIC(5,2) NOT NULL,

    gross_exposure NUMERIC(16,2) NOT NULL DEFAULT 0,
    estimated_recoverable NUMERIC(16,2) NOT NULL DEFAULT 0,

    recurrence_count_30d INTEGER NOT NULL DEFAULT 1,

    evidence_summary TEXT NOT NULL,

    CONSTRAINT detected_severity_chk
        CHECK (severity IN ('Critical', 'High', 'Medium', 'Low')),
    CONSTRAINT detected_confidence_chk
        CHECK (confidence >= 0 AND confidence <= 1),
    CONSTRAINT detected_gross_chk
        CHECK (gross_exposure >= 0),
    CONSTRAINT detected_recoverable_chk
        CHECK (estimated_recoverable >= 0)
);


-- ================================================================
-- Detection CTEs
-- ================================================================

WITH

-- Order-level value used by several order-based exceptions.
order_value AS (
    SELECT
        o.order_id,
        o.customer_id,
        o.order_date,
        o.discount_pct_applied,
        c.max_discount_pct,
        o.promised_ship_date,
        c.sla_fulfillment_days,
        COALESCE(SUM(oi.line_total), 0)::NUMERIC(16,2) AS order_value
    FROM core.orders o
    JOIN core.contracts c
      ON c.contract_id = o.contract_id
    LEFT JOIN core.order_items oi
      ON oi.order_id = o.order_id
    GROUP BY
        o.order_id,
        o.customer_id,
        o.order_date,
        o.discount_pct_applied,
        c.max_discount_pct,
        o.promised_ship_date,
        c.sla_fulfillment_days
),

shipment_value AS (
    SELECT
        s.shipment_id,
        s.order_id,
        s.ship_date,
        s.quantity_shipped,
        COALESCE(SUM(oi.quantity_ordered), 0) AS quantity_ordered,
        COALESCE(SUM(oi.line_total), 0)::NUMERIC(16,2) AS order_value
    FROM core.shipments s
    JOIN core.orders o
      ON o.order_id = s.order_id
    JOIN core.order_items oi
      ON oi.order_id = s.order_id
    GROUP BY
        s.shipment_id,
        s.order_id,
        s.ship_date,
        s.quantity_shipped
),

invoice_payment_summary AS (
    SELECT
        i.invoice_id,
        i.order_id,
        i.invoice_date,
        i.invoice_amount,
        i.expected_amount,
        i.due_date,
        COALESCE(SUM(p.payment_amount), 0)::NUMERIC(16,2) AS total_paid,
        MAX(p.payment_date) AS latest_payment_date,
        COUNT(p.payment_id)::INTEGER AS payment_count
    FROM core.invoices i
    LEFT JOIN core.payments p
      ON p.invoice_id = i.invoice_id
    GROUP BY
        i.invoice_id,
        i.order_id,
        i.invoice_date,
        i.invoice_amount,
        i.expected_amount,
        i.due_date
),

order_payment_summary AS (
    SELECT
        o.order_id,
        o.customer_id,
        COUNT(i.invoice_id)::INTEGER AS invoice_count
    FROM core.orders o
    LEFT JOIN core.invoices i
      ON i.order_id = o.order_id
    GROUP BY o.order_id, o.customer_id
),

base_detections AS (

    -- 1. UNAUTHORIZED DISCOUNT
    SELECT
        'Unauthorized discount'::TEXT AS exception_type,
        'core.orders'::TEXT AS source_table,
        ov.order_id::TEXT AS source_record_id,
        ov.customer_id,
        ov.order_date AS detected_date,
        'High'::TEXT AS severity,
        1.00::NUMERIC(5,2) AS confidence,
        ROUND(
            ov.order_value *
            GREATEST(ov.discount_pct_applied - ov.max_discount_pct, 0) / 100.0,
            2
        ) AS gross_exposure,
        ROUND(
            ov.order_value *
            GREATEST(ov.discount_pct_applied - ov.max_discount_pct, 0) / 100.0,
            2
        ) AS estimated_recoverable,
        CONCAT(
            'Applied discount ', ov.discount_pct_applied,
            '% exceeds contract maximum ', ov.max_discount_pct, '%.'
        ) AS evidence_summary
    FROM order_value ov
    WHERE ov.discount_pct_applied > ov.max_discount_pct

    UNION ALL

    -- 2. PRICE MISMATCH
    SELECT
        'Price mismatch',
        'core.invoices',
        ips.invoice_id,
        o.customer_id,
        ips.invoice_date,
        'Critical',
        1.00,
        ROUND(GREATEST(ips.invoice_amount - ips.expected_amount, 0), 2),
        ROUND(GREATEST(ips.invoice_amount - ips.expected_amount, 0), 2),
        CONCAT(
            'Invoice amount $', ROUND(ips.invoice_amount,2),
            ' exceeds expected amount $', ROUND(ips.expected_amount,2), '.'
        )
    FROM invoice_payment_summary ips
    JOIN core.orders o
      ON o.order_id = ips.order_id
    WHERE ips.invoice_amount > ips.expected_amount

    UNION ALL

    -- 3. LATE FULFILLMENT
    SELECT
        'Late fulfillment',
        'core.shipments',
        s.shipment_id,
        o.customer_id,
        s.ship_date,
        'High',
        1.00,
        ROUND(GREATEST(
            (s.ship_date - o.promised_ship_date) * 0.00,
            0
        ), 2),
        0.00,
        CONCAT(
            'Shipment date ', s.ship_date,
            ' is ', (s.ship_date - o.promised_ship_date),
            ' day(s) after promised ship date ', o.promised_ship_date, '.'
        )
    FROM core.shipments s
    JOIN core.orders o
      ON o.order_id = s.order_id
    WHERE s.ship_date > o.promised_ship_date

    UNION ALL

    -- 4. PARTIAL SHIPMENT
    SELECT
        'Partial shipment',
        'core.shipments',
        sv.shipment_id,
        o.customer_id,
        sv.ship_date,
        'Medium',
        1.00,
        ROUND(
            GREATEST(
                sv.order_value *
                (sv.quantity_ordered - sv.quantity_shipped)
                / NULLIF(sv.quantity_ordered, 0),
                0
            ),
            2
        ),
        ROUND(
            GREATEST(
                sv.order_value *
                (sv.quantity_ordered - sv.quantity_shipped)
                / NULLIF(sv.quantity_ordered, 0),
                0
            ),
            2
        ),
        CONCAT(
            'Shipped ', sv.quantity_shipped,
            ' of ', sv.quantity_ordered, ' ordered units.'
        )
    FROM shipment_value sv
    JOIN core.orders o
      ON o.order_id = sv.order_id
    WHERE sv.quantity_shipped < sv.quantity_ordered

    UNION ALL

    -- 5. UNDERBILLING
    SELECT
        'Underbilling',
        'core.invoices',
        ips.invoice_id,
        o.customer_id,
        ips.invoice_date,
        'Critical',
        1.00,
        ROUND(GREATEST(ips.expected_amount - ips.invoice_amount, 0), 2),
        ROUND(GREATEST(ips.expected_amount - ips.invoice_amount, 0), 2),
        CONCAT(
            'Invoice amount $', ROUND(ips.invoice_amount,2),
            ' is below expected amount $', ROUND(ips.expected_amount,2), '.'
        )
    FROM invoice_payment_summary ips
    JOIN core.orders o
      ON o.order_id = ips.order_id
    WHERE ips.invoice_amount < ips.expected_amount

    UNION ALL

    -- 6. MISSING INVOICE
    SELECT
        'Missing invoice',
        'core.orders',
        o.order_id,
        o.customer_id,
        (s.ship_date + INTERVAL '7 days')::DATE,
        'Critical',
        1.00,
        ROUND(COALESCE(SUM(oi.line_total),0), 2),
        ROUND(COALESCE(SUM(oi.line_total),0), 2),
        CONCAT(
            'Order was fulfilled on ', s.ship_date,
            ' and has no invoice after the 7-day invoicing window.'
        )
    FROM core.orders o
    JOIN core.shipments s
      ON s.order_id = o.order_id
    LEFT JOIN core.invoices i
      ON i.order_id = o.order_id
    LEFT JOIN core.order_items oi
      ON oi.order_id = o.order_id
    WHERE i.invoice_id IS NULL
      AND s.ship_date <= DATE '2026-08-31' - INTERVAL '7 days'
    GROUP BY o.order_id, o.customer_id, s.ship_date

    UNION ALL

    -- 7. DUPLICATE INVOICE
    SELECT
        'Duplicate invoice',
        'core.orders',
        o.order_id,
        o.customer_id,
        MAX(i.invoice_date),
        'High',
        1.00,
        ROUND(GREATEST(SUM(i.invoice_amount) - MAX(i.expected_amount), 0), 2),
        ROUND(GREATEST(SUM(i.invoice_amount) - MAX(i.expected_amount), 0), 2),
        CONCAT(
            COUNT(i.invoice_id), ' invoices exist for order ',
            o.order_id, '.'
        )
    FROM core.orders o
    JOIN core.invoices i
      ON i.order_id = o.order_id
    GROUP BY o.order_id, o.customer_id
    HAVING COUNT(i.invoice_id) > 1

    UNION ALL

    -- 8. PARTIAL PAYMENT
    SELECT
        'Partial payment',
        'core.invoices',
        ips.invoice_id,
        o.customer_id,
        COALESCE(ips.latest_payment_date, ips.invoice_date),
        'Medium',
        1.00,
        ROUND(GREATEST(ips.invoice_amount - ips.total_paid, 0), 2),
        ROUND(GREATEST(ips.invoice_amount - ips.total_paid, 0), 2),
        CONCAT(
            'Paid $', ROUND(ips.total_paid,2),
            ' of $', ROUND(ips.invoice_amount,2),
            ' and payment is not overdue.'
        )
    FROM invoice_payment_summary ips
    JOIN core.orders o
      ON o.order_id = ips.order_id
    WHERE ips.total_paid > 0
      AND ips.total_paid < ips.invoice_amount
      AND COALESCE(ips.latest_payment_date, ips.invoice_date) <= ips.due_date

    UNION ALL

    -- 9. OVERDUE PAYMENT
    SELECT
        'Overdue payment',
        'core.invoices',
        ips.invoice_id,
        o.customer_id,
        COALESCE(ips.latest_payment_date, ips.due_date),
        'High',
        1.00,
        ROUND(
            CASE
                WHEN ips.total_paid < ips.invoice_amount
                THEN ips.invoice_amount - ips.total_paid
                ELSE ips.invoice_amount
            END,
            2
        ),
        ROUND(
            CASE
                WHEN ips.total_paid < ips.invoice_amount
                THEN ips.invoice_amount - ips.total_paid
                ELSE 0
            END,
            2
        ),
        CONCAT(
            CASE
                WHEN ips.total_paid >= ips.invoice_amount
                    THEN 'Payment was made after due date.'
                ELSE 'Invoice remains unpaid/partially paid after due date.'
            END,
            ' Due ', ips.due_date,
            '; latest payment ', COALESCE(ips.latest_payment_date::TEXT, 'none'), '.'
        )
    FROM invoice_payment_summary ips
    JOIN core.orders o
      ON o.order_id = ips.order_id
    WHERE COALESCE(ips.latest_payment_date, DATE '2026-09-12') > ips.due_date

    UNION ALL

    -- 10. DUPLICATE PAYMENT
    SELECT
        'Duplicate payment',
        'core.invoices',
        ips.invoice_id,
        o.customer_id,
        ips.latest_payment_date,
        'High',
        1.00,
        ROUND(GREATEST(ips.total_paid - ips.invoice_amount, 0), 2),
        ROUND(GREATEST(ips.total_paid - ips.invoice_amount, 0), 2),
        CONCAT(
            ips.payment_count, ' payments exist for invoice ',
            ips.invoice_id,
            '; total paid $', ROUND(ips.total_paid,2),
            ' vs invoice $', ROUND(ips.invoice_amount,2), '.'
        )
    FROM invoice_payment_summary ips
    JOIN core.orders o
      ON o.order_id = ips.order_id
    WHERE ips.payment_count > 1
),

with_recurrence AS (
    SELECT
        bd.*,
        COUNT(*) OVER (
            PARTITION BY bd.customer_id, bd.exception_type
            ORDER BY bd.detected_date
            RANGE BETWEEN INTERVAL '30 days' PRECEDING AND CURRENT ROW
        )::INTEGER AS recurrence_count_30d
    FROM base_detections bd
)

INSERT INTO analytics.detected_exceptions (
    exception_type,
    source_table,
    source_record_id,
    customer_id,
    detected_date,
    severity,
    confidence,
    gross_exposure,
    estimated_recoverable,
    recurrence_count_30d,
    evidence_summary
)
SELECT
    exception_type,
    source_table,
    source_record_id,
    customer_id,
    detected_date,
    severity,
    confidence,
    gross_exposure,
    estimated_recoverable,
    recurrence_count_30d,
    evidence_summary
FROM with_recurrence;


-- ================================================================
-- Detection summary
-- ================================================================

SELECT
    exception_type,
    COUNT(*) AS detected_cases,
    ROUND(SUM(gross_exposure), 2) AS gross_exposure,
    ROUND(SUM(estimated_recoverable), 2) AS estimated_recoverable
FROM analytics.detected_exceptions
GROUP BY exception_type
ORDER BY
    CASE exception_type
        WHEN 'Unauthorized discount' THEN 1
        WHEN 'Price mismatch' THEN 2
        WHEN 'Late fulfillment' THEN 3
        WHEN 'Partial shipment' THEN 4
        WHEN 'Underbilling' THEN 5
        WHEN 'Missing invoice' THEN 6
        WHEN 'Duplicate invoice' THEN 7
        WHEN 'Partial payment' THEN 8
        WHEN 'Overdue payment' THEN 9
        WHEN 'Duplicate payment' THEN 10
        ELSE 99
    END;
