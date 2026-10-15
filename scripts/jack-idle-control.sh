#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
probe_dir=$(mktemp -d);trap 'rm -rf "$probe_dir"' EXIT
if [[ -n ${JACK_INCLUDE:-} ]];then jack_flags=(-I"$JACK_INCLUDE" -l:libjack.so.0);else read -r -a jack_flags <<< "$(pkg-config --cflags --libs jack)";fi
c++ -std=c++11 -O2 -pthread tests/jack_idle_control.cpp "${jack_flags[@]}" -o "$probe_dir/probe"
IDLE_JACK_PROBE="$probe_dir/probe" "${TEST_PYTHON:-python3}" tests/jack_idle_control.py "$@"
