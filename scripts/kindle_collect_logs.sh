#!/bin/sh
# Kindle log collector — run from KTerm to gather every log that's useful
# for debugging the Command Center start/stop crash reports.
#
# Usage (in KTerm on the Kindle):
#   sh /mnt/us/kindle_collect_logs.sh
#
# Then plug the Kindle into your laptop via USB and drag the whole
# `cc_logs` folder (on the Kindle drive root) into the project so I can read it.

OUT=/mnt/us/cc_logs
mkdir -p "$OUT"

echo "collecting into $OUT ..."

# --- 0. Device / firmware info -----------------------------------------
{
  echo "==== device info $(date) ===="
  cat /etc/prettyversion.txt 2>/dev/null
  cat /etc/version.txt 2>/dev/null
  cat /proc/version 2>/dev/null
  echo "model: $(lipc-get-prop com.lab126.system.userstore deviceModel 2>/dev/null)"
} > "$OUT/device_info.txt" 2>&1

# --- 1. Our launcher's own log -----------------------------------------
cp /mnt/us/extensions/commandcenter/launch.log "$OUT/launch.log" 2>/dev/null

# --- 2. System message log (where framework crashes are recorded) ------
# Copy current + any rotated/compressed older logs.
cp /var/log/messages       "$OUT/messages.log"     2>/dev/null
cp /var/log/messages.0     "$OUT/messages.0.log"   2>/dev/null
cp /var/log/messages_0     "$OUT/messages_0.log"   2>/dev/null
cat /var/log/messages*     > "$OUT/messages_all.log" 2>/dev/null

# --- 3. Kernel ring buffer ---------------------------------------------
dmesg > "$OUT/dmesg.log" 2>/dev/null

# --- 4. Crash reports the framework drops into the library -------------
# These are what show up as "documents" on the home screen. Grab the files
# themselves plus a time-sorted listing so we can spot the newest ones.
ls -lt /mnt/us/documents 2>/dev/null > "$OUT/documents_listing.txt"

# Copy anything in documents that looks like a crash/error/diagnostic report.
for f in /mnt/us/documents/*; do
  case "$f" in
    *[Cc]rash*|*[Ee]rror*|*[Rr]eport*|*[Dd]iag*|*.log)
      cp "$f" "$OUT/" 2>/dev/null ;;
  esac
done

# Other common crash-report locations on Kindle firmware.
ls -lt /var/local 2>/dev/null      > "$OUT/var_local_listing.txt"
cp /var/local/*crash* "$OUT/" 2>/dev/null
cp -r /var/local/crash* "$OUT/" 2>/dev/null
ls -lt /mnt/us/system 2>/dev/null  > "$OUT/system_listing.txt"

echo "done. files in $OUT:"
ls -l "$OUT"
echo
echo "Now: USB-connect the Kindle and copy the cc_logs folder to your laptop."
