#!/usr/bin/env bash
# Instrument the actual native host; inspect child diagnostics even if Python's
# functional assertions pass. This runs private non-JACK fixtures only.
set -euo pipefail
cd "$(dirname "$0")/.."
: "${TEST_PYTHON:=python3}"
export HEADLESS_BINARY="$PWD/.build/midi-headless-engine-conductor-asan"
export SANITIZE=1
sanitizer_dir=$(mktemp -d)
trap 'rm -rf "$sanitizer_dir"' EXIT
export ASAN_OPTIONS="detect_leaks=1:abort_on_error=1:log_path=$sanitizer_dir/asan"
export UBSAN_OPTIONS="halt_on_error=1:print_stacktrace=1:log_path=$sanitizer_dir/ubsan"
scripts/headless-build.sh
set +e
"$TEST_PYTHON" tests/test_conductor_persistence.py
functional_status=$?
"$TEST_PYTHON" tests/test_conductor_execution_native.py
execution_status=$?
if [[ $execution_status != 0 ]];then functional_status=$execution_status;fi
"$TEST_PYTHON" tests/test_movement_persistence.py
movement_status=$?
if [[ $movement_status != 0 ]];then functional_status=$movement_status;fi
set -e
"$TEST_PYTHON" - "$sanitizer_dir" "$functional_status" <<'PY'
from pathlib import Path
import sys
logs=sorted(Path(sys.argv[1]).glob('*'))
for log in logs:
    print(log.read_text(),file=sys.stderr)
print(f'Native sanitizer gate: functional exit={sys.argv[2]}, diagnostic files={len(logs)}')
if sys.argv[2]!='0' or logs:sys.exit(1)
PY
