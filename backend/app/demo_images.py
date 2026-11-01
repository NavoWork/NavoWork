"""Bundled roadshow artwork. Playback never calls an image model."""
from pathlib import Path

from .core import decode

ASSET_DIR = Path(__file__).parent / "assets" / "demo-images"
PRESETS = frozenset({"de-backpack", "us-tote", "uk-duffel", "jp-cooler", "au-laptop"})


def preset_id(case):
    value = decode(case.payload).get("demoScenarioId")
    return value if value in PRESETS else None


def preset_path(key):
    # Only server-owned scenario IDs may select a local file.
    if key not in PRESETS:
        raise ValueError("Unknown demo image")
    return ASSET_DIR / f"{key}.png"
