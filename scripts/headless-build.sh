#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
: "${YSFX_SOURCE:=$PWD/.build/ysfx}"
: "${YSFX_BUILD:=$YSFX_SOURCE/build}"
: "${HEADLESS_BINARY:=$PWD/.build/midi-headless-engine}"
if [[ ! -f "$YSFX_BUILD/libysfx.a" ]]; then
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
graphics_flags=()
for dependency in fontconfig freetype2;do
  if pkg-config --exists "$dependency";then
    read -r -a dependency_flags <<< "$(pkg-config --libs "$dependency")"
    graphics_flags+=("${dependency_flags[@]}")
  fi
done
c++ -std=c++11 -O2 -DSWELL_LICE_GDI -I"$YSFX_SOURCE/include" -I"$YSFX_SOURCE/sources" -I"$YSFX_SOURCE/thirdparty/WDL/source" headless/engine.cpp "$YSFX_BUILD/libysfx.a" "${jack_flags[@]}" "${graphics_flags[@]}" -ldl -lpthread -o "$HEADLESS_BINARY"
"$HEADLESS_BINARY" --queue-test
printf 'Built %s on %s (%s bits)\n' "$HEADLESS_BINARY" "$(uname -m)" "$(getconf LONG_BIT)"
