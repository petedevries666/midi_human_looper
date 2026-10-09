#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
: "${YSFX_SOURCE:=$PWD/.build/ysfx}"
: "${HEADLESS_BINARY:=$PWD/.build/midi-headless-engine}"
if [[ ! -f "$YSFX_SOURCE/build/libysfx.a" ]]; then
  echo 'Run scripts/headless-setup.sh first, or set YSFX_SOURCE to the pinned checkout.' >&2; exit 1
fi
[[ "$(git -C "$YSFX_SOURCE" rev-parse HEAD)" == 8077347ccf4115567aed81400281dca57acbb0cc ]]
mkdir -p "$(dirname "$HEADLESS_BINARY")"
# JACK_INCLUDE permits an extracted development package in an unprivileged workspace.
if [[ -n "${JACK_INCLUDE:-}" ]]; then
  jack_flags=(-I"$JACK_INCLUDE" -l:libjack.so.0)
else
  read -r -a jack_flags <<< "$(pkg-config --cflags --libs jack)"
fi
c++ -std=c++11 -O2 -DSWELL_LICE_GDI -I"$YSFX_SOURCE/include" -I"$YSFX_SOURCE/sources" -I"$YSFX_SOURCE/thirdparty/WDL/source" headless/engine.cpp "$YSFX_SOURCE/build/libysfx.a" "${jack_flags[@]}" -ldl -lpthread -o "$HEADLESS_BINARY"
"$HEADLESS_BINARY" --queue-test
printf 'Built %s on %s (%s bits)\n' "$HEADLESS_BINARY" "$(uname -m)" "$(getconf LONG_BIT)"
