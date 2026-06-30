# Kindle Command Center

An e-ink home dashboard for a jailbroken Kindle. The backend runs on your
laptop; the Kindle opens the page over the local network via KUAL.

Cards: Todoist, Calendar (ICS), Weather (Open-Meteo), Spotify, Hue.

Runs with mock data out of the box — no keys needed to see the dashboard.
Add credentials to make each card live.

## Run (laptop)

```bash
./run.sh            # creates .venv, installs deps, starts server
```

Or manually:

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
python run.py
```

Then visit `http://<laptop-ip>:8000`. Find your IP with `ipconfig getifaddr en0` (macOS).

## KUAL launcher (Kindle)

1. Copy `kual/extensions/commandcenter/` into your Kindle's `extensions/`
   folder (usually `/mnt/us/extensions/`).
2. Copy `url.txt.example` to `url.txt` and set it to your laptop's IP,
   e.g. `http://192.168.1.100:8000`. (`url.txt` is git-ignored.)
3. Open KUAL → Kindle Command Center.

`launch.sh` stops the Kindle GUI, opens the mesquite browser fullscreen at
the URL, and restores the GUI when you tap Exit on the dashboard. It checks
the server is reachable before stopping the GUI, disables the screensaver
while running, and writes `launch.log` each run.

The launcher reads the Kindle battery on-device and pushes it to the server
(~once a minute) so it shows in the top bar.

To exit: tap Exit on the dashboard. If stuck, short-press the power button.

## Configuration

- Layout → `config/config.yaml` (reorder/toggle cards, set columns, titles).
- Secrets → copy `.env.example` to `.env` and fill in what you have.

Auto-refresh keys in `config.yaml`:

- `dashboard.poll_seconds` — how often the browser checks for changes (default 15).
- `dashboard.full_refresh_minutes` — full page reload to clear e-ink ghosting (default 30; `0` disables).
- per-card `ttl` — how often that card actually re-fetches from its service.

The browser polls `/api/state` for per-card hashes and swaps only the cards
that changed, so the e-ink screen doesn't fully flash on every update.

## Per-card setup

See `.env.example` for exact variable names.

- **Weather** — works now. Set `WEATHER_LAT` / `WEATHER_LON` (defaults to NYC).
- **Todoist** — set `TODOIST_API_TOKEN` (Todoist → Settings → Integrations → Developer).
- **Calendar** — set `CALENDAR_ICS_URL` (Google Calendar → Settings → "Secret address in iCal format").
- **Spotify** — create an app at <https://developer.spotify.com/dashboard>, add
  redirect URI `http://127.0.0.1:8888/callback`, set `SPOTIFY_CLIENT_ID` /
  `SPOTIFY_CLIENT_SECRET`, then run `python scripts/spotify_auth.py` and paste
  the printed `SPOTIFY_REFRESH_TOKEN` into `.env`. Controls need an active
  device (Premium).
- **Hue** — placeholder; toggles are in-memory only.

## Architecture

```
run.py                  # start the server
backend/
  app.py                # Flask routes (HTML + JSON API + controls)
  config.py             # loads config.yaml + .env
  integrations/         # one module per card (base.py handles cache + mock)
  templates/            # base + dashboard + cards/*.html
  static/css/eink.css
config/config.yaml      # dashboard layout
kual/extensions/commandcenter/   # KUAL launcher
```

Each integration subclasses `Integration` and implements `is_configured()`,
`fetch_real()`, and `mock()`. The base class handles TTL caching and mock
fallback so a broken service can't take down the page. To add a card: add a
module in `integrations/`, register it in `integrations/__init__.py`, add a
`cards/<type>.html` partial, and list it in `config.yaml`.

## API

- `GET /` — dashboard
- `GET /api/<card>` — JSON for one card (`?refresh` forces fresh fetch)
- `GET /api/state` — per-card version hashes
- `GET /card/<type>` — rendered HTML for one card
- `GET|POST /api/kindle-battery?level=<0-100>&charging=<0|1>` — battery push
- `GET /healthz` — liveness + enabled cards
