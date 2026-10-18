# M2b — REVEAL / GATE evidence, draft #82

Code commit: `74a8f3d457fb6509dec7e26e218e923034375bdb`. Base #81:
`e8785f3cb3ede32445bdf08c9715334c3abc047f`. Later commits contain evidence and
status documentation. No physical hardware, installation, merge or release.

## Implemented and observed

Real Chromium authoring → DONE → PATCH SAVE/LOAD → reconnect → actual native DSP →
private JACK MIDI port capture, without replacing the engine or mocking its API.
`jack-trace.json` records receiver observation order; the receiver never sorts.

- PRESS emits CC7=0 before CH2 pad Note On at the same sample.
- Short tap: actual pad On at offset16 and Off at64; bass continues. Source-owned
  CC64=0 is emitted before CC7 is restored. The same full port fixture also passes
  without a browser (`headless-jack.log`).
- Twelve instances coexist; a thirteenth/two-layer admission is refused without
  changing any survivor ID. PANIC clears every note and CC7 lease (native + ASAN).
- HOLD restores 127 (unknown) or the observed effective value exactly 12000 samples
  after PRESS at 48 kHz. No replacement pad Note On at HOLD.
- GATE remasks while the same instance continues: the later note stays exactly
  36000 samples after the initial note. LATCH survives RELEASE.
- Source STOP and PANIC release ownership. Same-block PRESS16/PANIC64 emits
  attacks before releases; a later PRESS works without thousands of dummy Offs.
- A real CC7 MOVEMENT is replaced by REVEAL; its last audible value (93 in this
  run) is restored. Stale MOVEMENT retirement cannot delete the winning lease.
- Physical CC7=85 passes intact; old RELEASE/cleanup emits no later stale CC7.
- Captured attacks: `[48,72,48,72,76,48,72,76,48,72,76,48,72,48,72,76]`.
- Private bus-15 control markers do not appear on the JACK port. No output overflow.

`movement-before.json` proves a discovered branch regression: coalesced starts
emitted `[25,102]`. Final `movement-trace.json` proves the correction: `[102]`,
with original exact 10/25/50/100 Hz, initial/final and takeover assertions passing.
It also preserves the old cyclic receiver's backwards attribution; see the
implementation document for the acyclic single-clock-snapshot diagnostic fix.

## Executed commands / exits

Use the prepared environment from AGENTS.md (`HEADLESS_BINARY`, `TEST_PYTHON`,
`YSFX_SOURCE`, `YSFX_BUILD`, `JACK_INCLUDE`, `JACKD`, `JACK_DRIVER_DIR`, Chromium).
No test commands below are an instruction to operate on a live Zynthian.

| Command | Exit / actual result | Evidence |
|---|---|---|
| `scripts/headless-build.sh` | 0, bounded queue self-test | built binary hashes in provenance |
| `RUN_JACK_TESTS=1 RUN_CHAIN_BROWSER=1 scripts/reveal-test.sh` | 0: production token helper, 5 native tests, real Chromium/JACK | `focused.log`, `jack-trace.json` |
| `scripts/m2-gesture-test.sh` | 0: 692 actual DSP checks + 3 native tests | `m2-gesture.log` |
| `scripts/movement-jack-test.sh` (existing acyclic probe flag, unchanged Python assertions) | 0: four exact CC rates and ownership | `movement-jack.log`, `movement-trace.json` |
| `SANITIZE=1 scripts/reveal-test.sh` | 0, production helper instrumented | earlier helper run; actual native binary gate below |
| sanitized native build + `tests/test_conductor_reveal_native.py` | 0: 5 tests, no sanitizer diagnostics | `native-reveal-asan.log` |
| `scripts/conductor-persistence-test.sh` | 0: actual sanitized native persistence/execution/MOVEMENT; diagnostic files=0 | `remaining/06-conductor-persistence-test.log` |
| `tests/run_host_tests.sh` | 0: 18508 EEL checks + 18 capture + 36 free-capture/export fixtures | `remaining/04-run_host_tests.log` |
| `scripts/controller-test.sh`, ordinary and sanitizer | both 0: 162709 core + 579 host checks each | `combined-no-jack.log` |
| `scripts/screenshots.sh` | 0: 200 real PNGs, zero layout findings | `screenshots.log`, `docs/screenshots/manifest.json` |
| `CHAIN_JACK_PROBE=… tests/test_instance_output_overflow_jack.py` | 0: deliberate overflow=1; 64 attacks + 64 emergency releases | `overflow-jack.log` |
| `CHAIN_JACK_PROBE=… tests/test_zynthian_chains.py` | 0: three isolated processor fixture, recording/playback/save/load | `three-chains.log` |
| `scripts/combined-test.py --native --jack --browser chromium --timeout 600` | **1** on final code: legacy ownership expectation | `combined-final-jack.log` |
| `scripts/combined-test.py --native --browser chromium --timeout 600` | **1**: baseline still expects cross-source choke | `combined-no-jack.log` |

The diagnostic continuation (`diagnostic-remaining.py`, not a substitute green
combined gate) executed 30 commands: 29 exit0, one generic browser invocation
incorrectly defaulted to unavailable Firefox. Explicit `MIDI_BROWSER=chromium
$TEST_PYTHON tests/test_headless_browser.py` exits0 (`headless-chromium.log`). All
other requested Chromium tests passed, including both historical race fixtures
`pending_edit.py` and `editor_click.py`. Raw continuation exit remains1; it has not
been rewritten to green. `remaining/results.json` preserves each command and exit.
Native ownership, M0, source mute groups, M2, portable/patch compatibility, controller,
Snapshot, MIDI interchange, phrase editor and recovery checks are included.

Some independent earlier commands ran before the final C++ coalescing correction;
the final strict combined attempt, REVEAL JACK/native, MOVEMENT and native sanitizer
qualification used the corrected implementation. Do not claim a full green suite
on final HEAD: the strict combined runner stops at the retained failure.

## Three pre-existing contract mismatches, exact parent comparison

No test or assertion has been deleted, relaxed, filtered or converted to XFAIL.

| Fixture | Current result | Rebuilt exact #81 result |
|---|---|---|
| `test_instance_ownership_jack.py:55` | missing the expected source1 choke-Off; ONCE sources coexist | identical 8-event list (`parent-exact-ownership.log`) |
| `test_conductor_native_baseline.py:35` | expects only `[2]`, actual `[1,2]` | same error (`parent-native-baseline.log`) |
| `test_zynthian_dedicated_chain.py:161` | expects RELEASE to end HOLD; actual 3 held notes, contract2 | same 3 notes, contract2 (`parent-dedicated-chain.log`) |

Parent C++/changed headers and JSFX were read directly with `git show e8785f3:…`
and built with the same pinned ysfx/JACK environment; unchanged headers are shared.
No new checkout, install or alternate musical engine was created. Parent binary
and source identities are recorded in `provenance.json`. These old assertions
conflict with the already-approved M0 contract; focused contract2 DSP/JACK tests
remain separate and pass. Reconcile via explicit versioned legacy coverage later,
not by declaring this strict run successful.

## Visual evidence and limits

All 200 generated views were inspected in five viewport contact sheets, with the
new REVEAL editor also inspected full-size at 1440×900 and 320×240. Compact ENTRY,
REL, sliders, warning and scroll access remain usable. Real PNGs are in
`docs/screenshots/`; `screenshot-links.json` records three public raw PNG links
verified HTTP200. Generation preceded the final C++ coalescing fix; Web source did
not change afterwards. The manifest retains the actual generator provenance.

Functional JACK captures: Cloud x86_64, dummy/non-RT, 48 kHz/8192 frames. Expanded sustain/browser
REVEAL observation: max callback wall 12.2213 ms, 3 XRUN notifications. An earlier
coalescing run observed 48.7241 ms and 4 notifications; do not cherry-pick the lower
value or interpret either as engine-only CPU. MOVEMENT:
40.8713 ms, 2 notifications. Earlier runs overlapped browser regressions and sanitizer compilation. The expanded
fixture includes setup/configuration, actual browser editing and MIDI testing;
these lifetime maxima do not isolate steady-state LIVE use. CPU time was not
separately measured. The final combined run also
reported an XRUN (6207 µs) during the source-group fixture before its later pass.
This does not determine engine-only cost or establish 256/512-frame safety.

Not yet qualified: physical Zynthian/Helix/synth, external/shared-channel sustain interactions, dense REVEAL admission/cleanup under saturation,
small-buffer CPU/deadline behavior. CC7 is channel-wide; shared channels are warned
and allowed. Source PHRASE CC7 is explicitly refused. FADE/JOIN are not implemented
here. Unknown restore volume is 127 by explicit user decision.

**GO for focused draft code review. NO-GO for merge/release/deployment or claiming
complete M2/live qualification.** Next executable task is the missing REVEAL
sustain/shared-channel and saturation port coverage, then versioned reconciliation
of the three old-contract gates. Preserve #54 and the REAPER freeze.
