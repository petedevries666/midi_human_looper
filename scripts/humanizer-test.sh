#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
humanizer_test_dir=$(mktemp -d)
trap 'rm -rf "$humanizer_test_dir"' EXIT
flags=(-std=c++11 -O2 -Wall -Wextra -Werror)
[[ "${SANITIZE:-0}" == 1 ]] && flags+=(-O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer)
c++ "${flags[@]}" tests/humanizer.cpp -o "$humanizer_test_dir/humanizer-test"
"$humanizer_test_dir/humanizer-test"
