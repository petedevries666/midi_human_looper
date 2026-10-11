#!/usr/bin/env bash
# One command after environment setup. Never connects to a musician's running engine.
set -euo pipefail
cd "$(dirname "$0")/.."
: "${SCREENSHOT_PYTHON:=$PWD/.build/browser-venv/bin/python}"
: "${HEADLESS_BINARY:=$PWD/.build/midi-headless-engine}"
if [[ -z "${CHROMIUM_PATH:-}" ]] && command -v chromium >/dev/null; then
  export CHROMIUM_PATH="$(command -v chromium)"
fi
export HEADLESS_BINARY
export PLAYWRIGHT_BROWSERS_PATH="${PLAYWRIGHT_BROWSERS_PATH:-$PWD/.build/playwright-browsers}"
if [[ ! -x "$SCREENSHOT_PYTHON" ]]; then
  echo 'Run scripts/screenshots-setup.sh first (or set SCREENSHOT_PYTHON).' >&2; exit 1
fi
if [[ ! -x "$HEADLESS_BINARY" ]]; then scripts/headless-build.sh; fi
exec "$SCREENSHOT_PYTHON" scripts/screenshots.py "$@"
