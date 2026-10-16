#!/usr/bin/env bash
# Private development JACK servers only. Never run on the physical Zynthian.
set -euo pipefail
cd "$(dirname "$0")/.."
: "${TEST_PYTHON:=python3}"
build_dir=$(mktemp -d)
trap 'rm -rf "$build_dir"' EXIT
if [[ -n ${JACK_INCLUDE:-} ]];then jack_flags=(-I"$JACK_INCLUDE" -l:libjack.so.0);else read -r -a jack_flags <<< "$(pkg-config --cflags --libs jack)";fi
c++ -std=c++11 -O2 -DMBMF_TEST_ACYCLIC -DMBMF_TEST_CAPTURE_ALL_CC tests/conductor_jack.cpp "${jack_flags[@]}" -lpthread -o "$build_dir/probe"
c++ -std=c++11 -O2 tests/jack_transport_control.cpp "${jack_flags[@]}" -lpthread -o "$build_dir/transport"
export CONDUCTOR_JACK_PROBE="$build_dir/probe" M4_TRANSPORT_PROBE="$build_dir/transport"
"$TEST_PYTHON" tests/test_m4_diagnostics_jack.py
"$TEST_PYTHON" tests/test_m4_free_clock_jack.py
