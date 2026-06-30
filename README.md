# Kindle Command Center

A local, e-ink-friendly home dashboard for a **jailbroken Kindle**. The
backend runs on your laptop on the local network; the Kindle just opens
the page (launched from **KUAL**).

Cards: **Todoist**, **Calendar** (ICS), **Weather** (Open-Meteo),
**Spotify** (now playing + controls), and a **Hue placeholder**.

> Everything runs with **mock data out of the box** — no API keys needed
> to see the dashboard. Add credentials later to make each card live.

---

## Design goals (and how they're met)

| Goal | How |
| --- | --- |
| Big buttons / text | Large serif type, 56–72px tap targets (`eink.css`) |
| Grayscale / e-ink | Pure black-on-white, heavy borders, no gradients |
| Minimal animations | No CSS transitions; only changed cards repaint |
| Manual refresh | Per-card `↻` button + "Refresh All" |
| Auto-refresh | Change-detection polling updates only cards that changed |
| Configurable layout | Edit `config/config.yaml` (order, columns, enable) |
| Integration/UI separation | `backend/integrations/*` ↔ templates via a registry |
| Local-first | Mock fallbacks, no key needs Open-Meteo/ICS |
| Launch from KUAL | `kual/extensions/commandcenter/` |

---

## Architecture

```
run.py                      # start the server (python run.py)
backend/
  app.py                    # Flask routes (HTML + JSON API + controls)
  config.py                 # loads config.yaml + .env
  integrations/
    base.py                 # caching, mock fallback, error capture
    todoist.py calendar.py spotify.py weather.py hue.py
  templates/
    base.html dashboard.html
    cards/*.html            # one partial per card type
  static/css/eink.css
config/config.yaml          # dashboard layout
.env.example                # all secrets, documented
scripts/spotify_auth.py     # one-time Spotify refresh-token helper
kual/extensions/commandcenter/  # KUAL launcher
```

Each integration subclasses `Integration` and implements
`is_configured()`, `fetch_real()`, and `mock()`. The base class handles
TTL caching, manual force-refresh, and falling back to mock data so one
broken service can never take down the page. To add a new card: drop a
module in `integrations/`, register it in `integrations/__init__.py`, add
a `cards/<type>.html` partial, and list it in `config.yaml`.

---

## Run it (laptop)

```bash
./run.sh            # creates .venv, installs deps, starts server
# or manually:
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
python run.py
```

Then visit `http://<laptop-ip>:8000` from any device. Find your IP with
`ipconfig getifaddr en0` (macOS).

---

## KUAL launcher (Kindle)

1. Copy `kual/extensions/commandcenter/` into the `extensions/` folder of
   your Kindle's KUAL install (usually `/mnt/us/extensions/`).
2. Copy `commandcenter/url.txt.example` to `commandcenter/url.txt` and set it
   to your laptop's IP, e.g. `http://192.168.1.100:8000`. (`url.txt` is
   git-ignored so your local IP never gets committed.)
3. Open **KUAL** → **Kindle Command Center**.

`launch.sh` uses the **fullmesquite** approach (by slyhype): stops the
Kindle GUI, opens the experimental mesquite browser fullscreen, navigates
to the URL in `url.txt` via `gotoURL`, and waits for the dashboard **Exit**
button to restore the GUI. During startup it shows on-screen status
messages (via `eips`): "Connecting to Wi-Fi…", "Checking server…",
"Loading dashboard…", so you get feedback instead of a frozen KUAL screen.
If the server is unreachable it shows an error and returns to the Kindle UI.

**How to exit:** tap **Exit** on the dashboard (top bar). Exit works via a
signal to the laptop: the launcher polls the server while the browser is
open (`window.close()` does not work in mesquite fullscreen). The GUI
restarts automatically (you may briefly see "Please wait while UI is reset").

The launcher checks the dashboard is reachable *before* stopping the GUI,
so a down server won't trap you on a blank screen. A log is written to
`launch.log` on each run.

**Battery %:** the dashboard runs on your laptop, which can't see the
Kindle's battery, so the launcher reads it on-device (`lipc`) and pushes it
to the server about once a minute. It shows in the top bar (e.g. `87%`,
`+` = charging, `?` = the reading went stale). It's rendered as part of the
rotated HTML page, so it appears in the **correct orientation** — unlike an
`eips` overlay, which would draw sideways in landscape.

**Screen / battery health:** E-ink holds a static image with ~zero power and
has **no** OLED-style burn-in, so the launcher disables the Kindle's
screensaver/suspend (`preventScreenSaver`) to keep the dashboard up, and
restores it on exit. *Ghosting* (faint residue from the partial card
repaints) is handled separately by the dashboard doing a periodic full-page
reload — a full flashing e-ink refresh that clears it. Tune via
`config.yaml` → `dashboard.full_refresh_minutes` (default 30; `0` disables).

### Troubleshooting the launcher

- **Returns straight to KUAL:** read `launch.log` — usually "not reachable"
  (server down or wrong IP in `url.txt`).
- **Browser opens but wrong page:** confirm `url.txt` and that the URL works
  manually in the experimental browser first.
- **Stuck in browser:** short-press the power button to exit.

---

## Configuration

- **Layout** → `config/config.yaml` (add/remove/reorder cards, set
  `columns`, rename titles, toggle `enabled`).
- **Secrets** → copy `.env.example` to `.env` and fill in what you have.

### Auto-refresh

The dashboard quietly polls the server and updates **only the cards whose
data actually changed**, so a song change repaints just the Now Playing
card and the rest of the e-ink screen stays still (no full-page flashing).

Controlled in `config/config.yaml`:

- `dashboard.auto_refresh` — `true`/`false` to enable the feature.
- `dashboard.poll_seconds` — how often the browser checks for changes (default 15).
- `dashboard.full_refresh_minutes` — how often the page does a full reload to
  clear e-ink ghosting from the partial updates (default 30; `0` disables).
- per-card `ttl` — how often that card's data is actually re-fetched from
  its service (e.g. `weather: 1800`, `spotify: 15`, `todoist: 120`). The
  poll only *notices* changes; `ttl` controls how often external APIs are
  hit, so a small `poll_seconds` does not hammer them.

How it works: the browser polls `/api/state` for per-card version hashes
(computed from each card's content, ignoring timestamps). When a hash
changes it fetches just that card's HTML from `/card/<type>` and swaps it
in place. Plain ES5 + `XMLHttpRequest` for the old Kindle WebKit; if JS is
unavailable the manual refresh buttons still work.

---

## What I need from you to make each card live

Build is done. Here's the setup required per integration (see
`.env.example` for the exact variable names):

### ✅ Weather — works now, no key
Just set `WEATHER_LAT` / `WEATHER_LON` (defaults to NYC). Uses Open-Meteo.

### Todoist
- Get a token: Todoist → Settings → Integrations → Developer → "API token".
- Set `TODOIST_API_TOKEN`.

### Calendar (ICS)
- Notion Calendar / Google Calendar both expose a private `.ics` URL.
  - Google Calendar → Settings → your calendar → **Secret address in
    iCal format**.
- Set `CALENDAR_ICS_URL`.

### Spotify (now playing + controls)
- Create an app at <https://developer.spotify.com/dashboard>.
- Add redirect URI `http://127.0.0.1:8888/callback` to the app.
- Put `SPOTIFY_CLIENT_ID` / `SPOTIFY_CLIENT_SECRET` in `.env`.
- Run `python scripts/spotify_auth.py`, approve in browser, paste the
  printed `SPOTIFY_REFRESH_TOKEN` into `.env`.
- **Controls require an active Spotify device** (Premium; have the app
  open somewhere).
- **Lyrics**: the official API has **no lyrics endpoint**. Left disabled
  (`show_lyrics: false`). Options later: an unofficial lyrics source, or
  a synced-lyrics provider — your call, since these are unofficial.

### Hue — placeholder for now
- Renders fake lights with working toggle buttons (in-memory only).
- Later (back at college): set `HASS_URL` / `HASS_TOKEN` and we'll wire
  `hue.py` to Home Assistant's `light.turn_on` / `turn_off` services.

---

## Local API (handy for debugging)

- `GET /` — the dashboard
- `GET /api/<card>` — JSON for one card (`?refresh` forces fresh fetch)
- `GET /api/state` — per-card version hashes (used by auto-refresh)
- `GET /card/<type>` — rendered HTML for one card (used by auto-refresh)
- `GET|POST /api/kindle-battery?level=<0-100>&charging=<0|1>` — the launcher
  pushes the Kindle's battery here; shown in the top bar
- `GET /healthz` — liveness + enabled cards
