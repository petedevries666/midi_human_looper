#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
# Private desktop dummy server only. This script does not attach to Zynthian JACK.
: "${HEADLESS_BINARY:=$PWD/.build/midi-headless-engine}"
: "${JACKD:=jackd}"
export HEADLESS_BINARY JACKD
probe_dir=$(mktemp -d);trap 'rm -rf "$probe_dir"' EXIT
if [[ -n ${JACK_INCLUDE:-} ]];then jack_flags=(-I"$JACK_INCLUDE" -l:libjack.so.0);else read -r -a jack_flags <<< "$(pkg-config --cflags --libs jack)";fi
c++ -std=c++11 -O2 -DMBMF_TEST_CAPTURE_ALL_CC -DMBMF_TEST_EVENT_CAPACITY=65536 -DMBMF_TEST_ACYCLIC tests/conductor_jack.cpp "${jack_flags[@]}" -lpthread -o "$probe_dir/probe"
MOVEMENT_JACK_PROBE="$probe_dir/probe" "${TEST_PYTHON:-python3}" "${MOVEMENT_RT_TEST:-tests/movement_realtime_matrix.py}" "$@"
