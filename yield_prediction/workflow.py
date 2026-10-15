"""Scoped historical, forecasting, sensitivity and capacity-planning views."""
import hashlib
import json
import math
from statistics import mean
from .data import InputError, group, load, month_index, month_label
from .model import FEATURES, RIDGE_ALPHA, evaluate, examples, features, fit, predict

QUESTIONS = {
    'forecast': ('forecast next month', 'prediksi bulan depan'),
    'history': ('show historical yield', 'tampilkan hasil historis'),
    'evaluation': ('show model evaluation', 'tampilkan evaluasi model'),
    'scenario': ('simulate lower rainfall', 'simulasi curah hujan lebih rendah'),
    'plan': ('draft harvest plan', 'buat rencana panen'),
}


def forecast(rows, model, target, rainfall_multiplier=1.0):
    results = []
    for (division, block), records in sorted(group(rows).items()):
        previous = records[-1]
        altered = dict(previous, rainfall_mm=previous['rainfall_mm'] * rainfall_multiplier)
        x = features(altered, target)
        value, explanation = predict(model, x)
        results.append({'division': division, 'block': block, 'forecast_month': target,
                        'area_ha': previous['area_ha'], 'prediction_t_ha': round(value, 6),
                        'prediction_tonnes': round(value * previous['area_ha'], 6),
                        'source_id': previous['record_id'], 'feature_values': dict(zip(FEATURES, x)),
                        'explanation': explanation})
    return results


def planning(predictions, assumptions):
    if not isinstance(assumptions, dict) or set(assumptions) != {'working_days', 'tonnes_per_worker_day'}:
        raise InputError('Plan requires working_days and tonnes_per_worker_day.')
    days, capacity = assumptions['working_days'], assumptions['tonnes_per_worker_day']
    if isinstance(days, bool) or not isinstance(days, int) or not 1 <= days <= 31:
        raise InputError('working_days must be an integer from 1 to 31.')
    if isinstance(capacity, bool) or not isinstance(capacity, (int, float)) or not math.isfinite(capacity) or not 0 < capacity <= 100:
        raise InputError('tonnes_per_worker_day must be finite, positive and at most 100.')
    return {'assumptions': assumptions, 'blocks': [
        {'division': p['division'], 'block': p['block'], 'forecast_month': p['forecast_month'],
         'forecast_tonnes': p['prediction_tonnes'],
         'worker_days': round(p['prediction_tonnes'] / capacity, 2),
         'workers_per_day_rounded_up': math.ceil(p['prediction_tonnes'] / capacity / days)} for p in predictions],
        'review_status': 'draft_for_human_review',
        'limitations': ['Uniform daily capacity assumption; not a daily harvest schedule or an optimized roster.',
                        'Does not account for ripeness, terrain, weather, safety, existing staffing or worker availability.']}


def run(source, as_of, question, role='management', division=None, assumptions=None):
    if not isinstance(question, str) or not 1 <= len(question.strip()) <= 500:
        raise InputError('Question must contain 1 to 500 characters.')
    rows = load(source, as_of, role, division)
    normalized = ' '.join(question.lower().strip().rstrip('?.!').split())
    intent = next((k for k, aliases in QUESTIONS.items() if normalized in aliases), None)
    result = {'status': 'answered', 'mode': 'synthetic_portfolio_demo', 'as_of': as_of,
              'scope': {'role': role, 'division': division or 'ALL'}, 'question': question,
              'intent': intent, 'review_status': 'human_review_required',
              'trace': ['validate_monthly_data', 'filter_division_before_training', 'route_supported_question']}
    if intent is None:
        return dict(result, status='unsupported_question', answer='No supported intent matched; no prediction was generated.',
                    supported_questions=[v[0] for v in QUESTIONS.values()])
    result['data_provenance'] = {'scoped_record_count': len(rows), 'start_month': rows[0]['month'],
                                 'end_month': rows[-1]['month'],
                                 'sha256': hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest(),
                                 'record_ids': [r['record_id'] for r in rows]}
    if intent == 'history':
        result['answer'] = {'blocks': [
            {'division': d, 'block': b, 'months': len(records),
             'mean_monthly_yield_t_ha': round(mean(r['yield_t_ha'] for r in records), 6),
             'total_observed_production_tonnes': round(sum(r['yield_t_ha'] * r['area_ha'] for r in records), 6),
             'latest': records[-1]} for (d, b), records in sorted(group(rows).items())]}
        return result
    items = examples(rows)
    result['evaluation'] = evaluate(items, as_of)
    if intent == 'evaluation':
        result['answer'] = 'Chronological holdout metrics and per-record evidence are included in evaluation.'
        return result
    model = fit(items)
    target = month_label(month_index(as_of) + 1)
    predictions = forecast(rows, model, target)
    result['model'] = {'algorithm': 'ridge_regression', 'alpha': RIDGE_ALPHA, 'feature_names': FEATURES, **model}
    result['trace'].extend(['evaluate_on_chronological_holdout', 'refit_on_all_available_history', 'predict_one_month_ahead'])
    result['forecast'] = predictions
    result['forecast_total_tonnes'] = round(sum(p['prediction_tonnes'] for p in predictions), 6)
    result['limitations'] = ['Synthetic model and data; not validated for agricultural decisions.',
                            'Linear contributions explain model arithmetic, not causal agronomic effects.',
                            'No calibrated uncertainty interval is available; extrapolation is flagged.',
                            'Caller-selected role and division simulate scoping; they are not authentication.']
    if intent == 'scenario':
        altered = forecast(rows, model, target, rainfall_multiplier=0.8)
        result['scenario'] = {'assumption': 'Reduce the previous-month rainfall feature by 20 percent, holding all other features fixed.',
                              'kind': 'model_sensitivity_not_causal_intervention', 'predictions': altered,
                              'delta_total_tonnes': round(sum(p['prediction_tonnes'] for p in altered) - result['forecast_total_tonnes'], 6),
                              'limitation': 'This changes a historical input hypothetically; it is not a future weather forecast or treatment recommendation.'}
    if intent == 'plan':
        result['plan'] = planning(predictions, assumptions)
    return result
