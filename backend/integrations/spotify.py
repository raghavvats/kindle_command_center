"""Spotify integration: now playing + basic transport controls.

Uses the Authorization Code flow with a stored refresh token, so the
backend can act on your account headlessly.
Needs: SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, SPOTIFY_REFRESH_TOKEN
Get the refresh token with: python scripts/spotify_auth.py

Note on lyrics: the official Web API does NOT expose lyrics. The
`get_lyrics` hook is left as a stub; see README for options.
"""
import base64
import time

import requests

from .base import Integration

TOKEN_URL = "https://accounts.spotify.com/api/token"
API_BASE = "https://api.spotify.com/v1"


class SpotifyIntegration(Integration):
    name = "spotify"

    def __init__(self, env, cache_ttl=300):
        # Now-playing changes fast; keep its cache short regardless of global TTL.
        super().__init__(env, cache_ttl=min(cache_ttl, 15))
        self.client_id = env.get("SPOTIFY_CLIENT_ID", "").strip()
        self.client_secret = env.get("SPOTIFY_CLIENT_SECRET", "").strip()
        self.refresh_token = env.get("SPOTIFY_REFRESH_TOKEN", "").strip()
        self._access_token = None
        self._token_expiry = 0.0

    def is_configured(self):
        return bool(self.client_id and self.client_secret and self.refresh_token)

    # ----- auth -----------------------------------------------------------
    def _get_access_token(self):
        if self._access_token and time.time() < self._token_expiry - 30:
            return self._access_token

        auth = base64.b64encode(
            f"{self.client_id}:{self.client_secret}".encode()
        ).decode()
        resp = requests.post(
            TOKEN_URL,
            headers={"Authorization": f"Basic {auth}"},
            data={"grant_type": "refresh_token", "refresh_token": self.refresh_token},
            timeout=10,
        )
        resp.raise_for_status()
        payload = resp.json()
        self._access_token = payload["access_token"]
        self._token_expiry = time.time() + payload.get("expires_in", 3600)
        return self._access_token

    def _headers(self):
        return {"Authorization": f"Bearer {self._get_access_token()}"}

    # ----- read -----------------------------------------------------------
    def fetch_real(self):
        resp = requests.get(
            f"{API_BASE}/me/player/currently-playing",
            headers=self._headers(),
            timeout=10,
        )
        if resp.status_code == 204 or not resp.content:
            return {"playing": False, "track": None}

        resp.raise_for_status()
        data = resp.json()
        item = data.get("item") or {}
        return {
            "playing": data.get("is_playing", False),
            "track": item.get("name", ""),
            "artist": ", ".join(a["name"] for a in item.get("artists", [])),
            "album": (item.get("album") or {}).get("name", ""),
        }

    def mock(self):
        return {
            "playing": True,
            "track": "Configure Spotify in .env",
            "artist": "Kindle Command Center",
            "album": "Run scripts/spotify_auth.py",
        }

    # ----- write / controls ----------------------------------------------
    def do_action(self, action: str):
        """Execute a transport control. No-op when not configured."""
        if not self.is_configured():
            return False, "Spotify not configured"

        try:
            headers = self._headers()
            if action == "play":
                requests.put(f"{API_BASE}/me/player/play", headers=headers, timeout=10)
            elif action == "pause":
                requests.put(f"{API_BASE}/me/player/pause", headers=headers, timeout=10)
            elif action == "next":
                requests.post(f"{API_BASE}/me/player/next", headers=headers, timeout=10)
            elif action == "previous":
                requests.post(f"{API_BASE}/me/player/previous", headers=headers, timeout=10)
            else:
                return False, f"Unknown action: {action}"
        except Exception as exc:
            return False, str(exc)

        # Bust the cache so the UI reflects the new state on next render.
        self._cache = None
        return True, "ok"

    def get_lyrics(self):
        """Stub. Official API has no lyrics endpoint. See README."""
        return None
