"""Configuration loading: dashboard layout (YAML) + secrets (.env).

Keeping config loading isolated here means the rest of the app never
touches os.environ or the YAML file directly.
"""
import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config" / "config.yaml"
ENV_PATH = ROOT / ".env"


def load_env():
    """Load .env into os.environ (if present) and return a dict view."""
    if ENV_PATH.exists():
        load_dotenv(ENV_PATH)
    return dict(os.environ)


def load_layout():
    """Load the dashboard layout / card configuration."""
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"Missing config file: {CONFIG_PATH}")
    with open(CONFIG_PATH, "r") as f:
        data = yaml.safe_load(f) or {}

    dashboard = data.get("dashboard", {})
    cards = [c for c in data.get("cards", []) if c.get("enabled", True)]
    return {
        "title": dashboard.get("title", "Command Center"),
        "orientation": str(dashboard.get("orientation", "portrait")).lower(),
        "columns": int(dashboard.get("columns", 2)),
        "cache_ttl": int(dashboard.get("cache_ttl", 300)),
        "auto_refresh": bool(dashboard.get("auto_refresh", True)),
        "poll_seconds": int(dashboard.get("poll_seconds", 15)),
        # Periodic full-page reload (minutes) that forces a full e-ink
        # repaint to clear ghosting from partial card updates. 0 disables.
        "full_refresh_minutes": int(dashboard.get("full_refresh_minutes", 30)),
        "presets": dashboard.get("presets") or {},
        "cards": cards,
    }
