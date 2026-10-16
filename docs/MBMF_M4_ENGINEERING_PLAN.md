# M4 — execution checkpoint

Source: #85 `13ed0961c839cd79b3391b14f0bc77b1cfdf268c`, comment
https://github.com/petedevries666/midi_human_looper/pull/85#issuecomment-6203741796
and the user's complete M4 mission, read on 2026-10-16. Native + Web remain the
active targets; REAPER is frozen. No changes to the deployed Zynthian, routing
activation, live hardware REC, merges, or issue-54's 25 protected files.

## Recovery / dependencies

The existing checkout and caches were recovered, not cloned or reset. Interrupted
independent M2 work is preserved and pushed as `2a62570` + `3a5d357` on
`fix/reveal-midi-safety`; it is **not** silently included in M4. M4 branch
`fix/m4-routing-diagnostics` starts exactly at #85, retaining #82's musical stack.
No other M4 implementation PR was open at inspection.

## Increment 1 — routing and diagnostic boundaries

Confirmed before/after: six new assertions expose five transient-admission
failures plus a missing refresh quarantine. #85 would invoke virtual route
`enabled=1` even with no opt-in, malformed config, absent keyboard or failed
native readback. A later quarantine did not undo the transient risk.

Implementation: snapshot old matrix, remove desired JACK fanout, quarantine and
verify **all** virtual routes (continue closing after an individual failure),
then isolate physical/internal inputs, verify MULTI and all exclusions, then
admit allowed synth destinations. A late setter failure closes virtual routes
before restoring owned physical inputs. No synth names or new routing shortcuts.
Tests record every native setter call in `evidence/m4/native-setter-calls.jsonl`.

The source `midiCount` remains unchanged. Add cumulative, single-processing-thread
counters, copied through the existing bounded status queue:

| Status field | Exact boundary |
|---|---|
| `midiReceived` | Events reported in the JACK input buffer, including intentionally rejected input |
| `midiInputAccepted` | Successfully copied from JACK to the host ingress queue |
| `midiGenerated` | Public MIDI output packets produced for host output, plus emergency CC attempts; no private control markers |
| `midiQueued` | Normal packets admitted to the host JACK output queue |
| `midiWritten` | Successful `jack_midi_event_write` calls, including emergency CCs |
| `midiDropped` | Known host ingress/output rejection or queue cancellation; a failed write retained for retry is not a drop |
| `midiWriteFailures` | Failed JACK write attempts, including retryable attempts |
| `midiRecoveries` | Host emergency cleanup passes (including commanded chain cleanup) |
| `outputOverflow` | Existing aggregate overflow/fault notification count, not recording overflow |

These are stage counters, not an end-to-end conservation equation. Internal DSP
admission failures remain separately visible as `instanceRejected`/`instanceError`.
`midiGenerated` is not a synth-delivery claim; neither are successful JACK writes.
The smoke tool reports boundary deltas, retains the generation/XRUN guard and
also rejects receive/write storms. Old runtimes are labelled legacy generation.

Executed on native x86_64 Cloud, using production EEL and private dummy JACK:

- New routing tests on #85: exit 1, 5 failures + 1 error, recorded unchanged.
- After fix: exclusive input 22, firewall 7, native-source 4, installer 30,
  adapter 7, legacy routing 5 tests: all exit 0 (75 tests).
- Smoke tool: 3 tests, exit 0. Actual native/HTTP: 16 tests, exit 0.
- Real JACK: 3 input events -> 3 accepted -> 3 generated -> 3 queued -> 3
  successful writes -> 3 receiver events, at offsets 16/32/64; no drops or overflow.
- Initial JACK run failed with an empty receiver trace during multiple logged
  client XRUNs; retained as `midi-jack.log`, not relabelled PASS. An isolated rerun
  passed (`midi-jack-rerun.log`, `midi-boundaries.json`). No deadline assertion was
  weakened. This is functional evidence, **not** real-time or ARM64 qualification.

## Feedback paths and remaining isolation risks

The helper checks MB self-routes, MIDI-only destinations, native chain `midi_out`
return paths and the desired JACK graph. Explicit keyboard isolation blocks direct
bypass to synths and internal seq/step/CV input return to MB. DIN/ttymidi and other
unselected physical sources remain unchanged. User observation: MPKmini2 became
exclusive to MB, whereas DIN-5 remained on both chains. This does not prove that
ZynMidiRouter's internal matrix or the *actual* live JACK graph has no return path.

The desired graph is not an inventory of every live JACK connection or client
internal forwarding behavior. Arbitrary external hardware loops, recorder returns,
manual JACK edges and native UI changes need a real graph/matrix audit. The
helper stays default-off without explicit exclusive input policy. Reconfiguration
quarantines routes and is not claimed to be a seamless live-note operation.
**No hardware activation is authorized or performed by this PR.**

## Next increment — free-time clocks / capture diagnostics

A production ChainMode/EEL test reproduces the transport STOP incorrectly ending
FREE TIME capture (`clock-before.log`). This is a distinct defect; no evidence yet
links it causally to the hardware storm. Next: continuous audio-cycle clock for
capture-gap detection, transport independent source timing, precise error codes,
bounded validation and previous-phrase rollback; preserve optional grid capture.

## Safest hardware next step (NOT RUN)

Review immutable SHAs and offline evidence first. Leave MB output disconnected;
inspect current JACK edges, native input matrix, snapshot and install configuration
read-only. Do **not** install, enable exclusive/native routing, run REC or use the
smoke tool to justify automatic activation. Hardware testing requires separate
user approval and an emergency disconnect plan. No code here changes OS/JACK,
LUMAZ, tokens, installer or updater.

## Increment 2 — continuous capture clock and stable failure reasons

Branch `fix/m4-free-time-clock`, stacked on #86 (`523636a`). Production
`ChainMode::tick()` compared transport and audio-cycle deltas, disabled gap
monitoring while stopped, and interpreted rolling-to-stopped as interruption.
The deterministic before-test fails on transport STOP. FREE TIME now checks the
continuous audio-cycle clock, including a valid first frame zero and 32-bit JACK
frame wrap. Transport START/STOP/locate cannot change source timestamps or finish
a take. Missing audio cycles still reject/rollback an active take. The continuity
check runs **before** command consumption, so FINISH/STOP cannot commit a partial
take before a missed cycle is diagnosed. Optional grid V1/V2 keeps its separate
transport-aligned policy and existing gates.

FREE TIME REC/PLAY also no longer calls `jack_transport_start`; it does not need
or own the global transport. Optional grid commands retain their transport start.
This avoids a global side effect, not a claim that this caused the MIDI storm.
A real private JACK test records through stopped -> rolling -> locate -> stopped
and plays while the global transport stays stopped. Source Note On is at zero;
Note Off retains channel, pitch, velocity and relative timing in exported SMF.

Capture finalization validates a bounded count, finite duration and event ranges
before pairing; failure restores the original count/duration/trigger. Native
status preserves `chainError` and adds authoritative `chainErrorCode`,
`chainErrorReason`, `chainErrorPhraseId` (0 = none), `captureRejected` and
`captureOverflows` (cumulative free-time rejection/input-overflow diagnoses).
Reason names are defined once by ChainMode, reused by status serialization:

| Code | Reason | Evidence |
|---|---|---|
| 0 | `none` | valid capture / fresh REC |
| 1 | `record_overflow` | real 2048-event source + overdub append rejected |
| 2 | `release_capacity` | full append has no capacity for required note release |
| 3 | `invalid_capture` | negative timestamp / nonfinite count before finalization |
| 4 | `audio_clock_discontinuity` | missed audio block during stopped/rolling capture |
| 5 | `grid_tempo_changed` | existing optional-grid tempo rejection |

Native API tests reproduce reasons 1 and 2 with `outputOverflow=0`, restore every
event of the previous valid source, and SAVE/LOAD without starting playback.
The EEL fixture invokes actual ChainMode/shared DSP for invalid captures, audio
gaps, REC/CANCEL/STOP, FINISH after gap, 44.1/48/96 kHz and 128/256/512/8192 frames.
There is no new scheduler, callback JSON/I/O/locks, patch schema, musical feature,
REAPER source/UI change or routing activation.

One follow-up JACK run genuinely missed audio cycles and correctly returned
`audio_clock_discontinuity` with XRUNs; `clock-xrun-failure.log` remains a failure,
not filtered or retried inside the test. An isolated rerun of the exact assertions
passed with zero observed XRUNs (`final-clock-jack.log`, `clock-progress.json`).
This demonstrates the guard, not the cause of the physical storm. Host scheduling
versus engine contribution to Cloud XRUNs remains unqualified.

### Musical reference and scope

The production shared source remains `midi_human_looper.jsfx`, header v1.27.1,
unchanged from #85. The frozen historical reference is v1.23.0,
`72b92db091d5aef05d37b45057b62ffca390c867:midi_human_looper.jsfx`. Its historical
cross-source choke/graphical HOLD-stop is **not** falsely called identical to the
approved native M0 contract 2: ONCE overlap, LOOP toggle, HOLD cut/retrigger with
RELEASE ignored. M4 runs actual M0/ownership MIDI assertions and leaves their
implementation untouched. The legacy expectations/versioned reconciliation and
external sustain improvement remain on the separate preserved M2 safety branch.

### Reproduce in development only

Use the existing AGENTS.md prepared caches and `YSFX_SOURCE`, `YSFX_BUILD`,
`JACK_INCLUDE`, `JACKD`, `JACK_DRIVER_DIR`, `HEADLESS_BINARY`, `TEST_PYTHON`.
No OS/service changes or physical MIDI connections:

```sh
scripts/headless-build.sh
scripts/m4-clock-test.sh
SANITIZE=1 scripts/m4-clock-test.sh
python tests/test_m4_capture_status.py
python tests/test_native_free_capture.py
scripts/m4-jack-test.sh
```

These gates are also registered in the combined runner. Final proportional
regression results and exact code/evidence commits follow below. No claim that
all historical combined or low-buffer LIVE gates passed; no hardware qualification.

### Implementation checkpoint before final native qualification

The focused ASAN/UBSAN EEL host run exits 0: 10,450 assertions across M4 clocks,
free capture, recording lifecycle, grid timing, M0 and instance ownership. The
pinned ysfx archive itself is reused; this does not claim every instruction in
that third-party archive was sanitizer-instrumented. Actual native error API,
FREE TIME HTTP/overdub (6 tests), Controller policy/host and REVEAL (5 tests)
gates passed. Final committed-source native build and proportional integration
results are recorded in the following evidence checkpoint, not inferred here.
