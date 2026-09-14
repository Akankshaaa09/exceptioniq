-- ExceptionIQ — Detection Evaluation
-- Run AFTER 06_exception_detection.sql.
--
-- Purpose:
-- Compare independently detected business exceptions with planted
-- business-exception ground truth.
--
-- This is implementation validation only: TP / FP / FN / precision /
-- recall / F1. It is NOT a claim of real-world generalization.
--
-- IMPORTANT:
-- Ground truth is NOT used by the detector. It is only used here to
-- evaluate the detector after detection has already happened.

DROP TABLE IF EXISTS analytics.detection_evaluation_detail;
DROP TABLE IF EXISTS analytics.detection_evaluation_summary;


-- ================================================================
-- 1. Build a normalized evaluation detail table
-- ================================================================

CREATE TABLE analytics.detection_evaluation_detail AS

WITH type_bridge AS (
    SELECT 'unauthorized_discount' AS gt_type, 'Unauthorized discount' AS detected_type
    UNION ALL SELECT 'price_mismatch', 'Price mismatch'
    UNION ALL SELECT 'late_fulfillment', 'Late fulfillment'
    UNION ALL SELECT 'partial_shipment', 'Partial shipment'
    UNION ALL SELECT 'underbilling', 'Underbilling'
    UNION ALL SELECT 'missing_invoice', 'Missing invoice'
    UNION ALL SELECT 'duplicate_invoice', 'Duplicate invoice'
    UNION ALL SELECT 'partial_payment', 'Partial payment'
    UNION ALL SELECT 'overdue_payment', 'Overdue payment'
    UNION ALL SELECT 'duplicate_payment', 'Duplicate payment'
),

gt AS (
    SELECT
        tb.detected_type AS exception_type,
        g.source_table,
        g.source_record_id,
        g.planted_condition,
        g.expected_financial_impact
    FROM raw.ground_truth_exceptions g
    JOIN type_bridge tb
      ON tb.gt_type = g.exception_type
    WHERE g.category = 'business_exception'
),

det AS (
    SELECT
        detection_id,
        exception_type,
        source_table,
        source_record_id,
        customer_id,
        detected_date,
        gross_exposure,
        estimated_recoverable
    FROM analytics.detected_exceptions
),

-- For duplicate invoices, the detector is order-level while the
-- ground truth identifies the specific duplicate invoice row.
duplicate_invoice_gt AS (
    SELECT
        g.exception_type,
        g.source_record_id AS ground_truth_record_id,
        i.order_id
    FROM gt g
    JOIN raw.invoices i
      ON i.invoice_id = g.source_record_id
    WHERE g.exception_type = 'Duplicate invoice'
),

-- For duplicate payments, the detector is invoice-level while the
-- ground truth identifies the specific duplicate payment row.
duplicate_payment_gt AS (
    SELECT
        g.exception_type,
        g.source_record_id AS ground_truth_record_id,
        p.invoice_id
    FROM gt g
    JOIN raw.payments p
      ON p.payment_id = g.source_record_id
    WHERE g.exception_type = 'Duplicate payment'
),

normalized_detections AS (
    SELECT
        d.detection_id,
        d.exception_type,
        d.source_record_id,
        d.customer_id,
        d.detected_date,
        d.gross_exposure,
        d.estimated_recoverable
    FROM det d
),

matched_gt AS (
    -- Ordinary exceptions: direct record-level matching.
    SELECT
        g.exception_type,
        g.source_record_id AS ground_truth_record_id,
        d.detection_id,
        d.source_record_id AS detected_record_id,
        CASE WHEN d.detection_id IS NULL THEN 'FN' ELSE 'TP' END AS result,
        g.planted_condition,
        g.expected_financial_impact,
        d.gross_exposure,
        d.estimated_recoverable
    FROM gt g
    LEFT JOIN normalized_detections d
      ON d.exception_type = g.exception_type
     AND d.source_record_id = g.source_record_id
    WHERE g.exception_type NOT IN ('Duplicate invoice', 'Duplicate payment')

    UNION ALL

    -- Duplicate invoice: match detector order_id to the order associated
    -- with the ground-truth duplicate invoice.
    SELECT
        g.exception_type,
        g.ground_truth_record_id,
        d.detection_id,
        d.source_record_id AS detected_record_id,
        CASE WHEN d.detection_id IS NULL THEN 'FN' ELSE 'TP' END AS result,
        gt2.planted_condition,
        gt2.expected_financial_impact,
        d.gross_exposure,
        d.estimated_recoverable
    FROM duplicate_invoice_gt g
    JOIN gt gt2
      ON gt2.exception_type = g.exception_type
     AND gt2.source_record_id = g.ground_truth_record_id
    LEFT JOIN normalized_detections d
      ON d.exception_type = 'Duplicate invoice'
     AND d.source_record_id = g.order_id

    UNION ALL

    -- Duplicate payment: match detector invoice_id to the invoice
    -- associated with the ground-truth duplicate payment.
    SELECT
        g.exception_type,
        g.ground_truth_record_id,
        d.detection_id,
        d.source_record_id AS detected_record_id,
        CASE WHEN d.detection_id IS NULL THEN 'FN' ELSE 'TP' END AS result,
        gt2.planted_condition,
        gt2.expected_financial_impact,
        d.gross_exposure,
        d.estimated_recoverable
    FROM duplicate_payment_gt g
    JOIN gt gt2
      ON gt2.exception_type = g.exception_type
     AND gt2.source_record_id = g.ground_truth_record_id
    LEFT JOIN normalized_detections d
      ON d.exception_type = 'Duplicate payment'
     AND d.source_record_id = g.invoice_id
),

false_positives AS (
    -- A detection that has no corresponding ground-truth case.
    SELECT
        d.exception_type,
        NULL::TEXT AS ground_truth_record_id,
        d.detection_id,
        d.source_record_id AS detected_record_id,
        'FP' AS result,
        NULL::TEXT AS planted_condition,
        NULL::TEXT AS expected_financial_impact,
        d.gross_exposure,
        d.estimated_recoverable
    FROM normalized_detections d
    WHERE NOT EXISTS (
        SELECT 1
        FROM matched_gt m
        WHERE m.detection_id = d.detection_id
    )
)

SELECT * FROM matched_gt
UNION ALL
SELECT * FROM false_positives;


-- ================================================================
-- 2. Summary metrics
-- ================================================================

CREATE TABLE analytics.detection_evaluation_summary AS
WITH types AS (
    SELECT DISTINCT exception_type
    FROM analytics.detection_evaluation_detail
),

counts AS (
    SELECT
        exception_type,
        COUNT(*) FILTER (WHERE result = 'TP') AS true_positives,
        COUNT(*) FILTER (WHERE result = 'FP') AS false_positives,
        COUNT(*) FILTER (WHERE result = 'FN') AS false_negatives
    FROM analytics.detection_evaluation_detail
    GROUP BY exception_type
)

SELECT
    t.exception_type,

    COALESCE(c.true_positives, 0) AS true_positives,
    COALESCE(c.false_positives, 0) AS false_positives,
    COALESCE(c.false_negatives, 0) AS false_negatives,

    COALESCE(c.true_positives, 0)
        + COALESCE(c.false_negatives, 0) AS ground_truth_cases,

    COALESCE(c.true_positives, 0)
        + COALESCE(c.false_positives, 0) AS detected_cases,

    ROUND(
        COALESCE(c.true_positives, 0)::NUMERIC
        / NULLIF(
            COALESCE(c.true_positives, 0)
            + COALESCE(c.false_positives, 0),
            0
        ),
        4
    ) AS precision,

    ROUND(
        COALESCE(c.true_positives, 0)::NUMERIC
        / NULLIF(
            COALESCE(c.true_positives, 0)
            + COALESCE(c.false_negatives, 0),
            0
        ),
        4
    ) AS recall,

    ROUND(
        2.0 * COALESCE(c.true_positives, 0)::NUMERIC
        / NULLIF(
            2.0 * COALESCE(c.true_positives, 0)
            + COALESCE(c.false_positives, 0)
            + COALESCE(c.false_negatives, 0),
            0
        ),
        4
    ) AS f1

FROM types t
LEFT JOIN counts c
  ON c.exception_type = t.exception_type

ORDER BY
    CASE t.exception_type
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


-- ================================================================
-- 3. Output
-- ================================================================

SELECT *
FROM analytics.detection_evaluation_summary;

SELECT
    exception_type,
    ground_truth_record_id,
    detected_record_id,
    planted_condition,
    expected_financial_impact
FROM analytics.detection_evaluation_detail
WHERE result = 'FN'
ORDER BY exception_type, ground_truth_record_id;
