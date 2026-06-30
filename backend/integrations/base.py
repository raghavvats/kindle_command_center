"""Base class shared by all integrations.

Responsibilities handled here so individual integrations stay tiny:
  - TTL caching (with manual force-refresh)
  - graceful fallback to mock data when not configured
  - uniform error capture so one broken service never breaks the page
"""
import time


class Integration:
    #: card type key, overridden by subclasses
    name = "base"

    def __init__(self, env, cache_ttl=300):
        self.env = env
        self.cache_ttl = cache_ttl
        self._cache = None
        self._cache_time = 0.0

    # ----- to be implemented by subclasses --------------------------------
    def is_configured(self) -> bool:
        """Return True when the required secrets/config are present."""
        return True

    def fetch_real(self) -> dict:
        """Fetch live data. Only called when is_configured() is True."""
        raise NotImplementedError

    def mock(self) -> dict:
        """Placeholder data used before the integration is configured."""
        return {}

    # ----- shared machinery -----------------------------------------------
    def fetch(self, force: bool = False) -> dict:
        now = time.time()
        fresh_enough = (
            self._cache is not None and (now - self._cache_time) < self.cache_ttl
        )
        if not force and fresh_enough:
            return self._cache

        configured = self.is_configured()
        data = {}
        try:
            data = self.fetch_real() if configured else self.mock()
            data.setdefault("error", None)
        except Exception as exc:  # never let one card crash the dashboard
            data = self.mock()
            data["error"] = str(exc)

        data["mock"] = not configured
        data["updated"] = now
        data["updated_str"] = time.strftime("%-I:%M %p", time.localtime(now))

        self._cache = data
        self._cache_time = now
        return data

    def status(self) -> str:
        return "live" if self.is_configured() else "mock"
