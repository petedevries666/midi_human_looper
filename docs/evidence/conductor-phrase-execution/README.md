# PR D validation: real PHRASE CONDUCTOR

Tested implementation: `84ca2c04cb730608171dc4368f46add3cf9e05be`.
Base: PR #58 `b82b9a1`, stacked on #57/#56/#50. Contract: latest PR #55
`73cdee5`, read in full. Subsequent evidence-only commits do not change tested code.

## Executed gates

| Gate | Observed result |
| --- | --- |
| Complete selected combined native/JACK/Chromium regression | exit 0; final PASS |
| Shared production EEL engine | 18,508 checks PASS, including D's 125 checks |
| C production persistence | 23 tests PASS, repeated with strict native ASAN |
| D actual native callback/API | 3 tests PASS, repeated with strict native ASAN |
| Strict native child ASAN gate | functional exit 0; zero diagnostic files |
| Focused D EEL ASAN/UBSAN host | 125 checks PASS; exit 0 |
| Focused B ownership EEL ASAN/UBSAN host | 6,698 checks PASS; exit 0 |
| Existing Chromium manual TEST through native callback | PASS with hardware input disabled/unassigned |
| Private JACK output capture | PASS; ordered events, no footswitch passthrough, empty receiver after cleanup |
| Known pending-edit UI counterexample | FAIL / exit 1, same signature; idle positive control PASS |
| Known telemetry/editor-click UI counterexample | FAIL / exit 1, same signature; idle positive control PASS |
| Legacy cross-source ONCE choke | unchanged shared/native XFAIL, not promoted or suppressed |

The selected combined suite is green; this **does not** make the two separately
executed UI counterexamples green. Both remain in the published evidence. No test
was removed or safety/overflow assertion relaxed. Build logs retain compiler
attribute warnings. The JACK log retains this environment's memory-lock warning.
The ysfx/WDL static library is not ASAN-instrumented; instrumented C++ adapters
and intercepted allocations are covered, not all generated EEL machine code.

## Actual emitted MIDI

`jack-output.json` contains all captured events from the real engine's JACK output,
not a software action echo. Tuple: absolute frame, block offset, status, data1,
data2. A separate bounded JACK client sends Note 110 footswitch PRESS/RELEASE into
the production engine; output comes from its shared EEL renderer and existing
native JACK path. Dummy JACK is a software driver, **not** physical hardware.

Four PRESS and wrap: `60, 62, 64, 65, 60`; all attacks have velocity 100. Earlier
instances remain active. The first targeted same-pitch STOP emits no premature
Note Off because the wrapped instance still owns that destination. Later two-layer
admission emits `60, 62` at the same absolute frame and offset. Targeted STOP emits
Off60; the existing legacy Smart Switch STOP emits Off62. PANIC uses the existing
CC64/123/120 emergency cleanup (624 captured messages across this fixture), not
an invented per-voice Off requirement. Receiver state ends empty. Missing UUID
references emit nothing. SAVE/LOAD adds no attacks and resets the cursor.

Focused EEL output independently proves `48, 52, 56, 60, 48`, actual local decay
velocities `46, 23, 11, 6`, time factors `1, 2, 4, 8`, source isolation, atomic
batch refusal and held-release ownership. Native/API tests cover supported local
LOOP/ONCE/HOLD overrides and reject unsupported REVEAL. The existing 12 slots
remain 12; a thirteenth admission cannot evict survivors.

## Measurements, not hardware promises

Final combined run, sparse two-event sources, 48 kHz / 128-frame EEL blocks,
100 admissions after ten warmups, Cloud x86_64:

| Layers admitted | Median µs | p95 µs | Max µs |
| --- | ---: | ---: | ---: |
| 1 | 28.447 | 55.459 | 171.280 |
| 2 | 29.244 | 41.387 | 77.972 |
| 12 | 46.996 | 106.874 | 935.522 |

These include shared admission/rendering, exclude stop cleanup/worker parsing,
and are noisy Cloud CPU measurements. Sanitized repeats have separate numbers
in their raw log. No Pi latency or resource qualification follows from these
figures. Functional JACK tests use 48 kHz / 8192 frames to reproduce the existing
conditional Cloud gate. Q3 is open: dense-source cost, larger configuration
handoff, Pi buffers/sample rates and final storage limits need measurements.
The compiled batch has 12 rows derived from the existing voice budget; documents
with more populated layers are preserved and explicitly refused, not truncated.

## Commands and environment

Executed from the isolated recovery checkout, with:

```sh
export YSFX_SOURCE=/workspace/setup-tools/ysfx
export YSFX_BUILD="$YSFX_SOURCE/build"
export JACK_INCLUDE=/workspace/scratch/midi-deps/root/usr/include
export JACKD=/workspace/scratch/midi-deps/root/usr/bin/jackd
export JACK_DRIVER_DIR=/workspace/scratch/midi-deps/root/usr/lib/x86_64-linux-gnu/jack
export TEST_PYTHON=/workspace/setup-tools/venv/bin/python
export CHROMIUM_PATH=/usr/bin/chromium
export HEADLESS_BINARY="$PWD/.build/midi-headless-engine"
export CHAIN_JACK_BLOCK=8192

scripts/headless-build.sh
"$TEST_PYTHON" tests/test_conductor_execution_browser.py
"$TEST_PYTHON" scripts/combined-test.py --native --jack --browser chromium --timeout 240
CONDUCTOR_TRACE=/tmp/mbmf-d-jack-final-trace.json \
  CONDUCTOR_JACK_PROBE="$PWD/.build/conductor-jack-probe" \
  "$TEST_PYTHON" tests/test_conductor_execution_jack.py
SANITIZE=1 scripts/conductor-execution-test.sh
SANITIZE=1 scripts/instance-ownership-test.sh
COMPARE_ROOT="$PWD" "$TEST_PYTHON" tests/conductor_diagnostics/pending_edit.py # expected exit 1
COMPARE_ROOT="$PWD" "$TEST_PYTHON" tests/conductor_diagnostics/editor_click.py # expected exit 1
```

Pinned ysfx SHA: `8077347ccf4115567aed81400281dca57acbb0cc`. The combined runner
builds the JACK probe. Normal binary SHA256 and source hashes are in `summary.json`.
No engine rebuild or source edit happened during the final combined run.

`browser-before-fix.log` retains the new disabled/unassigned-source TEST failure
found after the first combined run. `combined-before-preview-fix.log` is historical,
not final qualification. The fix is commit `84ca2c0`; final Chromium and full
combined regression were rerun on that commit. Keeping this evidence avoids
presenting the earlier green suite as coverage for a case it had not exercised.

## Phase verdict and preservation

**GO conditionnel for the next scoped implementation phase**: minimal PHRASE
execution, independent ownership, missing-reference diagnostics, supported local
overrides, STOP/PANIC and silent persistence pass actual production paths. Keep
all B/C gates and the two unchanged UI failures visible. Any new MIDI, JACK,
persistence or UI regression is NO-GO.

**Not a complete CONDUCTOR release**: no MOVEMENT/JOIN/REVEAL/FECK, unsupported
advanced gestures/configurations rejected, independent mono/ARP still restricted,
no new authoring UI. REAPER's adapter explicitly refuses native Conductor load;
shared EEL execution tests do not establish end-user REAPER execution parity.
Cloud tests do not qualify V4 ARM64/Helix/Firefox or low-buffer XRUN behavior.
Those physical tests remain human-reviewed and must not be deployed automatically.

No schema/portable format migration, web asset changes, JSFX `@gfx` changes,
installer changes, merge or deployment. All 25 preserved issue #54 working files
were rechecked by SHA256 and remain untouched.
