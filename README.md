# ExceptionIQ

### Operational Exception Intelligence & Value Recovery

ExceptionIQ is a PostgreSQL-backed operational intelligence prototype for B2B Order-to-Cash (O2C). It detects financial and operational exceptions, traces them to source evidence, estimates recoverable exposure, prioritizes cases, recommends a deterministic action, and tracks the case through resolution and recovery.

**Live demo:** `https://exceptioniqv1.streamlit.app`

---

## Why this exists

A normal dashboard can tell an operations or finance team that something is wrong. ExceptionIQ is designed around the next question:

> **What should I investigate, why is it happening, what is it worth, and what should happen next?**

The workflow is:

**Detect → Investigate → Assign → Resolve → Measure**

---

## What it detects

1. Unauthorized discount
2. Price mismatch
3. Late fulfillment
4. Partial shipment
5. Underbilling
6. Missing invoice
7. Duplicate invoice
8. Partial payment
9. Overdue payment
10. Duplicate payment

The rules are intentionally deterministic and explainable. This V1 does not pretend that a black-box ML model is necessary where the business condition itself is explicit.

---

## Architecture

```text
Synthetic generators
        ↓
CSV source artifacts
        ↓
PostgreSQL: raw
        ↓
PostgreSQL: staging
        ↓
PostgreSQL: core
        ↓
PostgreSQL: analytics + QA
        ↓
Streamlit operational application
```

### PostgreSQL layers

- **raw** — source-faithful landing zone; fields are permissive text so malformed records can be loaded.
- **staging** — typed/normalized records plus data-quality flags.
- **core** — trusted relational O2C model with keys, foreign keys, and business constraints.
- **analytics** — detections, recurrence, priority, cases, evidence, contributing factors, outcomes, and ticket handoff.
- **qa** — evaluation support around deliberately planted exceptions.

### Product workflow

| Workspace | Purpose |
|---|---|
| Action Center | Find what needs attention |
| Investigation | Understand evidence, impact, recurrence and recommended action |
| Resolution | Record action, status, recovery and reason |
| Outcomes | Measure recovery and unresolved exposure |

---

## Data engineering and reproducibility

The repository now contains the actual build logic behind the deployed database rather than only the presentation layer.

### Synthetic data generation

The generator chain creates a clean O2C baseline and then deliberately injects known exceptions and controlled source-quality issues. Fixed seeds make the business-data generation reproducible; runtime timestamps are naturally generated at execution time.

### Validation design

`ground_truth_exceptions` acts as an answer key **only after detection has run**. The detector never uses ground truth to produce cases. `sql/07_detection_evaluation.sql` calculates TP/FP/FN and precision/recall/F1 against the independently generated detections.

This is implementation validation, **not** a claim of production accuracy or real-world generalization.

### Evidence / lineage

Each case carries its originating source table and record ID. `analytics.exception_evidence` provides a case-to-record drill-down with field-level expected/actual values, deltas, and evidence descriptions. This lets a user move from a dollar amount back toward the source record that produced it.

### Contributing factors

The analysis layer looks for observed concentrations across dimensions such as customer segment, fulfillment center, and payment terms. These are explicitly presented as associations rather than causal root-cause findings.

### Outcomes

The outcome layer is deterministic synthetic simulation. It exists to demonstrate the closed loop from case status to actual recovered value and outcome KPIs; it is not a claim about real business performance.

---

## Repository structure

```text
exceptioniq/
├── app.py
├── requirements.txt
├── README.md
├── .env.example
├── .gitignore
│
├── scripts/
│   ├── generate_customers.py
│   ├── generate_products.py
│   ├── generate_contracts.py
│   ├── generate_orders.py
│   ├── generate_shipments.py
│   ├── generate_invoices.py
│   ├── generate_payments.py
│   ├── inject_exceptions.py
│   ├── inject_data_quality_issues.py
│   └── load_raw_postgres.py
│
├── sql/
│   ├── 01_create_schemas.sql
│   ├── 02_create_raw_tables.sql
│   ├── 04_create_staging.sql
│   ├── 05_create_core.sql
│   ├── 06_exception_detection.sql
│   ├── 07_detection_evaluation.sql
│   ├── 08_build_exception_cases.sql
│   ├── 09_contributing_factors.sql
│   └── 10_case_outcomes.sql
│
├── docs/
│   ├── business_specification.md
│   ├── data_model.md
│   ├── evaluation.md
│   └── reproducibility.md
│
└── data/
    └── README.md
```

Generated CSVs are intentionally ignored by Git. The repository contains their generators and the database build logic.

---

## Local setup

### 1. Install dependencies

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
```

### 2. Set a PostgreSQL connection

For example:

```bash
# PowerShell
$env:DATABASE_URL="postgresql://USER:PASSWORD@HOST:5432/DATABASE"
```

Keep real credentials out of Git.

### 3. Generate the source data

```bash
python scripts/generate_customers.py
python scripts/generate_products.py
python scripts/generate_contracts.py
python scripts/generate_orders.py
python scripts/generate_shipments.py
python scripts/generate_invoices.py
python scripts/generate_payments.py
python scripts/inject_exceptions.py
python scripts/inject_data_quality_issues.py
```

### 4. Build the database

Run the SQL files in numeric order after the raw CSVs have been generated. See `docs/reproducibility.md` for the complete command sequence.

### 5. Run the app

```bash
streamlit run app.py
```

The application supports local PostgreSQL environment variables and a hosted `DATABASE_URL` secret.

---

## Deployment

The deployed version separates the application from the database:

```text
GitHub → Streamlit Community Cloud → Neon PostgreSQL
```

The application receives the hosted connection string through `DATABASE_URL`; credentials are not stored in source control.

---

## Engineering decisions

- **PostgreSQL over a document store:** the O2C model has clear relationships and reconciliation joins.
- **SQL rules over ML for V1:** the exception conditions are explicit business invariants; deterministic rules are easier to audit and evaluate.
- **Synthetic ground truth:** controlled injection makes implementation-level detection validation possible without pretending the data is real.
- **Evidence as a first-class table:** a business user should be able to ask where a financial number came from.
- **Recoverable exposure separate from gross exposure:** value at risk is not always equal to realistically recoverable value.
- **Streamlit for V1:** the goal was to validate the operational workflow quickly; a productionized version could separate frontend/API layers if concurrency, security, or performance requirements justified it.

---

## Limitations / V2 considerations

This is a **production-style prototype**, not an enterprise production system. It does not implement authentication/RBAC, enterprise audit logging, CI/CD infrastructure, real ERP/CRM integrations, real-time event streaming, or a production ML lifecycle.

The next engineering step would be to profile hosted latency and query behavior before changing the architecture.
