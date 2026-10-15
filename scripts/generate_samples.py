"""Regenerate actual CLI responses from the committed synthetic fixture."""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    base = [sys.executable, '-m', 'yield_prediction', 'ask', 'samples/history.csv']
    cases = {
        'output_forecast.json': ['forecast next month'],
        'output_field.json': ['prediksi bulan depan', '--role', 'field', '--division', 'DIV_A'],
        'output_history.json': ['show historical yield'],
        'output_evaluation.json': ['show model evaluation'],
        'output_scenario.json': ['simulate lower rainfall'],
        'output_plan.json': ['buat rencana panen', '--planning', 'samples/planning.json'],
        'output_unsupported.json': ['Tell me the exact fertilizer dose to apply'],
        'output_invalid_scope.json': ['forecast next month', '--role', 'field'],
    }
    for filename, args in cases.items():
        p = subprocess.run(base + args + ['--as-of', '2026-09'], cwd=ROOT,
                           text=True, capture_output=True, encoding='utf-8')
        expected = 1 if filename == 'output_invalid_scope.json' else 0
        if p.returncode != expected:
            raise RuntimeError(f'CLI example failed: {filename}')
        result = json.loads(p.stdout)
        (ROOT / 'samples' / filename).write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(f'Generated {len(cases)} CLI outputs.')


if __name__ == '__main__':
    main()
