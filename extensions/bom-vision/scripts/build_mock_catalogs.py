"""Explicit authoring helper for the checked-in demo catalogs; replay never runs this."""
import json
from pathlib import Path

from demo_mock import Catalog, fingerprint
from demo_mock.catalog import MAX_JSON_BYTES, decode_json, read_bytes

ROOT = Path(__file__).resolve().parents[1]


def scenario(sid, workflow, operation, inputs, output):
    return {"id": sid, "workflow": workflow, "operation": operation,
            "inputs": {name: fingerprint(value) for name, value in inputs.items()},
            "output": {"path": output.name,
                       "sha256": fingerprint(decode_json(read_bytes(output, MAX_JSON_BYTES)))["sha256"]}}


def save(path, catalog_id, scenarios):
    document = {"schema_version": 1, "catalog_id": catalog_id, "scenarios": scenarios}
    Catalog(document, path.parent).check()
    path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main():
    samples = ROOT / "samples"
    manifest = json.loads((samples / "manifest.json").read_text(encoding="utf-8"))
    rows = [scenario(name, "bom", "extract", {"image": read_bytes(samples / item["image"])},
                     samples / item["fake_response"]) for name, item in manifest.items()]
    save(samples / "mock.catalog.json", "bom-demo-v1", rows)
    example = ROOT / "examples/document-demo"
    request = decode_json(read_bytes(example / "request.json"))
    summary = decode_json(read_bytes(example / "summary.json"))
    save(example / "catalog.json", "document-demo-v1", [
        scenario("summary-zh", "document-demo", "summarize", {"request": request}, example / "summary.json"),
        scenario("actions-zh", "document-demo", "next-actions", {"summary": summary}, example / "actions.json"),
    ])


if __name__ == "__main__":
    main()
