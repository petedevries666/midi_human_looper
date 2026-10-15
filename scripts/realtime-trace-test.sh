#!/usr/bin/env bash
# Worker drains CSV; allocation counter covers the bounded callback scopes.
set -euo pipefail
cd "$(dirname "$0")/.."
trace_test_dir=$(mktemp -d)
trap 'rm -rf "$trace_test_dir"' EXIT
c++ -std=c++11 -O2 -pthread tests/realtime_trace.cpp -o "$trace_test_dir/test"
"$trace_test_dir/test" "$trace_test_dir/callback.csv"

"$trace_test_dir/test" "$trace_test_dir/wall.csv" --wall
