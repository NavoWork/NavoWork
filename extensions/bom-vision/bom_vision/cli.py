from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .adapters import AdapterError, OpenAICompatibleAdapter
from .core import InputError, MAX_BYTES, correct, recognize, revalidate


def _read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="BOM image → reviewable candidates; no approval")
    sub = parser.add_subparsers(dest="command", required=True)
    extract = sub.add_parser("recognize")
    extract.add_argument("image", type=Path)
    extract.add_argument("--file-ref", type=Path, help="opaque versioned FileRef JSON; otherwise local URI")
    validate = sub.add_parser("validate")
    validate.add_argument("candidate", type=Path)
    edit = sub.add_parser("correct")
    edit.add_argument("candidate", type=Path)
    edit.add_argument("patches", type=Path)
    edit.add_argument("--expected-revision", type=int, required=True)
    edit.add_argument("--actor", required=True)
    edit.add_argument("--reason", required=True)
    for child in (extract, validate, edit):
        child.add_argument("--out", type=Path, help="new JSON file; refuses overwrite")
    args = parser.parse_args(argv)
    try:
        if args.command == "recognize":
            # Configure before opening file; no fake or text-rule fallback.
            adapter = OpenAICompatibleAdapter.from_environment()
            with args.image.open("rb") as stream:
                image = stream.read(MAX_BYTES + 1)
            ref = _read_json(args.file_ref) if args.file_ref else {
                "uri": args.image.resolve().as_uri(), "scope": "local-cli-only"}
            result = recognize(image, ref, adapter)
        elif args.command == "validate":
            result = revalidate(_read_json(args.candidate))
        else:
            result = correct(_read_json(args.candidate), _read_json(args.patches),
                             expected_revision=args.expected_revision, actor=args.actor, reason=args.reason)
        output = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            with args.out.open("x", encoding="utf-8") as stream:
                stream.write(output)
        else:
            sys.stdout.write(output)
        return 0
    except (InputError, AdapterError) as exc:
        sys.stderr.write(json.dumps({"status": "blocked", "code": str(exc)}) + "\n")
        return 2
    except (OSError, ValueError, TypeError, KeyError):
        sys.stderr.write('{"status":"blocked","code":"local_io_or_candidate_invalid"}\n')
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
