#!/usr/bin/env bash
# Browser dependencies only. Native prerequisites use the existing headless setup.
set -euo pipefail
cd "$(dirname "$0")/.."
export PLAYWRIGHT_BROWSERS_PATH="${PLAYWRIGHT_BROWSERS_PATH:-$PWD/.build/playwright-browsers}"
python3 -m venv .build/browser-venv
.build/browser-venv/bin/python -m pip install -r scripts/requirements-screenshots.txt
# Playwright's version pins the downloaded Chromium revision. Optional system Chromium
# can instead be selected explicitly with CHROMIUM_PATH when running screenshots.sh.
if command -v chromium >/dev/null; then
  chromium --version
else
  .build/browser-venv/bin/python -m playwright install chromium
fi
# Missing Linux libraries: use `python -m playwright install-deps chromium` in the
# environment installation phase with appropriate OS package permissions, not at runtime.
