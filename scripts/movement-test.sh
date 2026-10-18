#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
movement_test_dir=$(mktemp -d);trap 'rm -rf "$movement_test_dir"' EXIT
flags=(-std=c++11 -O2)
[[ ${SANITIZE:-0} == 1 ]] && flags+=(-O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer)
c++ "${flags[@]}" tests/movement_engine.cpp -o "$movement_test_dir/movement-test"
"$movement_test_dir/movement-test"
