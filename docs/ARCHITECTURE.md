# Architecture and decisions

## Domain workflow

The demo represents four connected use cases: historical yield inspection, next-month forecasts, input sensitivity, and draft resource planning. A validated monthly dataset is the shared basis for all views. Source project material informed these broad categories; customer names, data, commercial terms, screenshots, model artifacts and infrastructure details are excluded.

## Separation of responsibilities

`data.py` parses the CSV and checks IDs, types, units, bounds, duplicate records, monthly continuity and constant block area. It selects the permitted division before analytical processing. The in-memory list is the common curated dataset; this demo does not implement a persistent data lake.

`model.py` creates one-step training examples: the observation at month t supplies predictors for the yield at t+1. Calendar seasonality for t+1 is known in advance. The target month's realized rainfall, fertilizer, upkeep and yield never enter that target's feature vector. Training-only scaling and fixed regularization keep the holdout separate from fitting.

`workflow.py` routes a supported phrase and composes the historical view, evaluation, forecast, sensitivity or plan. Source IDs, a digest of scoped records and feature values make each result inspectable. Forecast model metadata distinguishes the full-history refit from the earlier model used for holdout evaluation.

`__main__.py` handles file paths, JSON rendering, error responses and output protection. No SQL generation, model downloads, network calls or customer-site dependencies are required.

## Chronology and leakage boundaries

For the sample, the first target month is November 2022, training targets end in March 2026, and holdout targets span April–September 2026. During holdout evaluation, earlier holdout outcomes may appear as previous-month features for later one-step predictions. This is valid under the explicit assumption that last month's observations are available at each forecast origin. The fitted evaluation model and its scaler do not learn from any holdout target.

After evaluation, all observed targets through September are used in a new fit for the October forecast. This is intentionally different from reporting holdout errors on the final refitted model. No hyperparameter search is performed. A production evaluation should also account for reporting delays, multiple forecast horizons, geographic transfer and repeated rolling-origin refits.

## Scope and model behavior

Both training and prediction use only the selected division's records. Changing DIV_B observations cannot change a DIV_A field forecast, its scaler, evaluation or provenance. A management model may use both divisions and can produce different estimates. There is no shared hidden global model.

Local caller-selected roles demonstrate the filtering logic; they do not protect the CSV from the person running the program. A deployed service needs verified identity and server-side authorization for data, models, metrics and cached outputs.

## Deliberate trade-offs

- Ridge regression is compact, inspectable and stable for the small synthetic fixture. It does not capture long agronomic lags, nonlinear treatment effects or structural changes.
- The fixture's generating relationship is deliberately learnable. Its error metrics validate the software path, not the crop model's real-world usefulness.
- A previous-month yield baseline gives the error measures a point of comparison. The demo retains the fixed ridge model even if it performs worse on another dataset; there is no automatic promotion rule.
- Feature contributions sum to the raw linear prediction but are not causal explanations. Correlated inputs can make individual coefficients unstable or misleading.
- Out-of-range features and negative predictions are reported. There is no upper prediction cap or calibrated uncertainty interval.
- Capacity planning divides forecast tonnes by explicit worker-day capacity and working days, then rounds workers up per block. It does not optimize routes or assign individuals.

## Production extension map

| Local component | Possible production extension |
|---|---|
| CSV and in-memory curated data | Governed ingestion, warehouse, versioned datasets |
| Explicit monthly contract | Data-quality monitoring and delayed-report handling |
| Ridge and baseline evaluation | Agronomically reviewed features, multiple models, rolling backtests |
| Model metadata in JSON | Versioned model registry and evaluation gates |
| Exact bilingual routing | Constrained model-backed intent extraction and evaluated abstention |
| Caller-selected division | Verified identity and server-derived access policy |
| Source IDs and data digest | Durable provenance, audit records and retention policy |
| Draft capacity arithmetic | Human-reviewed planning with verified field constraints |

These are extension points, not implemented cloud integrations or claims of production readiness.
