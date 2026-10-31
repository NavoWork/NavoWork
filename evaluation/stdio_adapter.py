"""Absolute-file CLI entrypoint for the OFFLINE adapter, runnable from a staged cwd."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from evaluation.reference_adapter import run

if __name__ == "__main__":
    print(json.dumps(run(json.load(sys.stdin)), ensure_ascii=False))
