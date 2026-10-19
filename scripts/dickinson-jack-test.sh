#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ -n ${JACK_INCLUDE:-} ]];then jack_flags=(-I"$JACK_INCLUDE" -l:libjack.so.0);else read -r -a jack_flags <<< "$(pkg-config --cflags --libs jack)";fi
mkdir -p .build/dickinson
c++ -std=c++11 -O2 -DMBMF_TEST_ACYCLIC -DMBMF_TEST_CAPTURE_ALL_CC tests/conductor_jack.cpp "${jack_flags[@]}" -lpthread -o .build/dickinson/jack-probe
export CONDUCTOR_JACK_PROBE="$PWD/.build/dickinson/jack-probe"
"${TEST_PYTHON:-python3}" tests/test_dickinson_jack.py
