#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
: "${YSFX_SOURCE:=$PWD/.build/ysfx}"
: "${YSFX_BUILD:=$YSFX_SOURCE/build}"
mkdir -p .build/dickinson
python3 headless/native_capacity.py .build/dickinson/native.jsfx
read -r -a graphics <<< "$(pkg-config --libs fontconfig freetype2)"
flags=(-std=c++17 -O1 -fsigned-char -DSWELL_LICE_GDI)
if [[ ${SANITIZE:-0} == 1 ]];then flags+=(-g -fsanitize=address,undefined -fno-omit-frame-pointer);fi
for source in dickinson_arp native_random_arp;do
 c++ "${flags[@]}" -I"$YSFX_SOURCE/include" -I"$YSFX_SOURCE/sources" -I"$YSFX_SOURCE/thirdparty/WDL/source" "tests/$source.cpp" "$YSFX_BUILD/libysfx.a" "${graphics[@]}" -ldl -lpthread -o ".build/dickinson/$source"
 ".build/dickinson/$source" .build/dickinson/native.jsfx
done
