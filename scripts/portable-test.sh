#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
: "${YSFX_SOURCE:?Set YSFX_SOURCE}"
: "${YSFX_BUILD:=$YSFX_SOURCE/build}"
build_dir=$(mktemp -d)
trap 'rm -rf "$build_dir"' EXIT
c++ -std=c++11 -O2 -DSWELL_LICE_GDI -I"$YSFX_SOURCE/include" -I"$YSFX_SOURCE/sources" -I"$YSFX_SOURCE/thirdparty/WDL/source" tests/portable_parity.cpp "$YSFX_BUILD/libysfx.a" -ldl -lpthread -o "$build_dir/parity"
"$build_dir/parity" midi_human_looper.jsfx
"${TEST_PYTHON:-python3}" tests/test_portable_project.py
"${TEST_PYTHON:-python3}" tests/test_portable_engine.py
