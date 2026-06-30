"""Integration registry.

Each integration is a self-contained module exposing a subclass of
`Integration`. The UI layer only ever talks to this registry, never to
the individual services - that's the "clean separation" boundary.
"""
from .todoist import TodoistIntegration
from .calendar import CalendarIntegration
from .spotify import SpotifyIntegration
from .weather import WeatherIntegration
from .hue import HueIntegration

# Map a card `type` (from config.yaml) -> integration class.
REGISTRY = {
    "todoist": TodoistIntegration,
    "calendar": CalendarIntegration,
    "spotify": SpotifyIntegration,
    "weather": WeatherIntegration,
    "hue": HueIntegration,
}


def build_integrations(env, ttls=None, default_ttl=300):
    """Instantiate one integration per registered type.

    `ttls` is an optional {card_type: seconds} map (from config.yaml).
    Types without an entry fall back to `default_ttl`.
    """
    ttls = ttls or {}
    return {
        name: cls(env, ttls.get(name, default_ttl))
        for name, cls in REGISTRY.items()
    }
