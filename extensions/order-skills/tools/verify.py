"""Run module tests, optionally requiring the isolated QA dependencies."""

import argparse
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--qa-deps", type=Path, help="Additional package directory, e.g. .qa/deps")
    parser.add_argument("--require-qa", action="store_true", help="Fail if Schema/PDF QA dependencies are unavailable")
    args = parser.parse_args()
    if args.qa_deps:
        sys.path.insert(0, str(args.qa_deps.resolve()))
    if args.require_qa:
        try:
            from jsonschema import Draft202012Validator  # noqa: F401
            from pypdf import PdfReader  # noqa: F401
        except ImportError as error:
            parser.error(f"QA dependency unavailable: {error}")
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.discover(str(ROOT / "tests")))
    return 0 if result.wasSuccessful() and not (args.require_qa and result.skipped) else 1


if __name__ == "__main__":
    sys.exit(main())
