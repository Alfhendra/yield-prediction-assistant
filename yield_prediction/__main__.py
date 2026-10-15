import argparse
import csv
import json
import sys
from pathlib import Path
from .data import InputError
from .workflow import QUESTIONS, run


def presentation(value):
    """Limit floating-point serialization noise across supported platforms."""
    if isinstance(value, float):
        return round(value, 8)
    if isinstance(value, dict):
        return {k: presentation(v) for k, v in value.items()}
    if isinstance(value, list):
        return [presentation(v) for v in value]
    return value


def main(argv=None):
    parser = argparse.ArgumentParser(description='Synthetic monthly yield forecasting demo; no cloud keys required.')
    sub = parser.add_subparsers(dest='command', required=True)
    a = sub.add_parser('ask')
    a.add_argument('history')
    a.add_argument('question')
    a.add_argument('--as-of', required=True)
    a.add_argument('--role', choices=['management', 'field'], default='management')
    a.add_argument('--division')
    a.add_argument('--planning', help='JSON file with capacity planning assumptions')
    a.add_argument('--output')
    sub.add_parser('questions')
    args = parser.parse_args(argv)
    try:
        if args.command == 'questions':
            result = QUESTIONS
        else:
            assumptions = json.loads(Path(args.planning).read_text(encoding='utf-8')) if args.planning else None
            result = run(args.history, args.as_of, args.question, args.role, args.division, assumptions)
        rendered = json.dumps(presentation(result), indent=2, ensure_ascii=False, allow_nan=False)
        if getattr(args, 'output', None):
            dest = Path(args.output)
            inputs = [args.history] + ([args.planning] if args.planning else [])
            if any(dest.resolve() == Path(p).resolve() for p in inputs):
                raise InputError('Output must not overwrite an input file.')
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(rendered + '\n', encoding='utf-8')
        print(rendered)
        return 0
    except (InputError, OSError, UnicodeError, ValueError, csv.Error) as exc:
        message = str(exc) if isinstance(exc, InputError) else 'Unable to process input or output. Check data and paths.'
        print(json.dumps({'status': 'error', 'error_type': type(exc).__name__, 'message': message}))
        return 1


if __name__ == '__main__':
    sys.exit(main())
