"""One-time helper to obtain a Spotify refresh token.

Usage:
    1. Create an app at https://developer.spotify.com/dashboard
    2. Add this redirect URI to the app settings (must match exactly):
           http://127.0.0.1:8888/callback
    3. Put SPOTIFY_CLIENT_ID / SPOTIFY_CLIENT_SECRET in your .env
    4. Run:  python scripts/spotify_auth.py
    5. A browser opens; log in & approve. You'll be redirected to a
       127.0.0.1 URL. This script captures it automatically and prints
       the refresh token to paste into .env as SPOTIFY_REFRESH_TOKEN.

Scopes requested cover now-playing + transport controls.
"""
import base64
import http.server
import os
import sys
import urllib.parse
import webbrowser
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

CLIENT_ID = os.environ.get("SPOTIFY_CLIENT_ID", "").strip()
CLIENT_SECRET = os.environ.get("SPOTIFY_CLIENT_SECRET", "").strip()
REDIRECT_URI = os.environ.get("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8888/callback").strip()
SCOPES = "user-read-playback-state user-modify-playback-state user-read-currently-playing"

AUTH_CODE = {}


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        query = urllib.parse.urlparse(self.path).query
        params = urllib.parse.parse_qs(query)
        AUTH_CODE["code"] = params.get("code", [None])[0]
        AUTH_CODE["error"] = params.get("error", [None])[0]
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(b"<h1>Done. You can close this tab and return to the terminal.</h1>")

    def log_message(self, *args):
        pass  # silence default logging


def main():
    if not CLIENT_ID or not CLIENT_SECRET:
        print("ERROR: set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET in .env first.")
        sys.exit(1)

    auth_url = "https://accounts.spotify.com/authorize?" + urllib.parse.urlencode(
        {
            "client_id": CLIENT_ID,
            "response_type": "code",
            "redirect_uri": REDIRECT_URI,
            "scope": SCOPES,
        }
    )

    parsed = urllib.parse.urlparse(REDIRECT_URI)
    host, port = parsed.hostname, parsed.port or 8888

    print("Opening browser to authorize...")
    print(f"If it doesn't open, visit:\n{auth_url}\n")
    webbrowser.open(auth_url)

    server = http.server.HTTPServer((host, port), Handler)
    server.handle_request()  # serve exactly one request (the redirect)

    if AUTH_CODE.get("error"):
        print(f"Authorization failed: {AUTH_CODE['error']}")
        sys.exit(1)
    code = AUTH_CODE.get("code")
    if not code:
        print("No authorization code received.")
        sys.exit(1)

    auth = base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()
    resp = requests.post(
        "https://accounts.spotify.com/api/token",
        headers={"Authorization": f"Basic {auth}"},
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI,
        },
        timeout=15,
    )
    resp.raise_for_status()
    refresh_token = resp.json().get("refresh_token")

    print("\n" + "=" * 60)
    print("SUCCESS. Add this line to your .env:\n")
    print(f"SPOTIFY_REFRESH_TOKEN={refresh_token}")
    print("=" * 60)


if __name__ == "__main__":
    main()
