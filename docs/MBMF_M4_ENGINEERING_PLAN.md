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

### Committed-source regression checkpoint (973cc4f)

`evidence/m4/qualification/results.json` records exact source/binary SHA256 and
all 21 command exit codes. Eighteen commands passed. Three initial failures are
retained, not converted into PASS:

1. `test_phrase_midi.py`: two errors from using the system Python without mido.
   The existing prepared test venv has mido; the identical six tests pass there
   (`phrase-smf-venv.log`). No package installation or assertion changes.
2. `test_native_free_capture.py`: one legacy sequence check assumes the global
   last MIDI event is the new attack. Three fresh runs of the **actual built #85**
   and three of M4 reproduce one failure each. Logged reply is an old Note Off
   `[128,48,0]` while selected occurrences remain active. This is pre-existing
   last-event attribution sensitivity under overlapping short phrases, not proof
   that the new phrase failed to emit. Original assertions remain unchanged and
   the global fixture remains failing. `tests/m4_last_event_diagnostic.py` adds
   only failure context and preserves the original assertions/exit code.
3. Three optional-grid JACK processors: real 8192-sample gap, 18 XRUN notifications,
   max callback elapsed ~300 ms, source safety guard rejected the take. The result
   is NOT PASS. A fair #85 comparison and precise CPU versus scheduling attribution
   remain pending. An initial comparison was interrupted to avoid mixing it with
   a still-running sanitizer compile; it is not usable timing evidence.

The same committed-source campaign passes actual JACK M4 counter/transport tests,
M0 overlap/HOLD-retrigger/LOOP toggle, MOVEMENT cadence/ownership, bounded output
saturation (64 attacks, 64 emergency CCs, explicit fault, source unchanged), plus
Controller, Snapshot, Conductor execution/gestures/groups/persistence, native SMF
interchange and project restart gates. No full combined/Chromium/LIVE matrix was
rerun or claimed green. Native ASAN build/API verification is still pending at
this checkpoint; the earlier instrumented ChainMode/EEL host gate passed.

The original 13,801-byte attached M4 clock/forensics specification has now also
been recovered and read in full, in addition to the later 5,966-byte execution
mission and #85 comment. Remaining native route retirement/restore paths deserve
an isolated fail-closed regression: removing a chain while its JACK port still
exists must not resurrect that retired virtual input. Do this after preserving
#87 evidence, without modifying its tested musical source. No hardware activation.

## Increment 3 — retired virtual source and verified restore transaction

`fix/m4-retired-route-quarantine` is stacked on #87 evidence HEAD `42f364b`.
Three additional tests fail before the fix: orphan source re-enabled during chain
removal, physical bypass restored despite orphan quarantine failure, and physical
restore failures losing the ownership journal. These are production helper paths,
not speculation about a particular synth.

Quarantine now includes previously owned virtual sources and known destination
slots after a chain disappears. Discovery waits for an orphan device to disappear,
never restores its retired virtual receiver matrix, and removes retired outputs
from the desired JACK graph. Physical routes/modes are restored only after
quarantine, with setter/readback verification; failed restoration retains its
journal for retry. An unrelated recycled device slot is never overwritten: if its
identity cannot be proven, restore remains blocked pending graph reconciliation.
This can intentionally leave the selected keyboard isolated rather than risk a
feedback path. No automatic hardware activation or new route destination.

Two old native-source fixture assertions now explicitly model chain removal and
subsequent JACK-device disappearance separately. Their final retirement/mode
assertions remain; a retired virtual receiver staying disabled is the corrected
security contract. All 81 routing/source/installer/adapter/legacy-router tests
pass. Setter traces and three original failures are retained under
`evidence/m4/route-retirement-*` and `retirement-final-setters.jsonl`. Native
lib_zyncore/Oram services themselves are NOT available in Cloud: these are actual
production Python helper calls against captured API fixtures, not hardware proof.
The tested C++/EEL musical engine remains identical to `973cc4f`.

## Latest qualification / review decision

- Native ASAN/UBSAN binary built from M4 code ran the real capture-error API
  test successfully: both overflow/capacity cases, complete rollback and SAVE/LOAD;
  no sanitizer report files. `native-capture-asan.log` is complete (earlier pending
  checkpoint superseded). Existing pinned ysfx static archive is not wholly
  sanitizer-instrumented; no timing qualification from sanitizer runs.
- Three optional-grid processor test **also fails on independently built #85**:
  one 8192-frame audio gap, 5 XRUNs, max callback elapsed 4.329 ms. M4 observed
  an 8192-frame gap, 18 XRUNs and max elapsed 300.379 ms. Both guards reject the
  take. These are single functional runs, not comparable CPU/latency statistics;
  the larger M4 elapsed peak's CPU versus preemption cause remains unresolved.
  See `qualification/followups.json` and `three-grid-base85-isolated.log`.
- One interrupted baseline run is recorded separately and excluded from this
  comparison because a sanitizer compiler was still active.
- `free-time-recorded-source.mid` is produced by the production SMF writer from
  the actual JACK-captured source. Independent mido decoding confirms CH3 Note On
  65/V97 at tick **0**, paired CH3 Note Off/V31 at tick 80060, PPQ 24000.
- No complete combined/LIVE/Chromium success claim. The last-event sequence
  fixture remains a documented pre-existing failure; SMF's missing system-Python
  dependency is resolved by using the prepared venv, not weakening assertions.
- **GO for human review of the focused Drafts; NO-GO for activating native routing
  or claiming a generally qualified V4 release.** Physical storm root cause and
  live graph/matrix audit remain open. All hardware tests: **NOT RUN**.

### Safest next Raspberry Pi action (user only, no deployment)

Keep MB output disconnected. Collect the existing graph read-only:

```sh
jack_lsp -c > /tmp/mbmf-midi-graph-before-review.txt
```

Do not run REC, install these Drafts, reconnect MB or alter native source checkboxes
as part of this action. JACK's visible graph alone cannot show native matrix or
client-internal returns; review DIN/MPK selections, MB/synth input matrices and
seq/step/CV returns with the existing native UI before authorizing a separate
supervised test on an immutable reviewed SHA. No activation commands are supplied.
Projects/schema are unchanged; no deployed rollback is needed for this session.
Before any later approved hardware update, retain the existing runtime/config and
snapshot backup and its known rollback procedure.

### Exact next coding checkpoint

1. Preserve these Drafts and evidence; do not merge #85 or deploy any stack.
2. Diagnose the remaining 3-processor JACK XRUN wall/CPU attribution with existing
   trace infrastructure on an explicitly documented, controlled workload. Do not
   increase buffers or bypass the missed-block safety guard to obtain PASS.
3. Replace the *legacy global last-event attribution* test strategy with real
   per-action MIDI emission evidence in a separate tested increment, preserving
   its musical assertions. The original failing tests remain untouched here.
4. Qualify actual Oram native matrix/JACK reconciliation, including recycled slots,
   only after explicit hardware permission. A blocked restore must never be
   bypassed by unconditionally clearing its ownership journal.

## Published review stack / final handoff

- Draft [#86](https://github.com/petedevries666/midi_human_looper/pull/86),
  `fix/m4-routing-diagnostics`, `523636ad6d3e4694ce3994307553140f70e455c5`.
- Draft [#87](https://github.com/petedevries666/midi_human_looper/pull/87),
  `fix/m4-free-time-clock`, code `973cc4f789cb4fb1df40ea04f31f9952128b89f4`,
  evidence HEAD `42f364b1aebcfb3fbb31548bef64d3b57edd2506`.
- Draft [#88](https://github.com/petedevries666/midi_human_looper/pull/88),
  `fix/m4-retired-route-quarantine`, code/evidence
  `4c23bedbc5320e310a945fe84ea7e7ee48ee172b`; this documentation checkpoint follows.

All are GitHub MERGEABLE against their explicit parents at final inspection,
**still DRAFT**, and nothing was merged. Routing CI passed for #86 (run
38855519244) and #88 (run 38858585149); #87 has no applicable check-run in that
routing-only workflow. Those CI results are not native/global/hardware gates.

During development the old native-source retirement fixture initially failed
1/4 because it expected ownership deletion before its port disappeared. It was
expanded to assert quarantine in that intermediate state and retains its final
mode/retirement assertions after explicit disappearance; this is a deliberate
safety lifecycle correction, not a hidden relaxation of musical assertions.

Final checks: protected original working files 25/25 SHA256 unchanged from session
recovery; production JSFX byte-identical to #85; native engine/ChainMode sources
byte-identical to the qualified `973cc4f` code. No browser screenshots were rerun
because no Web files changed. No installed service, networking/JACK configuration,
LUMAZ, token or physical hardware was touched. Continue from the precise unresolved
checks above, not from a fresh global audit or another M3 implementation.
