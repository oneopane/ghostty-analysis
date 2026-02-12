# Attention Routing Task Index

> Note: Every task must beat at least one non-ML baseline before promotion.

| Task | Name | Stage | Prediction type | Primary metric | Label availability |
|---|---|---|---|---|---|
| 01 | Out-of-scope / wrong-repo detection | D0 | Classification | PR-AUC + Recall@high-precision | Risky |
| 02 | Ready-for-review vs needs-author-work | D0 | Classification | F1 (ready class) + Balanced accuracy | Needs definition |
| 03 | Oversized PR detection | D0 | Classification | Precision@policy-threshold | Known |
| 04 | Ownership coverage confidence | D1 | Classification (calibrated) | Brier score + PR-AUC | Risky |
| 05 | Boundary/module multi-label classification | D1 | Multi-label classification | Micro-F1 + Jaccard | Known |
| 06 | First-responder routing (team/user ranking) | D2 | Ranking | MRR + Hit@1/3/5 | Known |
| 07 | Owner-compliant constrained routing | D2 | Ranking | MRR (owner-constrained) + Owner-hit@k | Known |
| 08 | Candidate non-response / availability prediction | D2/D3 | Classification (candidate-level) | PR-AUC + Calibration (ECE/Brier) | Needs definition |
| 09 | Stall risk escalation trigger | D3 | Survival / classification | C-index + PR-AUC@SLA | Known |
| 10 | Reviewer set sizing (minimal k to hit SLA) | D3 | Classification (set success) | SLA-success@k calibration + Ping-efficiency | Risky |
