#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
: "${YSFX_SOURCE:?Set YSFX_SOURCE to the prepared ysfx checkout}"
: "${YSFX_BUILD:=$YSFX_SOURCE/build}"
mkdir -p .build
c++ -std=c++11 -O2 -DSWELL_LICE_GDI -I"$YSFX_SOURCE/include" -I"$YSFX_SOURCE/sources" -I"$YSFX_SOURCE/thirdparty/WDL/source" tests/expression_host.cpp "$YSFX_BUILD/libysfx.a" -ldl -lpthread -o .build/m0-playback-host
if [[ $# -gt 0 ]]; then
  .build/m0-playback-host midi_human_looper.jsfx "$1"
else
  for mode in --m0-playback --m0-once --m0-hold --m0-entries; do
    .build/m0-playback-host midi_human_looper.jsfx "$mode"
  done
fi
