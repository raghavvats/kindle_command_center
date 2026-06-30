#!/bin/sh
# Kindle Command Center launcher (fullscreen mesquite browser).
# Based on slyhype's fullmesquite KUAL extension.
#
# Flow: show status -> stop GUI -> connect -> open browser -> gotoURL ->
# wait for the dashboard Exit button -> restart GUI.
#
# URL is read from ../url.txt. Log: ../launch.log

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
EXTDIR="$(cd "$SCRIPT_DIR/.." && pwd)"
LOG="$EXTDIR/launch.log"
exec >>"$LOG" 2>&1
echo "==== launch $(date) ===="
echo "EXTDIR=$EXTDIR"

URL="$(head -n1 "$EXTDIR/url.txt" 2>/dev/null | tr -d '[:space:]')"
[ -z "$URL" ] && URL="http://192.168.1.100:8000"
BASE_URL="${URL%/}"
echo "URL=$URL"

GO_FULLSCREEN=true

# Screen orientation while the dashboard is shown. The dashboard is laid out
# for a wide ("horizontal") screen, so we rotate the Kindle into landscape.
#   U = portrait (Kindle default)      R = landscape, clockwise
#   L = landscape, counter-clockwise   D = inverted portrait
# mesquite (the browser) honors orientationLock even though the home screen
# does not. Set to U to keep portrait. Always restored to U on exit.
ORIENTATION="R"

set_orientation() {
  [ -z "$ORIENTATION" ] && return 0
  echo "set orientation $ORIENTATION"
  lipc-set-prop com.lab126.winmgr orientationLock "$ORIENTATION" 2>/dev/null
}

# --- Keep the screen on -------------------------------------------------
# E-ink holds a static image with ~zero power draw and does NOT suffer
# OLED-style burn-in, so it is safe to leave the dashboard up indefinitely.
# Stop powerd from blanking / suspending the device while we're shown.
# Restored on exit. (Anti-ghosting is handled separately by the dashboard's
# periodic full-page refresh; see config.yaml `full_refresh_minutes`.)
prevent_screensaver() {
  echo "preventing screensaver/suspend"
  lipc-set-prop com.lab126.powerd preventScreenSaver 1 2>/dev/null
}
restore_screensaver() {
  echo "restoring screensaver/suspend"
  lipc-set-prop com.lab126.powerd preventScreenSaver 0 2>/dev/null
}

# --- Battery ------------------------------------------------------------
# The dashboard runs on the laptop, which can't see THIS Kindle's battery, so
# we read it here via lipc and push it to the backend. The backend renders it
# in the dashboard top bar -- i.e. in the page's own rotated orientation --
# instead of an eips overlay, which would draw sideways while in landscape.
# Read the charge level (0-100). The property/tool names differ across Kindle
# firmware, so try the common sources in order (same chain KOReader uses):
#   1. lipc  com.lab126.powerd battLevel   (most models; NOT battery_capacity)
#   2. gasgauge-info -c                     (gas-gauge CLI; may print "85%")
read_battery_level() {
  lvl=$(lipc-get-prop com.lab126.powerd battLevel 2>/dev/null)
  case "$lvl" in ''|*[!0-9]*) lvl="" ;; esac
  if [ -z "$lvl" ]; then
    lvl=$(gasgauge-info -c 2>/dev/null | tr -cd '0-9')
  fi
  case "$lvl" in ''|*[!0-9]*) return 1 ;; esac
  echo "$lvl"
}

push_battery() {
  level=$(read_battery_level) || { echo "battery: no reading (lipc/gasgauge), skipping"; return 0; }
  charging=$(lipc-get-prop com.lab126.powerd isCharging 2>/dev/null)
  [ "$charging" = "1" ] || charging=0
  echo "battery: ${level}% charging=${charging}"
  curl -fsS -m 3 "$BASE_URL/api/kindle-battery?level=$level&charging=$charging" \
    >/dev/null 2>&1
}

# --- On-screen status (e-ink) -------------------------------------------
# eips draws text on the framebuffer in character cells (col row "text").
STATUS_ROW=8

banner() {
  eips -c 2>/dev/null
  eips 2 6 "Kindle Command Center" 2>/dev/null
}

# Update a single status line, padded to erase the previous (longer) text.
say() {
  echo "STATUS: $1"
  eips 2 "$STATUS_ROW" "                                                  " 2>/dev/null
  eips 2 "$STATUS_ROW" "  $1" 2>/dev/null
}

# --- GUI stop/start (from fullmesquite / KOReader) ----------------------
if [ -d /etc/upstart ]; then
  export INIT_TYPE="upstart"
  [ -f /etc/upstart/functions ] && . /etc/upstart/functions
else
  export INIT_TYPE="sysv"
  [ -f /etc/rc.d/functions ] && . /etc/rc.d/functions
fi

refresh_screen() {
  eips -c 2>/dev/null
  eips -c 2>/dev/null
}

stop_gui() {
  if [ "$GO_FULLSCREEN" = true ]; then
    echo "stopping gui"
    if [ "${INIT_TYPE}" = "sysv" ]; then
      /etc/init.d/framework stop
    else
      trap "" TERM
      stop lab126_gui
      usleep 1250000
      trap - TERM
    fi
    refresh_screen
  fi
}

start_gui() {
  if [ "$GO_FULLSCREEN" = true ]; then
    echo "starting gui"
    if [ "${INIT_TYPE}" = "sysv" ]; then
      cd / && /etc/init.d/framework start
    else
      cd / && start lab126_gui
      usleep 1250000
    fi
    refresh_screen
    eips 1 1 "Please wait while UI is reset" 2>/dev/null
  fi
}

# Stopping lab126_gui SIGKILLs the Kindle home/reader app (KPPMainAppV2).
# The firmware's crash-recovery daemon treats a KILL-signal death as a crash
# and drops a core dump + report (.tgz/.txt/.sdr) into /mnt/us/documents/,
# which then surfaces as junk "books" in the library. The dump is harmless
# (no reboot, marked a normal exit) but cosmetically annoying, and there is
# no graceful stop on this firmware that avoids it. So we just delete the
# artifacts. The glob is specific to these crash files; no real book matches.
clean_crash_reports() {
  echo "cleaning KPPMainApp crash reports from documents"
  rm -rf /mnt/us/documents/KPPMainAppV2_*_crash_* 2>/dev/null
}

reachable() {
  if command -v curl >/dev/null 2>&1; then
    curl -fsS -m 8 -o /dev/null "$1"
  elif command -v wget >/dev/null 2>&1; then
    wget -q -T 8 -O /dev/null "$1"
  else
    return 0
  fi
}

# --- 0. Clear any crash reports left in the library by previous runs ----
# (Their dumps are fully written by now, so this reliably catches them.)
clean_crash_reports

# --- 1. Immediate feedback while the GUI is still up --------------------
eips 2 6 "  Kindle Command Center starting..." 2>/dev/null

# --- 2. Enable Wi-Fi ----------------------------------------------------
lipc-set-prop com.lab126.wifid enable 1 2>/dev/null
lipc-set-prop com.lab126.cmd wirelessEnable 1 2>/dev/null

# --- 3. Take over the screen so status messages are clearly visible -----
stop_gui
banner
say "Connecting to Wi-Fi..."
sleep 3

# --- 4. Check the dashboard is reachable --------------------------------
say "Checking server at"
eips 2 "$((STATUS_ROW + 2))" "  $BASE_URL" 2>/dev/null

if ! reachable "$URL"; then
  echo "ERROR: $URL not reachable"
  say "Server not reachable."
  eips 2 "$((STATUS_ROW + 2))" "  Is the laptop on and run.py started?" 2>/dev/null
  eips 2 "$((STATUS_ROW + 4))" "  Returning to Kindle..." 2>/dev/null
  sleep 5
  start_gui
  clean_crash_reports
  echo "done (unreachable)"
  exit 0
fi
echo "URL reachable"
say "Loading dashboard..."

# Keep the dashboard visible: stop the device from auto-suspending while up.
prevent_screensaver

# --- 5. Launch mesquite browser and navigate ----------------------------
# The browser restores its last page on start. If the previous session
# ended on the exit page, we must force it back to the dashboard and beat
# the session-restore, so we send gotoURL several times while it settles.
unset LD_LIBRARY_PATH

echo "starting browser"
lipc-set-prop com.lab126.appmgrd start app://com.lab126.browser
sleep 3

# Rotate into landscape. Reassert on each gotoURL since the browser can
# reset orientation while it settles / restores its previous session.
set_orientation

i=0
while [ $i -lt 4 ]; do
  lipc-set-prop com.lab126.browser gotoURL "$URL" 2>/dev/null \
    || lipc-set-prop -s com.lab126.browser gotoURL "$URL" 2>/dev/null
  set_orientation
  i=$((i + 1))
  sleep 1
done
echo "gotoURL sent (x$i)"

# CRITICAL: clear the exit flag AFTER the browser has finished restoring
# and re-navigating. A restored exit page can re-arm the flag during
# startup; resetting here means we never auto-exit on relaunch.
curl -fsS -m 3 "$BASE_URL/api/kindle-exit/reset" >/dev/null 2>&1
echo "exit flag reset"

# --- 6. Wait for the dashboard Exit button ------------------------------
# Also push the battery level to the dashboard: once now, then about once a
# minute (the loop ticks ~1s, dominated by the exit poll's own latency).
echo "waiting for exit (dashboard Exit button)"
push_battery
secs=0
while true; do
  RESP=$(curl -fsS -m 2 "$BASE_URL/api/kindle-exit/poll" 2>/dev/null) || RESP=""
  case "$RESP" in
    *'"exit":true'*|*'"exit": true'*)
      echo "exit via dashboard button"
      break
      ;;
  esac
  secs=$((secs + 1))
  [ $((secs % 60)) -eq 0 ] && push_battery
  sleep 1
done

killall mesquite 2>/dev/null
# Restore portrait so the home UI comes back the right way up.
lipc-set-prop com.lab126.winmgr orientationLock U 2>/dev/null
# Re-enable normal power management now that we're handing back to the GUI.
restore_screensaver
start_gui

# Remove this session's crash report. The dump is generated during stop_gui
# at startup, so by now (after the user has exited) it's fully written. The
# startup cleanup above is the backstop in case this races on a quick exit.
clean_crash_reports

echo "done"
exit 0
