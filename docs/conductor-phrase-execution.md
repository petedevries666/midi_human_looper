# PR D minimal: real PHRASE CONDUCTOR execution

Base: PR #58 `b82b9a1c80066d2c3f4322bb5c4f6a5bf7860ddc`, then #57/#56/#50.
Contract fully reread: PR #55 `73cdee5604992ca3bd68e4c6c3b97c545333b127`,
including resolved Q1/Q2/Q4. Q3 remains open. No merge or hardware deployment.

## What executes

A configured Smart Switch can execute ordered PHRASE STEPS through
**SEQUENTIAL / IMMEDIATE / PRESS INSTANT**. First PRESS selects STEP 01; each
subsequent admissible PRESS selects the next position; the final position wraps
to STEP 01. A repeated source on two positions is still two distinct STEPS.
Changing STEP never stops previous voices. Each admission uses B's independent
instance ID/generation, actual transformed output ownership and bounded renderer.

The existing physical Note/CC Smart Switch entry, MIDI Learn, quarantine, command
THRU policy and TEST mailbox are reused. Sequenced PRESS bypasses delayed gesture
classification and DOUBLE consumption. A physical held button still has one PRESS
edge until its RELEASE; two rapid PRESS/RELEASE pairs advance twice. TEST is a
PRESS-only manual preview, available even when hardware input is disabled or
unassigned. Unsupported DOUBLE/HOLD TEST requests report result 4 instead of
silently invoking a legacy action. No simulated input is presented as a captured MIDI output.

Several PHRASE LAYERS in a STEP start at the same input sample offset. Before any
attack, the shared engine checks safe routing, nonempty source/duration, bounded
loop period, exact instance-ID range and available slots for the complete batch.
Insufficient slots reject the whole STEP, without stopping survivors or partially
starting a layer. Rejected admission leaves the cursor unchanged.

Supported local overrides: LOOP/ONCE/HOLD playMode, base velocity, velocity decay
and TIME DECAY. Velocity/time repeat counting stays in B's existing independent
admission domain; legacy repeat counters are unchanged. Base velocity overrides
are per instance; decay/time factors are captured during admission. Temporary
source values are restored before returning, without changing committed source
parameters or Controller ownership. Inherited base velocity keeps its existing
live behavior. Source MIDI events are never copied or rewritten.

LOOP repeats until STOP/PANIC/targeted cancellation. ONCE completes naturally.
HOLD repeats while held; physical RELEASE ends only that switch's held instances,
not its continuing ONCE/LOOP instances or another switch/live player. API
`conductor_release` supplies RELEASE for PRESS-only TEST workflows. It uses the
existing 16-entry DSP mailbox and a fixed 16-switch release fallback mask, so a
full mailbox cannot silently lose RELEASE. Deleting the owning Smart Switch
selectively retires its Conductor voices before identity removal.

Mute/Solo eligibility is checked at admission. For active Conductor voices,
subsequently muted attacks retain silent FIFO placeholders; their historical
Offs cannot cut a physical or another instance's note. Source Offs still clean
previously emitted attacks. Legacy rendering is unchanged when no Conductor
owns the voice. Sustain and exact channel/pitch release use B's existing ledger.

## Configuration handoff and runtime costs

C's version-1 document remains authoritative. The native **control worker**
validates it and resolves UUIDs through its explicit source registry. It compiles
numeric records into runtime RAM beyond `INSTANCE_STORAGE_END`; none enter
schema-7 memory, patch banks or portable timing conversion. Missing UUIDs become
diagnostics, not guessed indices. A STEP with surviving references can play those
layers while reporting its missing references; a completely missing STEP emits
nothing and advances normally.

Installation uses the existing STOP-only, paused configuration transaction.
All RAM cells/pages and pointers are resolved/touched by the worker before
processing resumes. A failed patch/Controller activation retains the old runtime
plan as well as C's saved document. LOAD/factory NEW reset runtime selection and
start no playback. Runtime selection, voices, owner tags and release masks are
not persisted. Worker restart retains the engine's current plan/configuration.

The callback performs no JSON/UUID parsing, vector growth, I/O or new locks.
Existing voice/header cells carry switch ownership and a local base-velocity
value. API RELEASE uses cached pointers, not RAM/variable registration in the
callback. Scheduling and chronological JACK output remain the existing engine's
responsibility; no second MIDI scheduler or host-side note generator is added.

Runtime layout: 16 existing switch headers × eight cells, and each STEP has four
header cells plus 12 five-cell admission records (64 cells / 512 bytes per STEP).
Four STEPS use 3,072 runtime bytes including the switch headers; backing EEL RAM
uses its existing page allocator. Configuration storage is bounded by C's existing
control/file byte ceiling, not a newly chosen STEP count.

The execution batch derives its 12 records from the **existing 12-voice budget**.
A document with more than 12 resolved populated PHRASE LAYERS in one STEP is
preserved but cannot execute in D, even if some are currently muted. This is a
conservative slice restriction, **not a final Q3 LAYER/storage decision**. No voice
capacity increase, eviction policy or arbitrary MOVEMENT rate is introduced.

`tests/conductor_execution_cases.hpp` measures 100 real 128-frame ysfx processing
blocks after ten warmup blocks for one/two/twelve-layer admissions. Raw medians,
p95 and maxima are in the evidence logs. These sparse-source, Cloud CPU numbers
include admission/rendering, not worker parsing, stop cleanup, full-density
source stress, JACK driver latency or Pi scheduling. They do not set a latency
promise or Q3 limits. Future phases must measure dense workloads/worker handoff
and propose their own resource decisions; B's output-overflow tests remain gates.

## Explicit unsupported configurations

No MOVEMENT, JOIN, REVEAL, FECK, END OF PHRASE, RANDOM/SHUFFLE, EXCLUSIVE gesture,
HOLD-entry admission, action BLOCK execution or new Conductor authoring UI.
Independent mono/legato/ARP remains refused by B's safety guard.
Only PRESS, NEW_INSTANCE and TRIGGER overrides are executable in this slice;
other advanced overrides/configurations are retained but explicitly rejected at
execution. They never fall back to a legacy phrase or approximate another mode.
Legacy switches without a Conductor continue through their original paths.

Existing legacy Reset/Reset-on-reentry fields do not implement Conductor cursor
reset in D. PANIC/STOP clean voices but are not advertised as FECK's replay policy.
The C data model and unsupported data remain intact for later phases.

## Observation/API

`GET /api/v1/conductor` exposes the model, missing references, minimal supported
execution list and authoritative runtime observations. Existing state `switches`
adds a `conductor` object: step (one-based, zero before first PRESS), steps,
result, missing, admitted. Legacy switches show zeroed fields, not stale state.
Result codes: 0 success, 1 missing references skipped, 2 capacity refusal,
3 unsafe/invalid source, 4 unsupported execution, 5 instance numeric-ID refusal.
An API TEST acknowledgment is not proof of an attack; use observations and MIDI
port capture. Configure through C's existing `conductor_commit` protocol with
current session/revision while stopped, then use existing TEST or learned MIDI.
No unauthenticated endpoint, token change or browser dependency is added.

## Tests and actual MIDI evidence

- Shared production EEL: four physical-style PRESS/RELEASE pairs, fifth wrap,
  actual attacks `48,52,56,60,48`, no premature Off, simultaneous layers,
  individual STOP, 12-slot saturation, atomic two-layer rejection, unsafe ARP
  refusal, missing UUID silence, local velocity/time modes and muted FIFO safety.
- Native callback/HTTP: four STEPS/wrap, 12-slot refusal, multi-layer and missing
  reference observations, unsupported REVEAL rejection, HOLD RELEASE, local source
  isolation, patch SAVE/LOAD with no autoplay.
- **Actual private JACK**: a separate bounded source client sends footswitch
  MIDI into the real engine; a receiver captures its output port. Required attacks
  are `60,62,64,65,60`, then simultaneous `60,62` at one frame/offset. Footswitch
  note 110 never leaks to output. The first targeted same-pitch STOP emits no Off;
  PANIC uses existing CC64/123/120 emergency receiver cleanup; later targeted
  STOP emits Off60, legacy STOP emits Off62. Receiver state ends empty, timestamps
  are chronological and LOAD emits no new attacks.
- Full A/B/C regression, capture/SMF/overdub, Controller/Snapshot/portable, strict
  child sanitizer gate and Chromium suites are run and recorded separately.

Test commands:

```sh
export HEADLESS_BINARY="$PWD/.build/midi-headless-engine"
scripts/headless-build.sh
scripts/conductor-execution-test.sh
python3 tests/test_conductor_execution_native.py
scripts/combined-test.py --native --jack --browser chromium --timeout 240
```

JACK runs require the existing extracted JACK environment/driver paths and a
private test server. `scripts/headless-test.sh` builds the real probe and includes
the JACK Conductor test. Do not start dummy JACK on a musician's live Zynthian.
The Cloud functional JACK run uses 48 kHz / 8192 frames and does not qualify
physical ARM64/V4/Helix/Firefox performance.

REAPER executes the same shared EEL admission/renderer in the harness, but its
project/patch adapter still cannot load C's Conductor document. Original data is
preserved with explicit refusal as in C. **No REAPER Conductor end-user parity
claim** is made. No schema, installer, Web UI or issue #54 modifications.

See `docs/evidence/conductor-phrase-execution/` for exact commands, hashes, raw
MIDI traces, measured costs, failures and final phase gate. The two pre-existing
UI counterexamples remain separately reported rather than hidden in green tests.
