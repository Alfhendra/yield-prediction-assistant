# Portfolio introduction

This is my compact yield-prediction portfolio demo, developed with AI assistance. It makes the core forecasting and assistant workflow runnable locally using synthetic monthly observations. The repository demonstrates validated ingestion, lagged features, chronological model evaluation, division-scoped forecasts, explainable calculations and a draft capacity plan.

## Suggested demonstration

1. Run the management forecast and trace an October prediction to its September source record.
2. Show the chronological evaluation and compare MAE with the previous-month baseline.
3. Explain why the holdout evaluates successive one-month forecasts and why it is not a six-month forecast.
4. Switch to a DIV_A field query and show that training, evidence and results exclude DIV_B.
5. Run the lower-rainfall sensitivity and explain why it is not a causal intervention.
6. Run the capacity plan with explicit productivity and working-day assumptions.
7. Run the tests, including the tests for holdout leakage and division isolation.

## Contribution note

Portfolio owner: Frederick Alfhendra. The owner supplied the domain direction, source context, confidentiality requirements and portfolio brief. AI assistance was used for the standalone implementation, synthetic fixtures, tests and documentation. This repository does not assign unverified responsibilities on a customer deployment or claim production outcomes. The owner's specific professional contribution to the original project should be described separately from this adaptation.

## Technical assessment discussion

The project provides concrete examples of data contracts, analytical tool boundaries, forecasting evaluation, model transparency and scope enforcement. The main engineering choices are visible in code and tests. The assistant is intentionally bounded, and all customer-specific systems are replaced with local components and fictional records.
