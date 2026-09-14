-- ExceptionIQ — Case Outcomes & Recovery Layer
-- Run AFTER 08_build_exception_cases.sql.
--
-- This simulates operational case outcomes for the synthetic environment.
-- These are NOT real business outcomes. They exist so the prototype can
-- demonstrate the full closed-loop workflow:
--
--   Open -> Investigating -> Resolved/Dismissed
--                     -> Recovery -> Outcome KPIs
--
-- Outcome assignment is deterministic from case_id so reruns are reproducible.

DROP TABLE IF EXISTS analytics.case_outcomes;


-- ================================================================
-- 1. Generate synthetic case outcomes
-- ================================================================

CREATE TABLE analytics.case_outcomes AS
WITH base AS (
    SELECT
        c.*,

        -- Deterministic pseudo-random value in [0, 1).
        (
            ('x' || SUBSTRING(MD5(c.case_id::TEXT), 1, 8))::BIT(32)::BIGINT
            / 4294967296.0
        ) AS r1,

        (
            ('x' || SUBSTRING(MD5((c.case_id::TEXT || '-time')), 1, 8))::BIT(32)::BIGINT
            / 4294967296.0
        ) AS r2

    FROM analytics.exception_cases c
),

assigned AS (
    SELECT
        b.*,

        CASE
            WHEN b.r1 < 0.68 THEN 'Resolved'
            WHEN b.r1 < 0.78 THEN 'Dismissed'
            WHEN b.r1 < 0.90 THEN 'Investigating'
            ELSE 'Open'
        END AS simulated_status

    FROM base b
),

outcomes AS (
    SELECT
        a.*,

        CASE
            WHEN a.simulated_status = 'Resolved' THEN
                CASE a.exception_type
                    WHEN 'Unauthorized discount'
                        THEN ROUND(a.estimated_recoverable * (0.65 + a.r2 * 0.30), 2)
                    WHEN 'Price mismatch'
                        THEN ROUND(a.estimated_recoverable * (0.75 + a.r2 * 0.20), 2)
                    WHEN 'Late fulfillment'
                        THEN 0
                    WHEN 'Partial shipment'
                        THEN ROUND(a.estimated_recoverable * (0.45 + a.r2 * 0.40), 2)
                    WHEN 'Underbilling'
                        THEN ROUND(a.estimated_recoverable * (0.70 + a.r2 * 0.25), 2)
                    WHEN 'Missing invoice'
                        THEN ROUND(a.estimated_recoverable * (0.85 + a.r2 * 0.15), 2)
                    WHEN 'Duplicate invoice'
                        THEN ROUND(a.estimated_recoverable * (0.85 + a.r2 * 0.15), 2)
                    WHEN 'Partial payment'
                        THEN ROUND(a.estimated_recoverable * (0.50 + a.r2 * 0.40), 2)
                    WHEN 'Overdue payment'
                        THEN ROUND(a.estimated_recoverable * (0.45 + a.r2 * 0.45), 2)
                    WHEN 'Duplicate payment'
                        THEN ROUND(a.estimated_recoverable * (0.90 + a.r2 * 0.10), 2)
                    ELSE 0
                END
            ELSE 0
        END AS simulated_recovered,

        CASE
            WHEN a.simulated_status IN ('Resolved', 'Dismissed') THEN
                GREATEST(
                    1,
                    ROUND(2 + a.r2 * 28)::INTEGER
                )
            ELSE NULL
        END AS resolution_days

    FROM assigned a
)

SELECT
    case_id,
    exception_type,
    simulated_status AS status,
    simulated_recovered AS actual_recovered,
    resolution_days,

    CASE
        WHEN simulated_status = 'Resolved'
            THEN 'Case reviewed and corrective action completed.'
        WHEN simulated_status = 'Dismissed'
            THEN 'Exception reviewed and dismissed after investigation.'
        WHEN simulated_status = 'Investigating'
            THEN NULL
        ELSE NULL
    END AS resolution_reason,

    CASE
        WHEN simulated_status = 'Resolved'
            THEN recommended_action
        WHEN simulated_status = 'Dismissed'
            THEN 'No corrective action required after review.'
        ELSE NULL
    END AS action_taken

FROM outcomes;


-- ================================================================
-- 2. Push outcomes into the case table
-- ================================================================

UPDATE analytics.exception_cases c
SET
    status = o.status,
    actual_recovered = o.actual_recovered,
    action_taken = o.action_taken,
    resolution_reason = o.resolution_reason,

    resolved_at = CASE
        WHEN o.resolution_days IS NOT NULL
            THEN c.opened_at + (o.resolution_days || ' days')::INTERVAL
        ELSE NULL
    END

FROM analytics.case_outcomes o
WHERE o.case_id = c.case_id;


-- ================================================================
-- 3. Outcome KPI summary
-- ================================================================

SELECT
    COUNT(*) AS total_cases,

    COUNT(*) FILTER (WHERE status = 'Resolved') AS resolved_cases,
    COUNT(*) FILTER (WHERE status = 'Investigating') AS investigating_cases,
    COUNT(*) FILTER (WHERE status = 'Open') AS open_cases,
    COUNT(*) FILTER (WHERE status = 'Dismissed') AS dismissed_cases,

    ROUND(SUM(estimated_recoverable), 2) AS estimated_recoverable,

    ROUND(SUM(actual_recovered), 2) AS actual_recovered,

    ROUND(
        100.0 * SUM(actual_recovered)
        / NULLIF(SUM(estimated_recoverable), 0),
        2
    ) AS recovery_rate_pct,

    ROUND(
        AVG(
            EXTRACT(
                EPOCH FROM (resolved_at - opened_at)
            ) / 86400.0
        ) FILTER (WHERE resolved_at IS NOT NULL),
        2
    ) AS avg_resolution_days

FROM analytics.exception_cases;


-- ================================================================
-- 4. Outcome performance by exception type
-- ================================================================

SELECT
    exception_type,
    COUNT(*) AS cases,
    COUNT(*) FILTER (WHERE status = 'Resolved') AS resolved_cases,
    COUNT(*) FILTER (WHERE status = 'Dismissed') AS dismissed_cases,

    ROUND(SUM(estimated_recoverable), 2) AS estimated_recoverable,
    ROUND(SUM(actual_recovered), 2) AS actual_recovered,

    ROUND(
        100.0 * SUM(actual_recovered)
        / NULLIF(SUM(estimated_recoverable), 0),
        2
    ) AS recovery_rate_pct,

    ROUND(
        AVG(
            EXTRACT(
                EPOCH FROM (resolved_at - opened_at)
            ) / 86400.0
        ) FILTER (WHERE resolved_at IS NOT NULL),
        2
    ) AS avg_resolution_days

FROM analytics.exception_cases
GROUP BY exception_type
ORDER BY actual_recovered DESC;


-- ================================================================
-- 5. Unresolved exposure — future Action Center KPI
-- ================================================================

SELECT
    status,
    COUNT(*) AS cases,
    ROUND(SUM(estimated_recoverable), 2) AS unresolved_estimated_exposure
FROM analytics.exception_cases
WHERE status IN ('Open', 'Investigating')
GROUP BY status
ORDER BY
    CASE status
        WHEN 'Open' THEN 1
        WHEN 'Investigating' THEN 2
    END;
