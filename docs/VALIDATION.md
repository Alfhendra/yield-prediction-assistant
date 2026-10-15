# Validation record

Local validation on 2026-10-15: all 20 tests passed. The sample generator executed the public CLI to produce eight outputs from 192 synthetic monthly observations. The example forecast targets October 2026 using history available through September 2026.

```sh
python -m unittest discover -s tests -v
python scripts/generate_fixture.py
python scripts/generate_samples.py
```

| Area | Verified behavior |
|---|---|
| Numerical methods | Known linear-system solution, constant features, exact MAE/WAPE examples |
| Features | Previous-month source IDs and predictors; month rollover |
| Time separation | 164 training examples through March; 24 holdout predictions for April–September |
| Leakage | Altering holdout targets does not change the fit or first holdout predictions |
| Scaling | Centers and ranges use only training records |
| Division scope | Altering another division's yields leaves scoped model and output unchanged |
| Forecasts | Feature contributions reconstruct predictions; area conversion is consistent |
| Model limits | Extrapolation and nonnegative clipping are flagged |
| Assistant | Bilingual equivalence and unsupported-question abstention |
| Sensitivity | Only the rainfall feature changes |
| Planning | Explicit assumptions, worker-day arithmetic and upward rounding |
| Input contract | Invalid values, dates, gaps, area changes and conflicting duplicates fail |
| CLI | Output file equals response; invalid scope fails; input overwrite is blocked |

The observed synthetic holdout MAE is 0.046992 t/ha/month for ridge and 0.208171 for the previous-month baseline. These figures are reproduced in the generated evaluation output. They are not measurements of customer performance or evidence of a field-ready agronomic model.

GitHub Actions is configured to run tests and regenerate samples on Python 3.11–3.13. This record reports local validation; remote CI execution must be checked separately after publication.
