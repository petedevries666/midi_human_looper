#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
movement_probe_dir=$(mktemp -d);trap 'rm -rf "$movement_probe_dir"' EXIT
if [[ -n ${JACK_INCLUDE:-} ]];then jack_flags=(-I"$JACK_INCLUDE" -l:libjack.so.0);else read -r -a jack_flags <<< "$(pkg-config --cflags --libs jack)";fi
c++ -std=c++11 -O2 -DMBMF_TEST_CAPTURE_ALL_CC tests/conductor_jack.cpp "${jack_flags[@]}" -lpthread -o "$movement_probe_dir/probe"
MOVEMENT_JACK_PROBE="$movement_probe_dir/probe" "${TEST_PYTHON:-python3}" tests/test_movement_jack.py
