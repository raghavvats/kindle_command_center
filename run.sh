#!/usr/bin/env bash
# Convenience launcher for local development on your laptop.
set -e
cd "$(dirname "$0")"

# Create venv on first run.
if [ ! -d ".venv" ]; then
  echo "Creating virtual environment..."
  python3 -m venv .venv
  ./.venv/bin/pip install --upgrade pip
  ./.venv/bin/pip install -r requirements.txt
fi

echo "Starting Kindle Command Center..."
echo "Open from another device at: http://$(ipconfig getifaddr en0 2>/dev/null || hostname):${PORT:-8000}"
exec ./.venv/bin/python run.py
