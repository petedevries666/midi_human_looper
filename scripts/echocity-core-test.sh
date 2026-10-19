#!/usr/bin/env bash
set -euo pipefail
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
build="$root/.build/echocity-core-tests"
mkdir -p "$build"
compiler=${CXX:-c++}
flags=(-std=c++17 -O1 -Wall -Wextra -Werror -pedantic)
if [[ ${SANITIZE:-0} == 1 ]]; then
  flags+=(-g -fsanitize=address,undefined -fno-omit-frame-pointer)
fi
# Sequential builds only. This does not start JACK, load the musician's engine,
# change a patch, install dependencies, or restart a Zynthian service.
for test in native_note_scheduler echocity_core; do
  "$compiler" "${flags[@]}" "$root/tests/$test.cpp" -o "$build/$test"
  "$build/$test"
done
