#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
printf 'Target: %s, %s bits\n' "$(uname -m)" "$(getconf LONG_BIT)"
case "$(uname -m)" in aarch64|armv7l|x86_64) ;; *) echo 'Unaudited architecture: verify ysfx support before continuing.' >&2;exit 1;; esac
# Run from a local terminal; SSH is not required. Uses sudo only for OS dependencies.
sudo apt-get update
sudo apt-get install -y git build-essential cmake pkg-config libjack-jackd2-dev jack-tools python3
: "${YSFX_SOURCE:=$PWD/.build/ysfx}"
if [[ ! -d "$YSFX_SOURCE/.git" ]]; then git clone https://github.com/jpcima/ysfx.git "$YSFX_SOURCE";fi
[[ -z "$(git -C "$YSFX_SOURCE" status --porcelain)" ]] || { echo 'ysfx checkout has changes; refusing checkout' >&2;exit 1; }
git -C "$YSFX_SOURCE" checkout 8077347ccf4115567aed81400281dca57acbb0cc
git -C "$YSFX_SOURCE" submodule update --init --recursive
cmake -S "$YSFX_SOURCE" -B "$YSFX_SOURCE/build" -DYSFX_PLUGIN=OFF -DYSFX_TOOLS=ON -DCMAKE_BUILD_TYPE=Release
cmake --build "$YSFX_SOURCE/build" --parallel "${BUILD_JOBS:-2}"
export YSFX_SOURCE
exec scripts/headless-build.sh
