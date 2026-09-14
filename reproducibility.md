# ExceptionIQ — Reproducibility

## 1. Generate the synthetic source data
From the repository root:

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

The order matters because later generators consume earlier outputs. `inject_exceptions.py` creates the ten business exception classes; `inject_data_quality_issues.py` then adds controlled source-quality problems while keeping those mutations separate conceptually from business exceptions.

## 2. Create PostgreSQL layers

```bash
psql "$DATABASE_URL" -f sql/01_create_schemas.sql
psql "$DATABASE_URL" -f sql/02_create_raw_tables.sql
python scripts/load_raw_postgres.py
psql "$DATABASE_URL" -f sql/04_create_staging.sql
psql "$DATABASE_URL" -f sql/05_create_core.sql
psql "$DATABASE_URL" -f sql/06_exception_detection.sql
psql "$DATABASE_URL" -f sql/07_detection_evaluation.sql
psql "$DATABASE_URL" -f sql/08_build_exception_cases.sql
psql "$DATABASE_URL" -f sql/09_contributing_factors.sql
psql "$DATABASE_URL" -f sql/10_case_outcomes.sql
```

The loader uses PostgreSQL's `COPY` path through Psycopg and deliberately loads raw fields as text. Staging performs typing/quality checks; core enforces relational integrity; analytics builds the business-facing exception workflow.

## 3. Hosted demo
The public demo uses the same application code against a hosted PostgreSQL database. The hosted database is an environment artifact, not a secret committed to this repository. `DATABASE_URL` belongs in the deployment platform's secret store.

## Important note
The synthetic CSV outputs and the hosted database are generated/deployment artifacts. The repository contains the **source logic needed to recreate them**, rather than pretending the hosted database is part of source control.
