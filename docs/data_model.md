# ExceptionIQ — Data Model

## Layered architecture

```text
Synthetic generators
      ↓
CSV source artifacts
      ↓
raw (source-faithful landing)
      ↓
staging (typed + quality flags)
      ↓
core (trusted relational O2C model)
      ↓
analytics + QA
      ↓
Streamlit operational workflow
```

## Core tables

| Table | Grain | Purpose |
|---|---|---|
| `core.customers` | one row/customer | Customer master |
| `core.contracts` | one row/contract | Discount ceiling, SLA, payment terms |
| `core.products` | one row/SKU | Product master and list price |
| `core.orders` | one row/order | Order header and applied discount |
| `core.order_items` | one row/order line | Quantity and unit-price detail |
| `core.shipments` | one row/shipment | Fulfillment date and quantity |
| `core.invoices` | one row/invoice | Billing and expected amount |
| `core.payments` | one row/payment | Accounts-receivable activity |

## Analytics tables
- `analytics.detected_exceptions`: independently detected business exceptions.
- `analytics.exception_cases`: prioritized operational cases.
- `analytics.exception_evidence`: case-to-source lineage/evidence.
- `analytics.case_contributing_factors`: observed dimensional associations.
- `analytics.contributing_factor_summary`: aggregated pattern summary.
- `analytics.case_outcomes`: deterministic synthetic outcome simulation.
- `analytics.exception_tickets`: lightweight operational handoff.
- `analytics.detection_evaluation_detail` / `_summary`: ground-truth validation.

Every case carries `source_table` and `source_record_id`; evidence rows additionally identify the related field and source record.
