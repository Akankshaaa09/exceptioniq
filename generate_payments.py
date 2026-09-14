"""
generate_payments.py

Generates the clean payment baseline for ExceptionIQ.

Source system: Finance/AR
Input:
  data/raw/finance/invoices.csv

Output:
  data/raw/finance/payments.csv

Clean baseline:
  - exactly one payment per invoice
  - payment amount = full invoice amount
  - payment_date is after invoice_date and on/before due_date
  - status = posted

Exception mutations (partial payment, overdue payment, duplicate payment)
are NOT introduced here; they belong in the later exception-injection step.
"""

import os
import random

import numpy as np
import pandas as pd

SEED = 42
random.seed(SEED)
np.random.seed(SEED)

BASE = os.path.join(os.path.dirname(__file__), "..")
INVOICES_PATH = os.path.join(BASE, "data", "raw", "finance", "invoices.csv")
OUT_PATH = os.path.join(BASE, "data", "raw", "finance", "payments.csv")


def load_inputs():
    return pd.read_csv(
        INVOICES_PATH,
        parse_dates=["invoice_date", "due_date"],
    )


def generate_payments(invoices):
    rows = []

    for i, invoice in enumerate(invoices.itertuples(), start=1):
        days_to_pay = random.randint(5, max(5, (invoice.due_date - invoice.invoice_date).days))

        payment_date = invoice.invoice_date + pd.Timedelta(days=days_to_pay)

        # Guardrail: clean baseline must never pay after due date.
        if payment_date > invoice.due_date:
            payment_date = invoice.due_date

        rows.append(
            {
                "payment_id": f"PAY{i:06d}",
                "invoice_id": invoice.invoice_id,
                "payment_date": payment_date,
                "payment_amount": round(float(invoice.invoice_amount), 2),
                "status": "posted",
            }
        )

    return pd.DataFrame(rows)


def validate(invoices, payments):
    if len(payments) != len(invoices):
        raise ValueError(
            f"Expected {len(invoices)} payments, generated {len(payments)}."
        )

    if payments["payment_id"].duplicated().any():
        raise ValueError("Duplicate payment_id values found.")

    if payments["invoice_id"].duplicated().any():
        raise ValueError("More than one clean-baseline payment found for an invoice.")

    check = payments.merge(
        invoices[
            ["invoice_id", "invoice_date", "due_date", "invoice_amount"]
        ],
        on="invoice_id",
        how="left",
    )

    if check["invoice_date"].isna().any():
        raise ValueError("Payment references an unknown invoice.")

    if (check["payment_date"] <= check["invoice_date"]).any():
        raise ValueError("Payment is on/before invoice date.")

    if (check["payment_date"] > check["due_date"]).any():
        raise ValueError("Payment is after due date in clean baseline.")

    if (check["payment_amount"] != check["invoice_amount"]).any():
        raise ValueError("Payment amount does not equal invoice amount.")

    if not (payments["status"] == "posted").all():
        raise ValueError("Unexpected payment status found.")

    print(f"Payment rows: {len(payments)}")
    print(f"Unique invoices paid: {payments['invoice_id'].nunique()}")
    print(f"Status distribution:\n{payments['status'].value_counts()}")
    print(
        "\nPayment amount distribution:\n"
        + str(payments["payment_amount"].describe()[["min", "mean", "50%", "max"]].round(2))
    )
    print("\nValidation: ALL CLEAN-BASELINE CHECKS PASSED.")


if __name__ == "__main__":
    invoices = load_inputs()
    payments = generate_payments(invoices)
    validate(invoices, payments)

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    payments.to_csv(OUT_PATH, index=False)
    print(f"\nGenerated {len(payments)} payments -> {OUT_PATH}")
