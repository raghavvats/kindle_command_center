"""Hue lights integration - PLACEHOLDER.

For now this renders a static set of "lights" with toggle buttons that
don't touch real hardware. The data shape and `do_action` signature are
designed so that swapping in a Home Assistant backend later (HASS_URL +
HASS_TOKEN, calling /api/services/light/turn_on etc.) requires no UI
changes.
"""
from .base import Integration


class HueIntegration(Integration):
    name = "hue"

    def __init__(self, env, cache_ttl=300):
        super().__init__(env, cache_ttl)
        self.hass_url = env.get("HASS_URL", "").strip()
        self.hass_token = env.get("HASS_TOKEN", "").strip()
        # In-memory state so toggles "stick" during a session (placeholder only).
        self._state = {
            "desk": {"name": "Desk", "on": True},
            "bedroom": {"name": "Bedroom", "on": False},
            "kitchen": {"name": "Kitchen", "on": False},
        }

    def is_configured(self):
        # Always False for now -> the card shows a "placeholder" badge.
        return bool(self.hass_url and self.hass_token)

    def fetch_real(self):
        # TODO: query Home Assistant for real light states.
        return self.mock()

    def mock(self):
        lights = [
            {"id": lid, "name": l["name"], "on": l["on"]}
            for lid, l in self._state.items()
        ]
        return {"lights": lights, "placeholder": True}

    def do_action(self, light_id: str, action: str):
        """Toggle a placeholder light. Returns (ok, message)."""
        if light_id not in self._state:
            return False, f"Unknown light: {light_id}"
        if action == "toggle":
            self._state[light_id]["on"] = not self._state[light_id]["on"]
        elif action == "on":
            self._state[light_id]["on"] = True
        elif action == "off":
            self._state[light_id]["on"] = False
        else:
            return False, f"Unknown action: {action}"
        self._cache = None
        return True, "ok"
