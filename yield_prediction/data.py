"""Strict monthly data contracts and scope filtering before model fitting."""
import csv
import math
import re
from pathlib import Path


class InputError(ValueError):
    pass


COLUMNS = ['record_id', 'division', 'block', 'month', 'area_ha', 'palm_age_years',
           'rainfall_mm', 'fertilizer_kg_ha', 'upkeep_pct', 'yield_t_ha']
LIMITS = {'area_ha': (0.01, 10000), 'palm_age_years': (3, 40), 'rainfall_mm': (0, 2000),
          'fertilizer_kg_ha': (0, 1000), 'upkeep_pct': (0, 100), 'yield_t_ha': (0, 10)}


def month_index(value):
    if not isinstance(value, str) or not re.fullmatch(r'\d{4}-(0[1-9]|1[0-2])', value):
        raise InputError('Month must use YYYY-MM.')
    year, month = map(int, value.split('-'))
    if not 1900 <= year <= 2100:
        raise InputError('Year must be between 1900 and 2100.')
    return year * 12 + month - 1


def month_label(index):
    return f'{index // 12:04d}-{index % 12 + 1:02d}'


def load(source, as_of, role='management', division=None):
    end = month_index(as_of)
    if role not in ('management', 'field'):
        raise InputError('Unknown role.')
    if role == 'field' and not division:
        raise InputError('Field role requires a division.')
    source = Path(source)
    if source.stat().st_size > 5_000_000:
        raise InputError('Input exceeds 5 MB.')
    with source.open(encoding='utf-8', newline='') as f:
        reader = csv.DictReader(f)
        if reader.fieldnames != COLUMNS:
            raise InputError('CSV headers must match the documented order and names.')
        rows = list(reader)
    if not rows or len(rows) > 10000:
        raise InputError('Supply 1 to 10000 observations.')
    seen, keys, cleaned = {}, set(), []
    for raw in rows:
        if set(raw) != set(COLUMNS) or any(v is None for v in raw.values()):
            raise InputError('Malformed CSV row.')
        row = dict(raw)
        for key in ('record_id', 'division', 'block'):
            if not re.fullmatch(r'[A-Z][A-Z0-9_-]{0,39}', row[key]):
                raise InputError('Identifiers must use uppercase letters, digits, underscores or hyphens.')
        if month_index(row['month']) > end:
            raise InputError('Observations later than as_of are not allowed.')
        for key, (low, high) in LIMITS.items():
            try:
                row[key] = float(row[key])
            except (ValueError, TypeError):
                raise InputError('Measurements must be numeric.') from None
            if not math.isfinite(row[key]) or not low <= row[key] <= high:
                raise InputError('Measurement is nonfinite or outside the demo input range.')
        if row['record_id'] in seen:
            if row != seen[row['record_id']]:
                raise InputError('Conflicting duplicate record ID.')
            continue
        natural = (row['division'], row['block'], row['month'])
        if natural in keys:
            raise InputError('Multiple records for the same block and month.')
        keys.add(natural)
        seen[row['record_id']] = row
        cleaned.append(row)
    if division and division not in {r['division'] for r in cleaned}:
        raise InputError('Unknown division.')
    scoped = [r for r in cleaned if division is None or r['division'] == division]
    groups = group(scoped)
    for records in groups.values():
        indices = [month_index(r['month']) for r in records]
        if indices[-1] != end:
            raise InputError('Every selected block must have a reading at as_of.')
        if len(indices) < 36 or indices != list(range(indices[0], end + 1)):
            raise InputError('Each block requires at least 36 consecutive months with no gaps.')
        if len({r['area_ha'] for r in records}) != 1:
            raise InputError('Block area must remain constant in this demo.')
    return sorted(scoped, key=lambda r: (r['month'], r['division'], r['block']))


def group(rows):
    groups = {}
    for row in rows:
        groups.setdefault((row['division'], row['block']), []).append(row)
    for records in groups.values():
        records.sort(key=lambda r: r['month'])
    return groups
