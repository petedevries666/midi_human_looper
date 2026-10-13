#!/usr/bin/env bash
# Actual shared EEL output; optional ASAN/UBSAN host instrumentation.
set -euo pipefail
cd "$(dirname "$0")/.."
: "${YSFX_SOURCE:?Set YSFX_SOURCE to the pinned ysfx checkout}"
: "${YSFX_BUILD:=$YSFX_SOURCE/build}"
[[ "$(git -C "$YSFX_SOURCE" rev-parse HEAD)" == 8077347ccf4115567aed81400281dca57acbb0cc ]]
build_dir=$(mktemp -d)
trap 'rm -rf "$build_dir"' EXIT
flags=(-O2)
if [[ ${SANITIZE:-0} == 1 ]];then flags=(-O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer);fi
c++ -std=c++11 "${flags[@]}" -fsigned-char -DSWELL_LICE_GDI \
 -I"$YSFX_SOURCE/include" -I"$YSFX_SOURCE/sources" \
 -I"$YSFX_SOURCE/thirdparty/WDL/source" tests/expression_host.cpp \
 "$YSFX_BUILD/libysfx.a" -ldl -lpthread -o "$build_dir/instance-host"
"$build_dir/instance-host" midi_human_looper.jsfx --instances
