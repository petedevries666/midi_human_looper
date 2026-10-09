#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
controller_test_dir=$(mktemp -d)
trap 'rm -rf "$controller_test_dir"' EXIT
flags=(-std=c++11 -O2 -Wall -Wextra -Werror)
[[ "${SANITIZE:-0}" == 1 ]] && flags+=(-O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer)
c++ "${flags[@]}" tests/controller_engine.cpp -o "$controller_test_dir/controller-test"
"$controller_test_dir/controller-test"
