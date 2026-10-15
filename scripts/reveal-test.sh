#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
: "${TEST_PYTHON:=python3}"
export PYTHONPATH="$PWD/headless:$PWD/tests${PYTHONPATH:+:$PYTHONPATH}"
build_dir=$(mktemp -d)
trap 'rm -rf "$build_dir"' EXIT
flags=(-std=c++11 -O2)
if [[ ${SANITIZE:-0} == 1 ]]; then flags=(-std=c++11 -O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer); fi
c++ "${flags[@]}" tests/reveal_engine.cpp -o "$build_dir/reveal"
"$build_dir/reveal"
"$TEST_PYTHON" tests/test_conductor_reveal_native.py
if [[ ${RUN_JACK_TESTS:-0} == 1 ]]; then
  if [[ -n ${JACK_INCLUDE:-} ]]; then jack_flags=(-I"$JACK_INCLUDE" -l:libjack.so.0); else read -r -a jack_flags <<< "$(pkg-config --cflags --libs jack)"; fi
  c++ -std=c++11 -O2 -DMBMF_TEST_CAPTURE_ALL_CC -DMBMF_TEST_ACYCLIC -DMBMF_TEST_FORBID_PRIVATE_CONTROL tests/conductor_jack.cpp "${jack_flags[@]}" -lpthread -o "$build_dir/probe"
  REVEAL_BROWSER_TEST="${RUN_CHAIN_BROWSER:-}" CONDUCTOR_JACK_PROBE="$build_dir/probe" "$TEST_PYTHON" tests/test_conductor_reveal_jack.py
fi
