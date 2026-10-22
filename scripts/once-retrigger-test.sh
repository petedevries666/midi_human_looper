#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
: "${YSFX_SOURCE:=$PWD/.build/ysfx}"
[[ "$(git -C "$YSFX_SOURCE" rev-parse HEAD)" == 8077347ccf4115567aed81400281dca57acbb0cc ]]
mkdir -p .build/once-retrigger
python3 headless/native_capacity.py .build/once-retrigger/native.jsfx
read -r -a graphics <<< "$(pkg-config --libs fontconfig freetype2)"
c++ -std=c++17 -O1 -fsigned-char -DSWELL_LICE_GDI -I"$YSFX_SOURCE/include" -I"$YSFX_SOURCE/sources" -I"$YSFX_SOURCE/thirdparty/WDL/source" tests/native_once_retrigger.cpp "$YSFX_SOURCE/build/libysfx.a" "${graphics[@]}" -ldl -lpthread -o .build/once-retrigger/test
.build/once-retrigger/test "${ONCE_TEST_SOURCE:-.build/once-retrigger/native.jsfx}"
