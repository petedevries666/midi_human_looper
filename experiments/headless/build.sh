#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
: "${YSFX_SOURCE:?Set YSFX_SOURCE to the audited ysfx checkout (see README)}"
: "${YSFX_BUILD:=$YSFX_SOURCE/build}"
: "${HEADLESS_BINARY:=/tmp/midi-headless-engine}"
test "$(git -C "$YSFX_SOURCE" rev-parse HEAD)" = "8077347ccf4115567aed81400281dca57acbb0cc"
c++ -std=c++11 -O2 -DSWELL_LICE_GDI -I"$YSFX_SOURCE/include" -I"$YSFX_SOURCE/sources" -I"$YSFX_SOURCE/thirdparty/WDL/source" experiments/headless/engine.cpp "$YSFX_BUILD/libysfx.a" -ldl -lpthread -o "$HEADLESS_BINARY"
"$HEADLESS_BINARY" --queue-test
