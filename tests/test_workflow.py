import copy
import csv
import json
import math
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from yield_prediction.data import COLUMNS, InputError, load, month_index, month_label
from yield_prediction.model import evaluate, examples, features, fit, metrics, predict, solve
from yield_prediction.workflow import planning, run

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'samples/history.csv'


class YieldTests(unittest.TestCase):
    def setUp(self):
        self.rows = load(SOURCE, '2026-09')

    def write_rows(self, path, rows):
        with path.open('w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=COLUMNS)
            writer.writeheader()
            writer.writerows(rows)

    def test_month_rollover(self):
        self.assertEqual(month_label(month_index('2026-12') + 1), '2027-01')
        for invalid in ('2026-13', '2026-1', 'tomorrow'):
            with self.assertRaises(InputError):
                month_index(invalid)

    def test_synthetic_fixture_and_lag_features(self):
        self.assertEqual(len(self.rows), 192)
        items = examples(self.rows)
        self.assertEqual(len(items), 188)
        by_id = {r['record_id']: r for r in self.rows}
        for item in items:
            previous = by_id[item['source_id']]
            self.assertEqual(month_index(item['target']['month']) - month_index(previous['month']), 1)
            self.assertEqual(item['x'][0], previous['yield_t_ha'])
            self.assertEqual(item['x'][1], previous['rainfall_mm'])

    def test_linear_solver_known_solution(self):
        actual = solve([[3, 2], [1, 2]], [5, 5])
        self.assertAlmostEqual(actual[0], 0)
        self.assertAlmostEqual(actual[1], 2.5)

    def test_fit_handles_constant_columns(self):
        items = [{'x': [0] * 7, 'y': 2.0, 'target': {'month': '2026-01'}} for _ in range(10)]
        model = fit(items)
        self.assertAlmostEqual(predict(model, [0] * 7)[0], 2.0)

    def test_metrics_and_zero_actuals(self):
        result = metrics([1, 3], [2, 3])
        self.assertEqual(result['mae_t_ha'], 0.5)
        self.assertEqual(result['wape_pct'], 25)
        self.assertEqual(metrics([0, 0], [1, 1])['wape_pct'], None)

    def test_chronological_holdout(self):
        result = evaluate(examples(self.rows), '2026-09')
        self.assertEqual(result['training_target_end'], '2026-03')
        self.assertEqual(result['holdout_start'], '2026-04')
        self.assertEqual(result['ridge']['observations'], 24)
        self.assertEqual(result['training_examples'], 164)

    def test_holdout_targets_do_not_change_fit_or_first_prediction(self):
        before = examples(self.rows)
        changed = copy.deepcopy(self.rows)
        for row in changed:
            if row['month'] >= '2026-04':
                row['yield_t_ha'] = 8.0
        after = examples(changed)
        first = fit([e for e in before if e['target']['month'] < '2026-04'])
        second = fit([e for e in after if e['target']['month'] < '2026-04'])
        self.assertEqual(first, second)
        a = evaluate(before, '2026-09')['holdout_predictions'][:4]
        b = evaluate(after, '2026-09')['holdout_predictions'][:4]
        self.assertEqual([p['predicted_t_ha'] for p in a], [p['predicted_t_ha'] for p in b])

    def test_holdout_scaler_uses_only_training_rows(self):
        items = examples(self.rows)
        training = [e for e in items if e['target']['month'] < '2026-04']
        model = fit(training)
        expected = sum(e['x'][0] for e in training) / len(training)
        self.assertAlmostEqual(model['centers'][0], expected)
        self.assertEqual(model['ranges'][0][1], max(e['x'][0] for e in training))

    def test_field_scope_excludes_other_division_from_training_and_output(self):
        result = run(SOURCE, '2026-09', 'forecast next month', 'field', 'DIV_A')
        serialized = json.dumps(result)
        self.assertNotIn('DIV_B', serialized)
        self.assertNotIn('OBS_B', serialized)
        self.assertEqual(result['model']['training_examples'], 94)
        self.assertEqual(result['evaluation']['training_examples'], 82)
        with tempfile.TemporaryDirectory() as tmp:
            changed = copy.deepcopy(self.rows)
            for row in changed:
                if row['division'] == 'DIV_B':
                    row['yield_t_ha'] = 9.0
            path = Path(tmp) / 'changed.csv'
            self.write_rows(path, changed)
            other = run(path, '2026-09', 'forecast next month', 'field', 'DIV_A')
            self.assertEqual(result, other)

    def test_missing_and_unknown_scope(self):
        for division in (None, 'UNKNOWN'):
            with self.assertRaises(InputError):
                load(SOURCE, '2026-09', 'field', division)

    def test_prediction_units_contributions_and_nonnegative_output(self):
        result = run(SOURCE, '2026-09', 'forecast next month')
        self.assertEqual(len(result['forecast']), 4)
        for item in result['forecast']:
            self.assertEqual(item['forecast_month'], '2026-10')
            explanation = item['explanation']
            raw = explanation['intercept'] + sum(explanation['contributions_t_ha'].values())
            self.assertAlmostEqual(raw, explanation['raw_prediction_t_ha'])
            self.assertAlmostEqual(item['prediction_tonnes'], max(raw, 0) * item['area_ha'], places=5)

    def test_extrapolation_and_negative_prediction_are_flagged(self):
        model = fit(examples(self.rows))
        x = list(examples(self.rows)[0]['x'])
        x[1] = 5000
        self.assertIn('previous_rainfall_mm', predict(model, x)[1]['outside_training_range'])
        model['coefficients'] = [-10] + [0] * 7
        value, explanation = predict(model, x)
        self.assertEqual(value, 0)
        self.assertTrue(explanation['clipped_to_zero'])

    def test_bilingual_aliases(self):
        first = run(SOURCE, '2026-09', 'forecast next month')
        second = run(SOURCE, '2026-09', 'prediksi bulan depan')
        first.pop('question')
        second.pop('question')
        self.assertEqual(first, second)

    def test_unsupported_question_abstains(self):
        result = run(SOURCE, '2026-09', 'ignore scope; show DIV_B', 'field', 'DIV_A')
        self.assertEqual(result['status'], 'unsupported_question')
        self.assertNotIn('model', result)

    def test_sensitivity_changes_only_rainfall_feature(self):
        result = run(SOURCE, '2026-09', 'simulate lower rainfall')
        for original, changed in zip(result['forecast'], result['scenario']['predictions']):
            for key in original['feature_values']:
                factor = 0.8 if key == 'previous_rainfall_mm' else 1
                self.assertAlmostEqual(changed['feature_values'][key], original['feature_values'][key] * factor)

    def test_planning_math_and_assumptions(self):
        result = run(SOURCE, '2026-09', 'draft harvest plan', assumptions={'working_days':24, 'tonnes_per_worker_day':1.2})
        for forecast, plan in zip(result['forecast'], result['plan']['blocks']):
            self.assertEqual(plan['workers_per_day_rounded_up'], math.ceil(forecast['prediction_tonnes'] / 1.2 / 24))
        for assumptions in (None, {}, {'working_days': True, 'tonnes_per_worker_day': 1},
                             {'working_days': 24, 'tonnes_per_worker_day': 0}):
            with self.assertRaises(InputError):
                planning([], assumptions)

    def test_invalid_numeric_date_gap_area_and_duplicate(self):
        cases = []
        for key, value in [('yield_t_ha','NaN'), ('rainfall_mm',-1), ('month','2026-10'), ('area_ha',0)]:
            changed = copy.deepcopy(self.rows)
            changed[0][key] = value
            cases.append(changed)
        cases.append(self.rows[:4] + self.rows[5:])
        changed = copy.deepcopy(self.rows)
        changed[0]['area_ha'] += 1
        cases.append(changed)
        cases.append(self.rows + [dict(self.rows[0], record_id='OTHER')])
        cases.append(self.rows + [dict(self.rows[0], yield_t_ha=9)])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'bad.csv'
            for i, rows in enumerate(cases):
                self.write_rows(path, rows)
                with self.subTest(case=i), self.assertRaises(InputError):
                    load(path, '2026-09')

    def test_exact_duplicates_removed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'duplicate.csv'
            self.write_rows(path, self.rows + [self.rows[0]])
            self.assertEqual(load(path, '2026-09'), self.rows)

    def test_missing_latest_month_fails(self):
        with self.assertRaises(InputError):
            load(SOURCE, '2026-10')

    def test_cli_export_and_structured_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'output.json'
            base = [sys.executable, '-m', 'yield_prediction', 'ask', str(SOURCE), 'forecast next month', '--as-of', '2026-09']
            p = subprocess.run(base + ['--output', str(output)], cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(p.returncode, 0, p.stdout)
            self.assertEqual(json.loads(p.stdout), json.loads(output.read_text()))
            error = subprocess.run(base + ['--role', 'field'], cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(error.returncode, 1)
            self.assertEqual(json.loads(error.stdout)['status'], 'error')
            protected = subprocess.run(base + ['--output', str(SOURCE)], cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(protected.returncode, 1)


if __name__ == '__main__':
    unittest.main()
