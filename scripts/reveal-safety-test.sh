#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
: "${TEST_PYTHON:=python3}"
work=$(mktemp -d);trap 'rm -rf "$work"' EXIT
if [[ -n ${JACK_INCLUDE:-} ]];then flags=(-I"$JACK_INCLUDE" -l:libjack.so.0);else read -r -a flags <<< "$(pkg-config --cflags --libs jack)";fi
c++ -std=c++11 -O2 -DMBMF_TEST_CAPTURE_ALL_CC -DMBMF_TEST_ACYCLIC -DMBMF_TEST_FORBID_PRIVATE_CONTROL tests/conductor_jack.cpp "${flags[@]}" -lpthread -o "$work/probe"
export CONDUCTOR_JACK_PROBE="$work/probe"
"$TEST_PYTHON" tests/test_reveal_safety_jack.py
"$TEST_PYTHON" tests/test_reveal_safety_jack.py --source-sustain
"$TEST_PYTHON" tests/test_reveal_safety_jack.py --takeover
"$TEST_PYTHON" tests/test_reveal_safety_jack.py --burst
