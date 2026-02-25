"""Thin helpers for reading / writing data/settings.json."""

import json
from pathlib import Path

SETTINGS_FILE = Path("data/settings.json")


def load_settings() -> dict:
    """Load settings from settings file."""
    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_settings(settings: dict) -> None:
    """Save settings to settings file."""
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(SETTINGS_FILE, "w") as f:
        json.dump(settings, f, indent=2)
