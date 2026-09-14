"""
ExceptionIQ - raw CSV -> PostgreSQL loader

Loads the nine ExceptionIQ raw CSV extracts into the `raw` schema.

Run from the ExceptionIQ project root:

    python scripts/load_raw_postgres.py

Requires:
    DATABASE_URL environment variable
    psycopg[binary]
    pandas
"""

from pathlib import Path
from io import StringIO
import os

import pandas as pd
import psycopg


PROJECT_ROOT = Path(__file__).resolve().parents[1]

FILES = {
    "customers": PROJECT_ROOT / "data" / "raw" / "commercial" / "customers.csv",
    "contracts": PROJECT_ROOT / "data" / "raw" / "commercial" / "contracts.csv",
    "products": PROJECT_ROOT / "data" / "raw" / "commercial" / "products.csv",
    "orders": PROJECT_ROOT / "data" / "raw" / "commercial" / "orders.csv",
    "order_items": PROJECT_ROOT / "data" / "raw" / "operations" / "order_items.csv",
    "shipments": PROJECT_ROOT / "data" / "raw" / "operations" / "shipments.csv",
    "invoices": PROJECT_ROOT / "data" / "raw" / "finance" / "invoices.csv",
    "payments": PROJECT_ROOT / "data" / "raw" / "finance" / "payments.csv",
    "ground_truth_exceptions": (
        PROJECT_ROOT / "data" / "ground_truth" / "ground_truth_exceptions.csv"
    ),
}


def require_files():
    missing = [str(path) for path in FILES.values() if not path.exists()]
    if missing:
        raise FileNotFoundError(
            "These expected CSV files were not found:\n" + "\n".join(missing)
        )


def load_table(cur, table_name, csv_path):
    df = pd.read_csv(
        csv_path,
        dtype=str,
        keep_default_na=False,
    )

    # The raw schema is intentionally TEXT-only.
    # We preserve malformed/blank values here so staging can validate them.
    df = df.astype(str)

    # table_name is ONLY the bare table name from FILES above.
    # The schema is explicitly fixed to `raw` here.
    cur.execute(f'TRUNCATE TABLE raw."{table_name}"')

    buffer = StringIO()
    df.to_csv(buffer, index=False, header=False, lineterminator="\n")
    buffer.seek(0)

    with cur.copy(f'COPY raw."{table_name}" FROM STDIN WITH (FORMAT CSV)') as copy:
        copy.write(buffer.getvalue())

    return len(df)


def main():
    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        raise RuntimeError(
            "DATABASE_URL is not set.\n"
            "In PowerShell, run:\n"
            '$env:DATABASE_URL="postgresql://postgres:YOUR_PASSWORD@localhost:5432/exceptioniq"'
        )

    require_files()

    print("Connecting to PostgreSQL...")
    print("Database: exceptioniq")
    print("Target schema: raw\n")

    total_rows = 0

    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            for table_name, csv_path in FILES.items():
                rows = load_table(cur, table_name, csv_path)
                total_rows += rows
                print(f"{table_name:24s} {rows:6,d} rows loaded")

        conn.commit()

    print(f"\nSUCCESS - loaded {total_rows:,} raw rows into PostgreSQL.")


if __name__ == "__main__":
    main()
