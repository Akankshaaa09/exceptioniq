-- ExceptionIQ — Case, Impact, Priority & Action Layer
-- Run AFTER 06_exception_detection.sql.
--
-- Converts independently detected exceptions into analyst-facing cases.
--
-- Workflow:
--   Exception -> Evidence -> Impact -> Priority -> Action -> Outcome
--
-- Priority is intentionally transparent and deterministic:
--   Financial exposure  : 0–50 points
--   Severity             : 0–25 points
--   30-day recurrence    : 0–15 points
--   Detection confidence : 0–10 points
--   Total                : 0–100
--
-- Financial component uses estimated recoverable exposure:
--   0 to $10,000 maps linearly to 0–50 points;
--   exposure above $10,000 caps at 50.
--
-- This is a prioritization heuristic, NOT a predictive model.
-- Recommended actions are deterministic playbook lookups, NOT AI recommendations.

DROP TABLE IF EXISTS analytics.exception_evidence;
DROP TABLE IF EXISTS analytics.exception_cases;


-- ================================================================
-- 1. CASE TABLE
-- ================================================================

CREATE TABLE analytics.exception_cases (
    case_id BIGSERIAL PRIMARY KEY,

    exception_type TEXT NOT NULL,
    source_table TEXT NOT NULL,
    source_record_id TEXT NOT NULL,
    customer_id TEXT,

    detected_date DATE NOT NULL,

    severity TEXT NOT NULL,
    confidence NUMERIC(5,2) NOT NULL,

    gross_exposure NUMERIC(16,2) NOT NULL,
    estimated_recoverable NUMERIC(16,2) NOT NULL,
    actual_recovered NUMERIC(16,2) NOT NULL DEFAULT 0,

    recurrence_count_30d INTEGER NOT NULL DEFAULT 1,

    financial_priority_points NUMERIC(6,2) NOT NULL,
    severity_priority_points NUMERIC(6,2) NOT NULL,
    recurrence_priority_points NUMERIC(6,2) NOT NULL,
    confidence_priority_points NUMERIC(6,2) NOT NULL,

    priority_score NUMERIC(6,2) NOT NULL,

    priority_band TEXT NOT NULL,

    recommended_action TEXT NOT NULL,

    status TEXT NOT NULL DEFAULT 'Open',
    owner TEXT,

    action_taken TEXT,
    resolution_reason TEXT,

    opened_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP,

    CONSTRAINT exception_cases_severity_chk
        CHECK (severity IN ('Critical', 'High', 'Medium', 'Low')),

    CONSTRAINT exception_cases_confidence_chk
        CHECK (confidence >= 0 AND confidence <= 1),

    CONSTRAINT exception_cases_exposure_chk
        CHECK (gross_exposure >= 0 AND estimated_recoverable >= 0),

    CONSTRAINT exception_cases_recovered_chk
        CHECK (actual_recovered >= 0),

    CONSTRAINT exception_cases_priority_chk
        CHECK (priority_score >= 0 AND priority_score <= 100),

    CONSTRAINT exception_cases_band_chk
        CHECK (priority_band IN ('P1 - Immediate', 'P2 - High', 'P3 - Routine')),

    CONSTRAINT exception_cases_status_chk
        CHECK (status IN ('Open', 'Investigating', 'Resolved', 'Dismissed'))
);


-- ================================================================
-- 2. BUILD CASES
-- ================================================================

WITH scored AS (
    SELECT
        d.*,

        LEAST(
            50.00,
            ROUND(
                d.estimated_recoverable / 10000.0 * 50.0,
                2
            )
        ) AS financial_points,

        CASE d.severity
            WHEN 'Critical' THEN 25.00
            WHEN 'High' THEN 20.00
            WHEN 'Medium' THEN 12.00
            WHEN 'Low' THEN 5.00
        END AS severity_points,

        LEAST(
            15.00,
            GREATEST((d.recurrence_count_30d - 1) * 3.00, 0)
        ) AS recurrence_points,

        ROUND(
            d.confidence * 10.00,
            2
        ) AS confidence_points,

        CASE d.exception_type
            WHEN 'Unauthorized discount'
                THEN 'Review contract terms and obtain approval or recover the unauthorized discount.'

            WHEN 'Price mismatch'
                THEN 'Reconcile invoice pricing to the contract and issue an invoice correction or credit.'

            WHEN 'Late fulfillment'
                THEN 'Review fulfillment-center delay, confirm customer impact, and escalate SLA breach.'

            WHEN 'Partial shipment'
                THEN 'Check backorder/fulfillment status and coordinate completion of the remaining quantity.'

            WHEN 'Underbilling'
                THEN 'Reconcile billed amount to contracted value and issue a corrective invoice for the shortfall.'

            WHEN 'Missing invoice'
                THEN 'Create or trigger the missing invoice and confirm the receivable is recorded.'

            WHEN 'Duplicate invoice'
                THEN 'Review duplicate billing and void or credit the duplicate invoice.'

            WHEN 'Partial payment'
                THEN 'Review outstanding balance and follow up with the customer or collections.'

            WHEN 'Overdue payment'
                THEN 'Escalate to the account owner or collections and follow up on the overdue balance.'

            WHEN 'Duplicate payment'
                THEN 'Reconcile the duplicate payment and initiate refund or account application review.'

            ELSE 'Investigate exception and determine corrective action.'
        END AS recommended_action

    FROM analytics.detected_exceptions d
),

final_scored AS (
    SELECT
        s.*,
        ROUND(
            s.financial_points
            + s.severity_points
            + s.recurrence_points
            + s.confidence_points,
            2
        ) AS total_priority_score
    FROM scored s
)

INSERT INTO analytics.exception_cases (
    exception_type,
    source_table,
    source_record_id,
    customer_id,
    detected_date,
    severity,
    confidence,
    gross_exposure,
    estimated_recoverable,
    actual_recovered,
    recurrence_count_30d,
    financial_priority_points,
    severity_priority_points,
    recurrence_priority_points,
    confidence_priority_points,
    priority_score,
    priority_band,
    recommended_action
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
    0,
    recurrence_count_30d,
    financial_points,
    severity_points,
    recurrence_points,
    confidence_points,
    total_priority_score,

    CASE
        WHEN total_priority_score >= 75 THEN 'P1 - Immediate'
        WHEN total_priority_score >= 50 THEN 'P2 - High'
        ELSE 'P3 - Routine'
    END,

    recommended_action
FROM final_scored;


-- ================================================================
-- 3. EVIDENCE / LINEAGE TABLE
-- ================================================================

CREATE TABLE analytics.exception_evidence (
    evidence_id BIGSERIAL PRIMARY KEY,
    case_id BIGINT NOT NULL
        REFERENCES analytics.exception_cases(case_id)
        ON DELETE CASCADE,

    related_table TEXT NOT NULL,
    related_record_id TEXT NOT NULL,

    field_name TEXT NOT NULL,
    expected_value TEXT,
    actual_value TEXT,
    delta_value NUMERIC(16,2),

    evidence_description TEXT NOT NULL
);


-- Every case gets a primary source-record evidence row.
INSERT INTO analytics.exception_evidence (
    case_id,
    related_table,
    related_record_id,
    field_name,
    expected_value,
    actual_value,
    delta_value,
    evidence_description
)
SELECT
    c.case_id,
    c.source_table,
    c.source_record_id,

    CASE c.exception_type
        WHEN 'Unauthorized discount' THEN 'discount_pct_applied'
        WHEN 'Price mismatch' THEN 'invoice_amount'
        WHEN 'Late fulfillment' THEN 'ship_date'
        WHEN 'Partial shipment' THEN 'quantity_shipped'
        WHEN 'Underbilling' THEN 'invoice_amount'
        WHEN 'Missing invoice' THEN 'invoice_id'
        WHEN 'Duplicate invoice' THEN 'invoice_count'
        WHEN 'Partial payment' THEN 'payment_amount'
        WHEN 'Overdue payment' THEN 'due_date'
        WHEN 'Duplicate payment' THEN 'payment_count'
        ELSE 'exception'
    END,

    NULL,
    NULL,
    NULL,

    CONCAT(
        'Primary source record for ', c.exception_type,
        '. Detection evidence: ',
        d.evidence_summary
    )

FROM analytics.exception_cases c
JOIN analytics.detected_exceptions d
  ON d.exception_type = c.exception_type
 AND d.source_table = c.source_table
 AND d.source_record_id = c.source_record_id;


-- ================================================================
-- 4. CASE SUMMARY
-- ================================================================

SELECT
    priority_band,
    COUNT(*) AS cases,
    ROUND(SUM(gross_exposure), 2) AS gross_exposure,
    ROUND(SUM(estimated_recoverable), 2) AS estimated_recoverable
FROM analytics.exception_cases
GROUP BY priority_band
ORDER BY
    CASE priority_band
        WHEN 'P1 - Immediate' THEN 1
        WHEN 'P2 - High' THEN 2
        WHEN 'P3 - Routine' THEN 3
    END;


-- Top cases for the future Action Center.
SELECT
    case_id,
    exception_type,
    source_record_id,
    severity,
    ROUND(estimated_recoverable, 2) AS estimated_recoverable,
    recurrence_count_30d,
    priority_score,
    priority_band,
    recommended_action
FROM analytics.exception_cases
ORDER BY priority_score DESC, estimated_recoverable DESC
LIMIT 25;
