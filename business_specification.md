# ExceptionIQ — Business Specification

## Business context
Meridian Supply Co. is a fictional US B2B industrial/MRO distributor. ExceptionIQ monitors the Order-to-Cash (O2C) chain:

**Customer → Contract → Order → Fulfillment → Invoice → Payment**

The V1 success state is: discounts stay within contract limits, fulfillment meets promised dates and quantities, invoices agree with expected contracted value, and payments arrive according to terms.

## Exception catalogue

| Exception | Rule / business meaning | Severity |
|---|---|---|
| Unauthorized discount | Applied discount exceeds contract ceiling | High |
| Price mismatch | Invoice amount differs from expected contracted amount | Critical |
| Late fulfillment | Shipment occurs after promised date | High |
| Partial shipment | Quantity shipped is below quantity ordered | Medium |
| Underbilling | Invoice is below expected amount | Critical |
| Missing invoice | Fulfilled order has no invoice after the configured grace period | Critical |
| Duplicate invoice | More than one invoice exists for an order | High |
| Partial payment | Payment is below invoice balance without a known dispute | Medium |
| Overdue payment | Payment arrives after contractual due date | High |
| Duplicate payment | More than one payment exists for an invoice | High |

## Design principles
- Deterministic SQL rules are used where the business condition is explicit.
- Gross exposure and estimated recoverable value are kept separate.
- Priority is explainable and combines financial exposure, severity, recurrence, and rule confidence.
- Contributing-factor analysis reports observed association, not causal proof.
- Recommended actions are deterministic playbook lookups, not an AI recommender.
- Outcomes are synthetic simulation data used to demonstrate the closed-loop workflow.
