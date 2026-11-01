from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from demo_mock import Catalog, MockError
from demo_mock.catalog import MAX_JSON_BYTES, decode_json, read_bytes

from .core import InputError, MAX_BYTES
from .mock import mock_recognize


def main(argv=None):
    parser = argparse.ArgumentParser(description="BOM mock: image hash → fixture → existing candidates/validation")
    parser.add_argument("image", type=Path)
    parser.add_argument("--catalog", required=True, type=Path)
    parser.add_argument("--file-ref", type=Path)
    parser.add_argument("--out", type=Path, help="new JSON result; refuses overwrite")
    args = parser.parse_args(argv)
    try:
        image = read_bytes(args.image, MAX_BYTES)
        ref = decode_json(read_bytes(args.file_ref, MAX_JSON_BYTES)) if args.file_ref else {
            "uri": args.image.resolve().as_uri(), "scope": "local-cli-only"}
        result = mock_recognize(image, ref, catalog=Catalog.load(args.catalog))
        output = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            with args.out.open("x", encoding="utf-8") as stream:
                stream.write(output)
        else:
            sys.stdout.write(output)
        return 0
    except (MockError, InputError) as exc:
        sys.stderr.write(json.dumps({"status": "blocked", "mode": "mock", "code": str(exc)}) + "\n")
        return 2
    except (OSError, TypeError, ValueError):
        sys.stderr.write('{"status":"blocked","mode":"mock","code":"mock_local_io_failed"}\n')
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
