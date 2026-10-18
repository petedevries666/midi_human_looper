#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
: "${YSFX_SOURCE:?Pinned ysfx required}"
: "${YSFX_BUILD:=$YSFX_SOURCE/build}"
[[ "$(git -C "$YSFX_SOURCE" rev-parse HEAD)" == 8077347ccf4115567aed81400281dca57acbb0cc ]]
dir=$(mktemp -d)
trap 'rm -rf "$dir"' EXIT
flags=(-O2)
if [[ ${SANITIZE:-0} == 1 ]];then flags=(-O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer);fi
c++ -std=c++11 "${flags[@]}" -fsigned-char -DSWELL_LICE_GDI -I"$YSFX_SOURCE/include" -I"$YSFX_SOURCE/sources" -I"$YSFX_SOURCE/thirdparty/WDL/source" tests/expression_host.cpp "$YSFX_BUILD/libysfx.a" -ldl -lpthread -o "$dir/host"
"$dir/host" midi_human_looper.jsfx --conductor-execution
