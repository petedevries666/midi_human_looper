#!/usr/bin/env bash
set -euo pipefail
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
: "${YSFX_SOURCE:=$root/.build/ysfx}"
: "${YSFX_BUILD:=$YSFX_SOURCE/build}"
[[ "$(git -C "$YSFX_SOURCE" rev-parse HEAD)" == 8077347ccf4115567aed81400281dca57acbb0cc ]]
build="$root/.build/echocity-native-tests"
mkdir -p "$build"
flags=(-std=c++17 -O1 -Wall -Wextra -fsigned-char -DSWELL_LICE_GDI)
if [[ ${SANITIZE:-0} == 1 ]];then flags+=(-g -fsanitize=address,undefined -fno-omit-frame-pointer);fi
graphics=()
for dependency in fontconfig freetype2;do
  if pkg-config --exists "$dependency";then
    read -r -a dependency_flags <<< "$(pkg-config --libs "$dependency")"
    graphics+=("${dependency_flags[@]}")
  fi
done
"${TEST_PYTHON:-python3}" "$root/headless/native_capacity.py" "$build/native-expanded.jsfx"
"${CXX:-c++}" "${flags[@]}" -I"$YSFX_SOURCE/include" -I"$YSFX_SOURCE/sources" -I"$YSFX_SOURCE/thirdparty/WDL/source" \
  "$root/tests/echocity_native_sources.cpp" "$YSFX_BUILD/libysfx.a" "${graphics[@]}" -ldl -lpthread -o "$build/echocity_native_sources"
"$build/echocity_native_sources" "$build/native-expanded.jsfx"
"${CXX:-c++}" "${flags[@]}" "$root/tests/echocity_runtime.cpp" -o "$build/echocity_runtime"
"$build/echocity_runtime"
