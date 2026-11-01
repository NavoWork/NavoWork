"""Explicit real-model acceptance. No replay path. Exit 2 = blocked, 1 = failed.

Run from extensions/bom-vision, after setting the model environment variables.
Saves real raw responses in ignored out/live/ for inspection; never logs config.
"""
import json
from pathlib import Path

from bom_vision import InputError, recognize
from bom_vision.adapters import AdapterError, OpenAICompatibleAdapter

ROOT = Path(__file__).resolve().parents[1]


def main():
    report = {"real_vision_acceptance": "not_accepted", "cases": {}}
    try:
        adapter = OpenAICompatibleAdapter.from_environment()
        manifest = json.loads((ROOT / "samples/manifest.json").read_text())
        results = {}
        for name, item in manifest.items():
            image = ROOT / "samples" / item["image"]
            result = recognize(image.read_bytes(), {"uri": image.as_uri(), "scope": "local-live-test"}, adapter)
            results[name] = result
            out = ROOT / "out/live"
            out.mkdir(parents=True, exist_ok=True)
            (out / (name + ".json")).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            report["cases"][name] = {"row_count": len(result["rows"]), "issues": [x["code"] for x in result["issues"]]}
        # These observations must come from live pixels; fake fixtures are never read.
        clear, changed = results["clear"], results["changed_number"]
        def first_quantity(candidate):
            return candidate["rows"][0]["quantity"] if candidate["rows"] else None

        checks = {
            "clear": len(clear["rows"]) == 2 and first_quantity(clear) in {"2.50", "2.5"}
                     and clear["rows"][0]["material_name"].lower() == "nylon"
                     and clear["rows"][0]["specification"] == "600D"
                     and clear["rows"][0]["unit"] == "m"
                     and clear["rows"][0]["unit_price"] in {"12.00", "12.0", "12"}
                     and clear["rows"][0]["subtotal"] in {"30.00", "30.0", "30"}
                     and clear["rows"][0]["currency"] == "CNY"
                     and clear["table_total"] in {"36.00", "36.0", "36"}
                     and not clear["validation"]["has_questions"],
            "changed_number": len(changed["rows"]) == 2 and first_quantity(changed) in {"3.50", "3.5"}
                              and first_quantity(clear) != first_quantity(changed)
                              and changed["table_total"] in {"48.00", "48.0", "48"}
                              and not changed["validation"]["has_questions"],
            "missing_price": len(results["missing_price"]["rows"]) == 2 and
                             results["missing_price"]["rows"][0]["unit_price"] is None and
                             results["missing_price"]["rows"][0]["subtotal"] is None,
            "blurry_digit": any(i["field"] == "quantity" and i["code"] in {"missing_field", "uncertain_value"}
                                for i in results["blurry_digit"]["issues"]),
            "total_conflict": "table_total_mismatch" in report["cases"]["total_conflict"]["issues"],
        }
        report["checks"] = checks
        report["real_vision_acceptance"] = "passed" if all(checks.values()) else "failed"
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if all(checks.values()) else 1
    except (AdapterError, InputError) as exc:
        report.update(status="blocked", code=str(exc))
        print(json.dumps(report))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
