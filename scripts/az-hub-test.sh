#!/usr/bin/env bash
# One command: production portal/editor + isolated service fixtures + real PNGs.
set -euo pipefail
cd "$(dirname "$0")/.."
: "${TEST_PYTHON:=python3}"
: "${HEADLESS_BINARY:=$PWD/.build/midi-headless-engine}"
export HEADLESS_BINARY
scripts/web-access-test.sh
"$TEST_PYTHON" tests/test_az_hub.py
