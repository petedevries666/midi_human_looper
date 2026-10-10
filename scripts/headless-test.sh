#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
: "${HEADLESS_BINARY:=$PWD/.build/midi-headless-engine}"
export HEADLESS_BINARY
"$HEADLESS_BINARY" --queue-test
python3 tests/test_headless_mvp.py
python3 tests/test_module_registry.py
python3 tests/test_zynthian_install.py
if [[ "${RUN_NATIVE_TESTS:-0}" == 1 ]];then tests/run_host_tests.sh;fi
if [[ "${RUN_JACK_TESTS:-0}" == 1 ]];then
  test_dir=$(mktemp -d);trap 'rm -rf "$test_dir"' EXIT
  if [[ -n "${JACK_INCLUDE:-}" ]];then jack_flags=(-I"$JACK_INCLUDE" -l:libjack.so.0);else read -r -a jack_flags <<< "$(pkg-config --cflags --libs jack)";fi
  c++ -std=c++11 -O2 tests/headless_jack.cpp "${jack_flags[@]}" -lpthread -o "$test_dir/jack-smoke"
  c++ -std=c++11 -O2 tests/zynthian_chain_jack.cpp "${jack_flags[@]}" -lpthread -o "$test_dir/chain-probe"
  CHAIN_JACK_PROBE="$test_dir/chain-probe" "${TEST_PYTHON:-python3}" tests/test_zynthian_chains.py
  JACK_TEST_BINARY="$test_dir/jack-smoke" python3 tests/test_jack_graph.py
fi
