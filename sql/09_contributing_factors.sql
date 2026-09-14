-- ExceptionIQ — Contributing-Factor Analysis
-- Run after 08_build_exception_cases.sql.
-- These are observable associations, not causal root-cause claims.

DROP TABLE IF EXISTS analytics.contributing_factor_summary;
DROP TABLE IF EXISTS analytics.case_contributing_factors;

CREATE TABLE analytics.case_contributing_factors AS
SELECT c.case_id,c.exception_type,'Fulfillment center' factor_dimension,s.fulfillment_center factor_value,
'Observed concentration by fulfillment center; association, not causation.' interpretation
FROM analytics.exception_cases c JOIN core.shipments s ON c.exception_type='Late fulfillment' AND c.source_record_id=s.shipment_id
UNION ALL
SELECT c.case_id,c.exception_type,'Customer segment',cu.segment,
'Observed concentration by customer segment; association, not causation.'
FROM analytics.exception_cases c JOIN core.orders o ON c.exception_type='Unauthorized discount' AND c.source_record_id=o.order_id JOIN core.customers cu ON cu.customer_id=o.customer_id
UNION ALL
SELECT c.case_id,c.exception_type,'Customer segment',cu.segment,
'Observed concentration by customer segment; association, not causation.'
FROM analytics.exception_cases c JOIN core.invoices i ON c.exception_type='Price mismatch' AND c.source_record_id=i.invoice_id JOIN core.orders o ON o.order_id=i.order_id JOIN core.customers cu ON cu.customer_id=o.customer_id
UNION ALL
SELECT c.case_id,c.exception_type,'Payment terms',CONCAT('Net ',ct.payment_terms_days),
'Observed concentration by contractual payment terms; association, not causation.'
FROM analytics.exception_cases c JOIN core.payments p ON c.exception_type='Overdue payment' AND c.source_record_id=p.payment_id JOIN core.invoices i ON i.invoice_id=p.invoice_id JOIN core.orders o ON o.order_id=i.order_id JOIN core.contracts ct ON ct.contract_id=o.contract_id
UNION ALL
SELECT c.case_id,c.exception_type,'Payment terms',CONCAT('Net ',ct.payment_terms_days),
'Observed concentration by contractual payment terms; association, not causation.'
FROM analytics.exception_cases c JOIN core.invoices i ON c.exception_type='Partial payment' AND c.source_record_id=i.invoice_id JOIN core.orders o ON o.order_id=i.order_id JOIN core.contracts ct ON ct.contract_id=o.contract_id
UNION ALL
SELECT c.case_id,c.exception_type,'Fulfillment center',s.fulfillment_center,
'Observed concentration by fulfillment center; association, not causation.'
FROM analytics.exception_cases c JOIN core.shipments s ON c.exception_type='Partial shipment' AND c.source_record_id=s.shipment_id
UNION ALL
SELECT c.case_id,c.exception_type,'Customer segment',cu.segment,
'Observed concentration by customer segment; association, not causation.'
FROM analytics.exception_cases c JOIN core.invoices i ON c.exception_type='Underbilling' AND c.source_record_id=i.invoice_id JOIN core.orders o ON o.order_id=i.order_id JOIN core.customers cu ON cu.customer_id=o.customer_id
UNION ALL
SELECT c.case_id,c.exception_type,'Customer segment',cu.segment,
'Observed concentration by customer segment; association, not causation.'
FROM analytics.exception_cases c JOIN core.orders o ON c.exception_type='Missing invoice' AND c.source_record_id=o.order_id JOIN core.customers cu ON cu.customer_id=o.customer_id
UNION ALL
SELECT c.case_id,c.exception_type,'Customer segment',cu.segment,
'Observed concentration by customer segment; association, not causation.'
FROM analytics.exception_cases c JOIN core.orders o ON c.exception_type='Duplicate invoice' AND c.source_record_id=o.order_id JOIN core.customers cu ON cu.customer_id=o.customer_id
UNION ALL
SELECT c.case_id,c.exception_type,'Customer segment',cu.segment,
'Observed concentration by customer segment; association, not causation.'
FROM analytics.exception_cases c JOIN core.invoices i ON c.exception_type='Duplicate payment' AND c.source_record_id=i.invoice_id JOIN core.orders o ON o.order_id=i.order_id JOIN core.customers cu ON cu.customer_id=o.customer_id;

CREATE TABLE analytics.contributing_factor_summary AS
WITH b AS (
 SELECT cf.exception_type,cf.factor_dimension,cf.factor_value,
 COUNT(DISTINCT cf.case_id) cases,ROUND(SUM(ec.estimated_recoverable),2) estimated_recoverable
 FROM analytics.case_contributing_factors cf JOIN analytics.exception_cases ec ON ec.case_id=cf.case_id
 GROUP BY cf.exception_type,cf.factor_dimension,cf.factor_value
), t AS (
 SELECT cf.exception_type,COUNT(DISTINCT cf.case_id) total_cases,ROUND(SUM(ec.estimated_recoverable),2) total_recoverable
 FROM analytics.case_contributing_factors cf JOIN analytics.exception_cases ec ON ec.case_id=cf.case_id
 GROUP BY cf.exception_type
)
SELECT b.*,t.total_cases,t.total_recoverable,
ROUND(100.0*b.cases/NULLIF(t.total_cases,0),2) case_share_pct,
ROUND(100.0*b.estimated_recoverable/NULLIF(t.total_recoverable,0),2) exposure_share_pct
FROM b JOIN t USING(exception_type);

SELECT exception_type,factor_dimension,factor_value,cases,estimated_recoverable,case_share_pct,exposure_share_pct
FROM analytics.contributing_factor_summary
ORDER BY exception_type,case_share_pct DESC,estimated_recoverable DESC;

SELECT DISTINCT ON (exception_type) exception_type,factor_dimension,factor_value,cases,estimated_recoverable,case_share_pct,exposure_share_pct
FROM analytics.contributing_factor_summary
ORDER BY exception_type,case_share_pct DESC,estimated_recoverable DESC;
