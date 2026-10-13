# Executed PR C evidence

Production engine implementation: `949b6b2c4d8c23ac18418f7b20fdd267a5aaa100`.
The later Lua wording clarification changes no execution or validation; its six
actual Lua-daemon tests were rerun after the change. Exact hashes are in
`summary.json`. Full combined suite exit **0**. No hardware access/deployment.

The environment reused the pinned ysfx `8077347ccf4115567aed81400281dca57acbb0cc`,
Python venv and Chromium; no OS package/service or JACK configuration was changed.
`Cannot lock down ...` messages in dummy JACK are Cloud memlock warnings, not
claims of real-time hardware qualification. Optional fontconfig/freetype pkg-config
metadata is absent; the pinned ysfx build does not require these optional links.

Commands executed from the C checkout:

```sh
source /tmp/mbmf-b-env.sh
scripts/headless-build.sh
"$TEST_PYTHON" tests/test_conductor_persistence.py
"$TEST_PYTHON" scripts/combined-test.py --native --jack --browser chromium --timeout 240
SANITIZE=1 scripts/instance-ownership-test.sh
COMPARE_ROOT="$PWD" "$TEST_PYTHON" tests/conductor_diagnostics/pending_edit.py
COMPARE_ROOT="$PWD" "$TEST_PYTHON" tests/conductor_diagnostics/editor_click.py
"$TEST_PYTHON" tests/test_patch_io.py
```

The temporary environment file supplies `YSFX_SOURCE`, `YSFX_BUILD`,
`JACK_INCLUDE`, `JACKD`, `JACK_DRIVER_DIR`, `TEST_PYTHON`, `CHROMIUM_PATH`,
`HEADLESS_BINARY` and `CHAIN_JACK_BLOCK=8192`. Use AGENTS.md and the existing build
setup on another Cloud workspace; this is not a Zynthian installation command.

Results:

- `targeted.log`: 23 tests = eight new C workflows plus 15 inherited native
  compatibility tests, all PASS. Actual native worker/HTTP/file/portable paths.
- `combined.log`: complete native/JACK/Chromium suite PASS; 18,383 actual
  EEL/GUI/MIDI checks, 18 capture/36 free-capture SMF fixtures, 41 shared-EEL
  portable parity checks. Ownership, overload, three-chain recording, timestamp
  order, controllers, snapshots, persistence, bridge and browser workflows pass.
- Controller normal and ASAN: 162,709 core + 558 host checks each PASS.
- `ownership-asan.log`: 6,698 actual EEL-host ownership checks PASS.
- `native-asan.log`: the actual C native engine rebuilt with ASAN/UBSAN runs the
  same 23 production-path tests, PASS. ysfx is the existing **uninstrumented**
  static library; this is host/worker instrumentation, not complete WDL coverage.
- `lua.log`: six tests against the shipped Lua daemon, PASS, including refused
  CONDUCTOR LOAD and overwrite without changing payload/original file.
- `ui-pending.log` and `ui-editor.log`: expected **FAIL, exit 1** with the same
  two PR B signatures; idle positive controls PASS. They are not counted green.
- `ui-*-import-failure.log`: initial diagnostic invocation omitted the required
  test import path. These are setup failures, not UI reproductions; the corrected
  `COMPARE_ROOT` invocations produce the actual observations above.
- Legacy ONCE cross-source choke remains explicit XFAIL (shared/native), separate
  from independently admitted voices. The two B ownership corrections stay PASS.

Native ASAN build used the production build's include/library flags with:

```sh
c++ -std=c++11 -O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer \
  -fsigned-char -DSWELL_LICE_GDI \
  '-DMBMF_BUILD_REVISION="949b6b2c4d8c23ac18418f7b20fdd267a5aaa100"' \
  -I"$YSFX_SOURCE/include" -I"$YSFX_SOURCE/sources" \
  -I"$YSFX_SOURCE/thirdparty/WDL/source" -I"$JACK_INCLUDE" \
  headless/engine.cpp "$YSFX_BUILD/libysfx.a" -l:libjack.so.0 -ldl -lpthread \
  -o .build/midi-headless-engine-conductor-asan
HEADLESS_BINARY="$PWD/.build/midi-headless-engine-conductor-asan" \
  "$TEST_PYTHON" tests/test_conductor_persistence.py
```

Capacity measurement recipe (no musical upper limit inferred):

```python
import json, sys
sys.path[:0] = ['tests', 'headless']
from test_conductor_persistence import fixture, step, block
import conductor
model = fixture({})
model['switches'][0]['steps'].append(step([block(model['sources'][1]['id']), None]))
wire = conductor.encode(model)
print(len(wire['configuration']))
print(len(json.dumps(wire, separators=(',', ':'))))
print(len(json.dumps(dict(protocolVersion=1, action='conductor_commit',
    expectedRevision=1, expectedEngineSessionId=1, conductor=model), separators=(',', ':'))))
```

**GO conditionnel pour D minimal**, with B ownership restrictions and 12 voices
preserved. D must provide bounded execution handoff, resolve stable IDs, refuse
missing sources and validate its own MIDI workflow. Movement source execution,
Q3 future limits, REAPER CONDUCTOR execution and physical V4/Helix/Firefox/REAPER
qualification are not delivered by C. No full release GO is claimed.
