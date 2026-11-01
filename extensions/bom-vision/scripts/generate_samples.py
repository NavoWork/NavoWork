"""Synthetic pixel fixtures and explicitly fake transcriptions. No hidden text metadata."""
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1] / "samples"


def main():
    ROOT.mkdir(exist_ok=True)
    font = ImageFont.truetype("DejaVuSans.ttf", 22)
    fields = ["material_name", "specification", "quantity", "unit", "unit_price", "currency", "subtotal"]
    header = ["Material", "Spec", "Qty", "Unit", "Price", "CCY", "Amount"]
    positions = [25, 220, 480, 580, 680, 820, 920, 1090]
    base = [["Nylon", "600D", "2.50", "m", "12.00", "CNY", "30.00"],
            ["Zipper", "20cm", "4", "pcs", "1.50", "CNY", "6.00"]]
    manifest = {}
    for name in ("clear", "missing_price", "blurry_digit", "total_conflict", "changed_number"):
        rows = [row[:] for row in base]
        total = "36.00"
        if name == "missing_price":
            rows[0][4] = ""
            rows[0][6] = ""
        if name == "changed_number":
            rows[0][2], rows[0][6], total = "3.50", "42.00", "48.00"
        if name == "total_conflict":
            total = "39.00"
        image = Image.new("RGB", (1120, 320), "white")
        draw = ImageDraw.Draw(image)
        draw.text((25, 15), "SYNTHETIC BOM - candidate evidence only", fill="black", font=font)
        for y, values in ((65, header), (125, rows[0]), (185, rows[1])):
            for x, value in zip(positions, values):
                draw.text((x, y), value, fill="black", font=font)
        for y in (55, 110, 170, 230):
            draw.line((20, y, 1090, y), fill="gray", width=1)
        draw.text((680, 265), f"TOTAL CNY {total}", fill="black", font=font)
        notes = []
        uncertain = []
        if name == "blurry_digit":
            box = (475, 115, 560, 159)
            image.paste(image.crop(box).filter(ImageFilter.GaussianBlur(4)), box)
            rows[0][2] = None
            uncertain = ["quantity"]
            notes = ["First quantity is blurred; inspect original before accepting a digit."]
        extension = ".jpg" if name == "clear" else ".png"
        path = ROOT / (name + extension)
        image.save(path, quality=95)
        model_rows = []
        for i, values in enumerate(rows, 1):
            row = dict(zip(fields, (v or None for v in values)))
            row.update(raw_text=" | ".join(v or ("2.?0" if name == "blurry_digit" and i == 1 and j == 2 else "[blank]")
                                          for j, v in enumerate(values)),
                       source_line=i, uncertain_fields=uncertain if i == 1 else [])
            model_rows.append(row)
        response = {"raw_text": " | ".join(header) + "\n" +
                    "\n".join(row["raw_text"] for row in model_rows) + f"\nTOTAL CNY {total}",
                    "rows": model_rows, "table_total": total, "currency": "CNY", "notes": notes}
        (ROOT / (name + ".fake.json")).write_text(json.dumps(response, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        manifest[name] = {"image": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                          "fake_response": name + ".fake.json", "expected_quantity": rows[0][2],
                          "expected_total": total}
    (ROOT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
