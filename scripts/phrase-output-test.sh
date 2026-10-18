#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
: "${YSFX_SOURCE:?Use the existing headless setup}"
: "${YSFX_BUILD:=$YSFX_SOURCE/build}"
: "${TEST_PYTHON:=python3}"
: "${HEADLESS_BINARY:=$PWD/.build/midi-headless-engine}"
export HEADLESS_BINARY
test -x "$HEADLESS_BINARY"
build_dir=$(mktemp -d)
trap 'rm -rf "$build_dir"' EXIT
c++ -std=c++11 -O2 -DSWELL_LICE_GDI -I"$YSFX_SOURCE/include" -I"$YSFX_SOURCE/sources" -I"$YSFX_SOURCE/thirdparty/WDL/source" tests/expression_host.cpp "$YSFX_BUILD/libysfx.a" -ldl -lpthread -o "$build_dir/host"
"$build_dir/host" midi_human_looper.jsfx --phrase-output
"$build_dir/host" midi_human_looper.jsfx --instances
"$TEST_PYTHON" tests/test_phrase_output_browser.py
if [[ -n "${JACK_INCLUDE:-}" ]];then jack_flags=(-I"$JACK_INCLUDE" -l:libjack.so.0);else read -r -a jack_flags <<< "$(pkg-config --cflags --libs jack)";fi
c++ -std=c++11 -O2 -DMBMF_TEST_CAPTURE_CHANNEL_VOICE tests/conductor_jack.cpp "${jack_flags[@]}" -lpthread -o "$build_dir/probe"
PHRASE_OUTPUT_PROBE="$build_dir/probe" "$TEST_PYTHON" tests/test_phrase_output_jack.py
