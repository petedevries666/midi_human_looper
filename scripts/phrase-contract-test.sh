#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
: "${TEST_PYTHON:=python3}"
export PYTHONPATH="$PWD/headless:$PWD/tests${PYTHONPATH:+:$PYTHONPATH}"
work=$(mktemp -d);trap 'rm -rf "$work"' EXIT
if [[ -n ${JACK_INCLUDE:-} ]];then flags=(-I"$JACK_INCLUDE" -l:libjack.so.0);else read -r -a flags <<< "$(pkg-config --cflags --libs jack)";fi
c++ -std=c++11 -O2 tests/zynthian_chain_jack.cpp "${flags[@]}" -lpthread -o "$work/probe"
export CHAIN_JACK_PROBE="$work/probe"
for contract in legacy1 2;do
 export MBMF_TEST_PHRASE_CONTRACT="$contract"
 "$TEST_PYTHON" tests/test_conductor_native_baseline.py
 "$TEST_PYTHON" tests/test_instance_ownership_jack.py
 CHAIN_NATIVE_ROUTES=1 "$TEST_PYTHON" tests/test_zynthian_dedicated_chain.py
done
