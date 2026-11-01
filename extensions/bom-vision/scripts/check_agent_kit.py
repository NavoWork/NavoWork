"""Read-only compatibility check against a committed agent-kit, no checkout/merge.

Only the two real package source files are materialized into a temporary folder;
no shared types are checked into this extension and no uncommitted files are read.
"""
import argparse
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--revision", default="d23ab0a")
    args = parser.parse_args()
    revision = subprocess.check_output(["git", "rev-parse", "--verify", args.revision + "^{commit}"], cwd=ROOT, text=True).strip()
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        for relative in ("__init__.py", "contracts/__init__.py"):
            data = subprocess.check_output(["git", "show", f"{revision}:agent-kit/src/navowork_agent/{relative}"], cwd=ROOT)
            target = tmp / "navowork_agent" / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        sys.path.insert(0, str(tmp))
        print("Testing actual committed contracts at", revision)
        suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"), pattern="test_agent_kit.py")
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        return 0 if result.wasSuccessful() and not result.skipped else 1


if __name__ == "__main__":
    raise SystemExit(main())
