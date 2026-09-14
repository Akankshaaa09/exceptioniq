# ExceptionIQ — Evaluation

The generator deliberately plants known business exceptions and records them in `raw.ground_truth_exceptions`. The detector does **not** read this answer key. A separate evaluation query normalizes the planted exception labels, matches them to independent detections, and calculates TP, FP, FN, precision, recall, and F1.

This is **implementation validation**, not evidence of real-world generalization. It answers: “Did the SQL detector correctly implement the business rules that were deliberately planted?”

Duplicate invoices and duplicate payments receive explicit bridge logic because the planted record and detector operate at different grains: invoice duplication is detected at order level and duplicate payment at invoice level.
