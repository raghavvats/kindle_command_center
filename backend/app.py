"""Flask app: serves the Kindle dashboard and the JSON API.

The HTML is server-rendered so the Kindle's limited e-ink browser only
ever does full-page loads (no fragile AJAX). Controls use POST -> redirect
-> GET so a button press results in a clean reload.
"""
import hashlib
import json
import time

from flask import (
    Flask,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)

from .config import load_env, load_layout
from .integrations import build_integrations

app = Flask(__name__)

ENV = load_env()
LAYOUT = load_layout()
# Per-card TTL overrides from config (falls back to the global cache_ttl).
_TTLS = {c["type"]: int(c["ttl"]) for c in LAYOUT["cards"] if "ttl" in c}
INTEGRATIONS = build_integrations(ENV, _TTLS, LAYOUT["cache_ttl"])

# Set when the dashboard Exit button is tapped; the KUAL launcher polls this.
_kindle_exit_at = 0.0

# The Kindle's battery, pushed by the KUAL launcher (the laptop serving this
# page can't see the Kindle's hardware). Rendered in the topbar so it shows in
# the dashboard's own rotated orientation - unlike an eips overlay, which would
# draw sideways in landscape.
_kindle_battery = {"level": None, "charging": False, "at": 0.0}
# Mark the reading stale if the launcher hasn't pushed in this long (it pushes
# about once a minute), so a dead/old value is visibly flagged rather than lying.
_BATTERY_STALE_SECONDS = 600


def _battery_view():
    """Current battery as a template/JSON dict, or None if never reported."""
    level = _kindle_battery["level"]
    if level is None:
        return None
    return {
        "level": level,
        "charging": bool(_kindle_battery["charging"]),
        "stale": (time.time() - _kindle_battery["at"]) > _BATTERY_STALE_SECONDS,
    }


def _card_signature(data):
    """Stable hash of a card's meaningful data (ignores fetch timestamps).

    Used for change detection so the browser only re-renders cards whose
    content actually changed - important for low e-ink refresh.
    """
    payload = {k: v for k, v in data.items() if k not in ("updated", "updated_str")}
    blob = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.md5(blob.encode("utf-8")).hexdigest()[:12]


def _build_card(card, refresh=None):
    """Fetch one card's data and wrap it with display metadata + version."""
    ctype = card["type"]
    integ = INTEGRATIONS.get(ctype)
    if integ is None:
        return None
    force = refresh == "all" or refresh == ctype
    data = integ.fetch(force=force)
    return {
        "type": ctype,
        "title": card.get("title", ctype.title()),
        "config": card,
        "data": data,
        "status": integ.status(),
        "version": _card_signature(data),
    }


def _cards_for_preset(preset):
    """Return the card configs to show, filtered/ordered by a preset.

    No preset (or an unknown one) falls back to every enabled card in
    config order. A known preset shows only its cards, in its listed order.
    """
    if not preset or preset == "all":
        return LAYOUT["cards"]
    spec = LAYOUT["presets"].get(preset)
    if not spec:
        return LAYOUT["cards"]
    by_type = {c["type"]: c for c in LAYOUT["cards"]}
    return [by_type[t] for t in spec.get("cards", []) if t in by_type]


def _gather_cards(refresh=None, preset=None):
    """Fetch data for the visible cards, honoring manual refresh + preset."""
    cards = []
    for card in _cards_for_preset(preset):
        built = _build_card(card, refresh=refresh)
        if built is not None:
            cards.append(built)
    return cards


def _no_cache(resp):
    """Stop the Kindle browser from caching polling responses."""
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp


@app.route("/")
def dashboard():
    refresh = request.args.get("refresh")
    preset = request.args.get("preset")
    if preset and preset not in LAYOUT["presets"]:
        preset = None
    cards = _gather_cards(refresh=refresh, preset=preset)
    html = render_template(
        "dashboard.html",
        title=LAYOUT["title"],
        orientation=LAYOUT["orientation"],
        columns=LAYOUT["columns"],
        cards=cards,
        presets=LAYOUT["presets"],
        active_preset=preset,
        auto_refresh=LAYOUT["auto_refresh"],
        poll_seconds=LAYOUT["poll_seconds"],
        full_refresh_minutes=LAYOUT["full_refresh_minutes"],
        battery=_battery_view(),
    )
    # No-cache so the Kindle's mesquite browser never serves a stale page
    # (e.g. an old portrait render or a previous preset) on relaunch.
    return _no_cache(app.make_response(html))


@app.route("/card/<card_type>")
def card_fragment(card_type):
    """Render a single card's HTML (for in-place auto-refresh updates)."""
    card_cfg = next((c for c in LAYOUT["cards"] if c["type"] == card_type), None)
    if card_cfg is None:
        return "unknown card", 404
    refresh = request.args.get("refresh")
    built = _build_card(card_cfg, refresh=refresh)
    html = render_template("_card.html", card=built)
    return _no_cache(app.make_response(html))


@app.route("/api/state")
def api_state():
    """Lightweight change-detection: per-card version hashes."""
    versions = {}
    for card in LAYOUT["cards"]:
        built = _build_card(card)
        if built is not None:
            versions[built["type"]] = built["version"]
    return _no_cache(jsonify({"versions": versions, "battery": _battery_view()}))


# ----- controls ----------------------------------------------------------
def _action_response(card_type):
    """Respond to a control POST.

    The page swaps just the affected card over XHR, so for those requests we
    return an empty 204 (no navigation -> the active preset and the landscape
    rotation are preserved). For a no-JS fallback we redirect back to the
    referring page so a button press still never bounces the user to "All".
    """
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return _no_cache(app.make_response(("", 204)))
    target = request.referrer or url_for("dashboard", refresh=card_type)
    return redirect(target)


@app.route("/action/spotify", methods=["POST"])
def spotify_action():
    action = request.form.get("action", "")
    INTEGRATIONS["spotify"].do_action(action)
    return _action_response("spotify")


@app.route("/action/todoist", methods=["POST"])
def todoist_action():
    action = request.form.get("action", "")
    task_id = request.form.get("task", "")
    if action == "complete":
        INTEGRATIONS["todoist"].complete_task(task_id)
    return _action_response("todoist")


@app.route("/action/hue", methods=["POST"])
def hue_action():
    light_id = request.form.get("light", "")
    action = request.form.get("action", "toggle")
    INTEGRATIONS["hue"].do_action(light_id, action)
    return _action_response("hue")


# ----- JSON API (handy for debugging / future clients) -------------------
@app.route("/api/<card_type>")
def api_card(card_type):
    integ = INTEGRATIONS.get(card_type)
    if integ is None:
        return jsonify({"error": "unknown card"}), 404
    force = request.args.get("refresh") is not None
    return jsonify(integ.fetch(force=force))


@app.route("/healthz")
def healthz():
    return jsonify({"ok": True, "cards": [c["type"] for c in LAYOUT["cards"]]})


# ----- Kindle fullscreen exit (fullmesquite launcher polls this) ----------
@app.route("/kindle-exit")
def kindle_exit():
    """Exit button target. window.close() does not work in mesquite fullscreen."""
    global _kindle_exit_at
    _kindle_exit_at = time.time()
    return render_template("kindle_exit.html")


@app.route("/api/kindle-exit/reset")
def kindle_exit_reset():
    global _kindle_exit_at
    _kindle_exit_at = 0.0
    return jsonify({"ok": True})


@app.route("/api/kindle-exit/poll")
def kindle_exit_poll():
    global _kindle_exit_at
    if _kindle_exit_at and (time.time() - _kindle_exit_at) < 60:
        _kindle_exit_at = 0.0
        return jsonify({"exit": True})
    return jsonify({"exit": False})


@app.route("/api/kindle-battery", methods=["GET", "POST"])
def kindle_battery():
    """The KUAL launcher reads this Kindle's battery (via lipc) and pushes it
    here; we render it in the topbar. Accepts `level` (0-100) and optional
    `charging` (1/true) from either the query string or a form body."""
    raw = request.values.get("level")
    try:
        level = int(float(raw))
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "missing or invalid level"}), 400
    level = max(0, min(100, level))
    charging = str(request.values.get("charging", "")).lower() in (
        "1", "true", "yes", "on",
    )
    _kindle_battery["level"] = level
    _kindle_battery["charging"] = charging
    _kindle_battery["at"] = time.time()
    return _no_cache(jsonify({"ok": True, "level": level, "charging": charging}))
