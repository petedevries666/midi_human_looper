#!/usr/bin/env bash
# Private production-engine/Tornado/Chromium fixtures; no host service operations.
set -euo pipefail
cd "$(dirname "$0")/.."
: "${TEST_PYTHON:=python3}"
: "${HEADLESS_BINARY:=$PWD/.build/midi-headless-engine}"
export HEADLESS_BINARY
"$TEST_PYTHON" tests/test_web_access_provision.py
"$TEST_PYTHON" tests/test_local_web_access.py
