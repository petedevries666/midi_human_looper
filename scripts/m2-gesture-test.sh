#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
: "${TEST_PYTHON:=python3}"
export PYTHONPATH="$PWD/headless:$PWD/tests${PYTHONPATH:+:$PYTHONPATH}"
scripts/m0-playback-test.sh --m2-gestures
"$TEST_PYTHON" tests/test_conductor_gestures_native.py
if [[ ${RUN_JACK_TESTS:-0} == 1 ]]; then
  build_dir=$(mktemp -d)
  trap 'rm -rf "$build_dir"' EXIT
  if [[ -n ${JACK_INCLUDE:-} ]]; then
    jack_flags=(-I"$JACK_INCLUDE" -l:libjack.so.0)
  else
    read -r -a jack_flags <<< "$(pkg-config --cflags --libs jack)"
  fi
  c++ -std=c++11 -O2 -DMBMF_TEST_ACYCLIC tests/conductor_jack.cpp "${jack_flags[@]}" -lpthread -o "$build_dir/probe"
  CONDUCTOR_JACK_PROBE="$build_dir/probe" "$TEST_PYTHON" tests/test_conductor_gestures_jack.py
fi
