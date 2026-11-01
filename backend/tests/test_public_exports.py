from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import pytest

from app.db import SessionLocal
from app.exports import export_artifact
from app.models import Blob, Case, Item
from app.workbench import append_artifact


@pytest.mark.parametrize("kind", ["quotation", "order"])
@pytest.mark.parametrize("fmt", ["docx", "xlsx", "pdf"])
def test_customer_exports_are_rebuilt_from_public_fields(client, kind, fmt):
    public = {"product": "Canvas bag", "quantity": 200, "unitPriceUsd": "13.13", "totalUsd": "2626.00"}
    private = {"margin": "PRIVATE_MARGIN", "supplier": "PRIVATE_FACTORY", "internalNotes": "PRIVATE_NOTE",
               "costVersionId": "PRIVATE_COST", "hidden": {"secret": "PRIVATE_NESTED"}}
    content = {**public, **private} if kind == "quotation" else {"pi": {**public, **private}, "po": private, "diff": [private]}
    with SessionLocal() as db:
        case = db.get(Case, "inq_demo_bag")
        artifact = append_artifact(db, case, kind, content)
        exported = export_artifact(db, case, db.get(Item, artifact["itemId"]), fmt)
        data = Path(db.get(Blob, exported["blobId"]).path).read_bytes()
        assert exported["audience"] == "customer"
    if fmt == "pdf":
        from pypdf import PdfReader
        text = "\n".join(page.extract_text() for page in PdfReader(BytesIO(data)).pages)
    else:
        with ZipFile(BytesIO(data)) as archive:
            text = "\n".join(archive.read(name).decode("utf-8") for name in archive.namelist() if name.endswith(".xml"))
            assert not any("comment" in name.lower() or "externalLink" in name for name in archive.namelist())
    assert "2626.00" in text and "13.13" in text
    assert "PRIVATE_" not in text
    assert "margin" not in text and "costVersionId" not in text
