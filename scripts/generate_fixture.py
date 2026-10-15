"""Generate fictional monthly observations. This is not an agronomic simulator."""
import csv
import math
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COLUMNS = ['record_id', 'division', 'block', 'month', 'area_ha', 'palm_age_years',
           'rainfall_mm', 'fertilizer_kg_ha', 'upkeep_pct', 'yield_t_ha']


def main():
    rng = random.Random(1729)
    records = []
    for division, block, area, age in [('DIV_A', 'A01', 40, 9), ('DIV_A', 'A02', 55, 12),
                                       ('DIV_B', 'B01', 35, 8), ('DIV_B', 'B02', 60, 14)]:
        previous = None
        for t in range(48):
            index = 2022 * 12 + 9 + t
            month = f'{index // 12:04d}-{index % 12 + 1:02d}'
            seasonal = math.sin(2 * math.pi * (index % 12) / 12)
            rainfall = round(max(0, 180 + 100 * seasonal + rng.uniform(-65, 65)), 2)
            fertilizer = round(rng.uniform(10, 75), 2)
            upkeep = round(rng.uniform(55, 98), 2)
            palm_age = round(age + t / 12, 4)
            if previous is None:
                observed_yield = 2.1 + rng.uniform(-0.2, 0.2)
            else:
                observed_yield = (0.55 + 0.42 * previous['yield_t_ha']
                                  + 0.0018 * previous['rainfall_mm']
                                  + 0.005 * previous['fertilizer_kg_ha']
                                  + 0.004 * previous['upkeep_pct']
                                  - 0.012 * previous['palm_age_years']
                                  + 0.23 * seasonal + rng.uniform(-0.12, 0.12))
            row = {'record_id': f'OBS_{block}_{month.replace("-", "")}', 'division': division,
                   'block': block, 'month': month, 'area_ha': area, 'palm_age_years': palm_age,
                   'rainfall_mm': rainfall, 'fertilizer_kg_ha': fertilizer, 'upkeep_pct': upkeep,
                   'yield_t_ha': round(max(0, observed_yield), 4)}
            records.append(row)
            previous = row
    records.sort(key=lambda r: (r['month'], r['division'], r['block']))
    with (ROOT / 'samples/history.csv').open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS, lineterminator='\n')
        writer.writeheader()
        writer.writerows(records)
    print(f'Generated {len(records)} synthetic observations with seed 1729.')


if __name__ == '__main__':
    main()
