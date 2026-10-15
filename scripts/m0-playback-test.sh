#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
: "${YSFX_SOURCE:?Set YSFX_SOURCE to the prepared ysfx checkout}"
: "${YSFX_BUILD:=$YSFX_SOURCE/build}"
mkdir -p .build
c++ -std=c++11 -O2 -DSWELL_LICE_GDI -I"$YSFX_SOURCE/include" -I"$YSFX_SOURCE/sources" -I"$YSFX_SOURCE/thirdparty/WDL/source" tests/expression_host.cpp "$YSFX_BUILD/libysfx.a" -ldl -lpthread -o .build/m0-playback-host
.build/m0-playback-host midi_human_looper.jsfx --m0-playback
