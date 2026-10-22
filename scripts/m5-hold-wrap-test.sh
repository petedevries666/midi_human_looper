#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
: "${YSFX_SOURCE:=$PWD/.build/ysfx}"
[[ "$(git -C "$YSFX_SOURCE" rev-parse HEAD)" == 8077347ccf4115567aed81400281dca57acbb0cc ]]
mkdir -p .build/m5-hold
python3 headless/native_capacity.py .build/m5-hold/native.jsfx
read -r -a graphics <<< "$(pkg-config --libs fontconfig freetype2)"
c++ -std=c++17 -O1 -fsigned-char -DSWELL_LICE_GDI -I"$YSFX_SOURCE/include" -I"$YSFX_SOURCE/sources" -I"$YSFX_SOURCE/thirdparty/WDL/source" tests/native_m5_hold_wrap.cpp "$YSFX_SOURCE/build/libysfx.a" "${graphics[@]}" -ldl -lpthread -o .build/m5-hold/test
.build/m5-hold/test .build/m5-hold/native.jsfx
c++ -std=c++17 -O1 -fsigned-char -DSWELL_LICE_GDI -I"$YSFX_SOURCE/include" -I"$YSFX_SOURCE/sources" -I"$YSFX_SOURCE/thirdparty/WDL/source" tests/native_m5_actions.cpp "$YSFX_SOURCE/build/libysfx.a" "${graphics[@]}" -ldl -lpthread -o .build/m5-hold/actions
.build/m5-hold/actions .build/m5-hold/native.jsfx
