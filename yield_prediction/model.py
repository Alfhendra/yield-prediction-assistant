"""Small ridge regression, fit-time scaling and chronological evaluation."""
import math
from statistics import mean
from .data import group, month_index, month_label

FEATURES = ['previous_yield_t_ha', 'previous_rainfall_mm', 'previous_fertilizer_kg_ha',
            'previous_upkeep_pct', 'previous_palm_age_years', 'target_month_sin', 'target_month_cos']
RIDGE_ALPHA = 1.0


def features(previous, target_month):
    angle = 2 * math.pi * (month_index(target_month) % 12) / 12
    return [previous['yield_t_ha'], previous['rainfall_mm'], previous['fertilizer_kg_ha'],
            previous['upkeep_pct'], previous['palm_age_years'], math.sin(angle), math.cos(angle)]


def examples(rows):
    result = []
    for records in group(rows).values():
        for previous, target in zip(records, records[1:]):
            result.append({'x': features(previous, target['month']), 'y': target['yield_t_ha'],
                           'target': target, 'source_id': previous['record_id']})
    return sorted(result, key=lambda e: (e['target']['month'], e['target']['division'], e['target']['block']))


def solve(matrix, vector):
    """Gaussian elimination with partial pivoting for a tiny regularized system."""
    a = [list(row) + [value] for row, value in zip(matrix, vector)]
    n = len(vector)
    for col in range(n):
        pivot = max(range(col, n), key=lambda row: abs(a[row][col]))
        a[col], a[pivot] = a[pivot], a[col]
        if abs(a[col][col]) < 1e-12:
            raise ValueError('Singular model system.')
        scale = a[col][col]
        a[col] = [v / scale for v in a[col]]
        for row in range(n):
            if row != col:
                multiple = a[row][col]
                a[row] = [v - multiple * p for v, p in zip(a[row], a[col])]
    return [row[-1] for row in a]


def fit(items):
    xs, ys = [e['x'] for e in items], [e['y'] for e in items]
    centers = [mean(col) for col in zip(*xs)]
    scales = [math.sqrt(mean((row[j] - centers[j]) ** 2 for row in xs)) or 1.0 for j in range(len(FEATURES))]
    normalized = [[1.0] + [(v - c) / s for v, c, s in zip(row, centers, scales)] for row in xs]
    n = len(FEATURES) + 1
    matrix = [[sum(row[i] * row[j] for row in normalized) + (RIDGE_ALPHA if i == j and i > 0 else 0)
               for j in range(n)] for i in range(n)]
    vector = [sum(row[i] * y for row, y in zip(normalized, ys)) for i in range(n)]
    return {'coefficients': solve(matrix, vector), 'centers': centers, 'scales': scales,
            'ranges': [[min(col), max(col)] for col in zip(*xs)], 'training_examples': len(items),
            'trained_through': max(e['target']['month'] for e in items)}


def predict(model, x):
    terms = [w * (v - c) / s for w, v, c, s in
             zip(model['coefficients'][1:], x, model['centers'], model['scales'])]
    raw = model['coefficients'][0] + sum(terms)
    return max(0.0, raw), {'intercept': model['coefficients'][0],
                         'contributions_t_ha': dict(zip(FEATURES, terms)), 'raw_prediction_t_ha': raw,
                         'clipped_to_zero': raw < 0,
                         'outside_training_range': [name for name, v, bounds in zip(FEATURES, x, model['ranges'])
                                                    if v < bounds[0] - 1e-9 or v > bounds[1] + 1e-9]}


def metrics(actual, predicted):
    errors = [a - p for a, p in zip(actual, predicted)]
    total = sum(abs(a) for a in actual)
    return {'mae_t_ha': round(mean(abs(e) for e in errors), 6),
            'rmse_t_ha': round(math.sqrt(mean(e * e for e in errors)), 6),
            'wape_pct': round(100 * sum(abs(e) for e in errors) / total, 4) if total else None,
            'observations': len(actual)}


def evaluate(items, as_of):
    start = month_label(month_index(as_of) - 5)
    train = [e for e in items if e['target']['month'] < start]
    test = [e for e in items if e['target']['month'] >= start]
    model = fit(train)
    actual = [e['y'] for e in test]
    predicted = [predict(model, e['x'])[0] for e in test]
    baseline = [e['x'][0] for e in test]
    return {'method': 'fixed_training_window_then_six_month_one_step_holdout',
            'holdout_start': start, 'holdout_end': as_of,
            'training_target_end': model['trained_through'], 'training_examples': len(train),
            'ridge': metrics(actual, predicted), 'previous_month_baseline': metrics(actual, baseline),
            'holdout_predictions': [{'target_id': e['target']['record_id'], 'source_id': e['source_id'],
                                     'month': e['target']['month'], 'actual_t_ha': e['y'],
                                     'predicted_t_ha': round(p, 6), 'baseline_t_ha': e['x'][0]}
                                    for e, p in zip(test, predicted)],
            'limitations': ['Each holdout prediction uses actual previous-month observations available at that origin.',
                            'This is not a six-month-ahead forecast.',
                            'Metrics describe synthetic data only; WAPE is an error measure, not accuracy.']}
