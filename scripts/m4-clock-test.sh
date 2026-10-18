#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
: "${YSFX_SOURCE:?Set YSFX_SOURCE to the prepared pinned ysfx checkout}"
: "${YSFX_BUILD:=$YSFX_SOURCE/build}"
mkdir -p .build
flags=(-O2)
if [[ ${SANITIZE:-0} == 1 ]];then flags=(-O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer);fi
c++ -std=c++11 "${flags[@]}" -fsigned-char -DSWELL_LICE_GDI -I"$YSFX_SOURCE/include" -I"$YSFX_SOURCE/sources" -I"$YSFX_SOURCE/thirdparty/WDL/source" tests/expression_host.cpp "$YSFX_BUILD/libysfx.a" -ldl -lpthread -o .build/m4-clock-host
for mode in --m4-clock --free-capture --recovery-recording --chain-grid --m0-once --m0-hold --m0-playback --m0-entries --instances;do
  .build/m4-clock-host midi_human_looper.jsfx "$mode"
done
