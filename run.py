"""Entry point: start the Kindle Command Center server.

    python run.py

Binds to HOST/PORT from .env (defaults 0.0.0.0:8000) so the Kindle can
reach it over the local network.
"""
import os

from backend.app import app

if __name__ == "__main__":
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8000"))
    # threaded=True so a slow integration fetch doesn't block other requests.
    app.run(host=host, port=port, threaded=True, debug=False)
