"""Ordinary backend-callable mock entry; no Agent, Worker or model configuration."""
from __future__ import annotations

import json
from typing import Mapping

from demo_mock import Catalog

from .core import recognize


class _FixtureAdapter:
    name = "mock-fixture-replay"

    def __init__(self, data):
        self._text = json.dumps(data, ensure_ascii=False, allow_nan=False)

    def extract(self, image: bytes, mime_type: str) -> str:
        return self._text


def mock_recognize(image: bytes, file_ref: Mapping, *, catalog: Catalog) -> dict:
    """Hash-match first, then reuse original candidate parsing/provenance/validation.

    file_ref is bound at runtime, outside fixture matching, to avoid stale Case or
    asset references. Caller authorizes and reads that exact version beforehand.
    """
    replay = catalog.replay("bom", "extract", {"image": image})
    result = recognize(image, file_ref, _FixtureAdapter(replay["data"]))
    result.update(mode="mock", mock=replay["mock"])
    return result
