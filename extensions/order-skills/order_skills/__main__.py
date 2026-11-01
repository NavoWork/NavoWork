"""Offline checks only: python -m order_skills OPERATION INPUT.json (or -)."""

import argparse
import json
from pathlib import Path
import sys

from .adapter import OPERATIONS
from .domain import InvalidInput


def main(argv=None):
    parser = argparse.ArgumentParser(description="Offline deterministic checks; no host permissions, model, file generation or approval.")
    parser.add_argument("operation", choices=OPERATIONS)
    parser.add_argument("input", help="UTF-8 JSON path, or - for stdin")
    args = parser.parse_args(argv)
    try:
        raw = sys.stdin.read() if args.input == "-" else Path(args.input).read_text(encoding="utf-8-sig")
        request = json.loads(raw)
        result = {"mode": "offline_deterministic", "operation": args.operation,
                  "analysis": OPERATIONS[args.operation](request)}
        code = 0  # Findings are business results; malformed input is exit 2.
    except (InvalidInput, ValueError, OSError) as error:
        result = {"mode": "offline_deterministic", "error": "INVALID_INPUT", "message": str(error)}
        code = 2
    print(json.dumps(result, ensure_ascii=True, indent=2, allow_nan=False))
    return code


if __name__ == "__main__":
    sys.exit(main())
