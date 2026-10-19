#!/usr/bin/env bash
set -euo pipefail
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
: "${YSFX_SOURCE:=/root/midi_human_looper/.build/ysfx}"
[[ "$(git -C "$YSFX_SOURCE" rev-parse HEAD)" == 8077347ccf4115567aed81400281dca57acbb0cc ]]
mkdir -p "$root/.build/velocity-tests"
python3 "$root/headless/native_capacity.py" "$root/.build/velocity-tests/native.jsfx"
read -r -a graphics <<< "$(pkg-config --libs fontconfig freetype2)"
c++ -std=c++17 -O1 -fsigned-char -DSWELL_LICE_GDI -I"$YSFX_SOURCE/include" -I"$YSFX_SOURCE/sources" -I"$YSFX_SOURCE/thirdparty/WDL/source" \
 "$root/tests/native_velocity_gain.cpp" "$YSFX_SOURCE/build/libysfx.a" "${graphics[@]}" -ldl -lpthread -o "$root/.build/velocity-tests/native-velocity"
"$root/.build/velocity-tests/native-velocity" "$root/.build/velocity-tests/native.jsfx"
python3 -m unittest discover -s "$root/tests" -p test_module_registry.py
python3 - "$root" <<'PY'
import json,pathlib,subprocess,sys
r=pathlib.Path(sys.argv[1]);catalog=json.loads((r/'modules/catalog.json').read_text())
legacy=json.loads((r/'tests/fixtures/conductor/legacy-parameters.json').read_text())
expected=next(p for p in legacy['parameters'] if p['id']=='velocity')
actual=next(p for p in catalog['parameters'] if p['id']=='velocity')
assert {key:actual[key] for key in expected}==expected
assert (r/'midi_human_looper.jsfx').read_bytes()==subprocess.check_output(['git','show','HEAD:midi_human_looper.jsfx'],cwd=r)
print('PASS frozen legacy velocity contract and byte-identical REAPER source')
PY
