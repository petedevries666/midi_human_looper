# #76 focused runtime corrections

Base: `integration/zynthian-release-candidate` at `58ce482`.
Fix branch: `fix/rc-live-runtime-gates`. No deployment, merge or release.
These are actual x86_64 Cloud/private dummy-JACK measurements at 48 kHz,
non-realtime JACK, not Raspberry Pi qualification. No browser/edit/SAVE/LOAD
inside LIVE measurement windows. Setup/load occurs before the window; shutdown
PANIC occurs afterward. The producer binary, source hash, event counts, active
sources and complete action schedule are recorded in each summary. Functional
exit 0 does **not** mean zero XRUNs or a qualified deadline.

## 1. Reproduced measurement defect and correction

The minimal IDLE control has no PHRASE or MOVEMENT. LIGHT has one of each,
25 Hz, three MIDI PRESS/RELEASE pairs at 0/4/8 s, no physical CC stream. The
existing detailed tracer calls `CLOCK_THREAD_CPUTIME_ID` at each stage and
`getrusage(RUSAGE_THREAD)` at callback boundaries. That diagnostic code executes
inside the callback and can itself stall. Its stage wall endpoints exclude the
clock call while the CPU endpoints include it, falsely blaming the following
musical stage.

Reproduced LIGHT/256: 75.172 ms CPU, 76.833 ms elapsed. Clock-read brackets account
for **76.704 ms**; PERFORMANCE wall is **0.648 microseconds**, but its attributed
CPU is **75.081 ms**. No input or command was admitted in this callback. This is
not evidence of 75 ms spent calculating a MOVEMENT. The raw row and enclosing
worker CPU samples for the after comparison are in
[evidence/rc-live-fixes/peak-attribution.json](evidence/rc-live-fixes/peak-attribution.json).
The former 26.85/104/265 ms peaks cannot all be retroactively assigned a cause
from their older broad brackets; those cases remain unproven.

Correction: `--rt-trace` now uses monotonic wall brackets and a separate worker
sampling the JACK thread CPU clock every 10 ms. **No thread-CPU clock or
getrusage calls in the default traced callback**; the unit test intercepts both
actual calls and asserts zero. Normal untraced operation does not read clocks for
these diagnostic brackets. Optional `--rt-trace-cpu` retains the intrusive mode
for explicit reproduction, never as the default qualification measurement.
Per-callback CPU is unavailable in wall mode, reported as JSON null (raw legacy
CSV CPU slots remain zero). Worker CPU measures the whole JACK thread, not an
individual stage. Only an enclosing CPU interval gives a callback upper bound.

Twenty-four fixed stage slots now distinguish cycle-clock, output-buffer lookup,
output clear, recovery, queued output, input-buffer lookup/count/event fetch,
input copy/dispatch, Controller tick, JACK transport query, chain tick and
MOVEMENT rendering. Child operation brackets overlap the original ten stage
brackets; **do not add parent and child totals**. No callback logging/allocation,
no new MIDI event ordering, scheduling or musical parameter policies.

### Focused before/after, 20 seconds per case

| Case | Wall p95 / p99 / max, ms | Callback CPU max | XRUN | Wall overruns |
|---|---:|---:|---:|---:|
| Before, detailed IDLE/256 | .142 / .533 / 19.538 | 17.948 ms (intrusive) | 100 | 1 |
| Before, detailed LIGHT/256 | .117 / .464 / 76.833 | 75.172 ms (intrusive) | 45 | 1 |
| After, wall LIGHT/256 | .092 / .288 / 4.830 | unavailable | 10 | 0 |
| After, wall LIGHT/512 | .133 / .508 / 14.469 | unavailable | 9 | 1 |
| After, wall STRESS/256 | .625 / 1.096 / 8.097 | unavailable | 12 | 1 |
| After, wall STRESS/512 | .665 / 1.297 / 4.244 | unavailable | 1 | 0 |

The after LIGHT/512 14.469 ms callback is enclosed by a worker interval using
**at most .865 ms CPU**, so at least 13.604 ms was off CPU. This is measured
scheduling delay, not a guess based on the host being Cloud. Conversely, the
STRESS/256 8.097 ms peak has an enclosing CPU interval of about 8.96 ms: it cannot
be dismissed as scheduling delay. Its EEL bracket remains a stress timing risk.
These short windows do not prove a universal performance speedup.

Independent negative control: only JACK buffer acquisition/clear and the same
wall tracer, **no application engine/EEL/Controller**. At 256: p99 2.498 us,
max 65.344 us, 0 XRUN. At 512: p99 3.765 us, max 81.548 us, **10 XRUN**, no callback
deadline overrun. Some XRUN notifications occur independently of MBMF; this does
not excuse every application deadline miss. The final complete matrix must be
reported separately on the delivered HEAD, including every failure.

## 2. Real chronology versus JACK clock ambiguity

The receiver now writes actual callback cycle, cumulative receiver sample and
XRUN count beside every event. Optional eight-column diagnostics preserve the
existing five-column fixture contract for other tests. No MIDI sorting/filtering
has been added to the receiver.

Actual reproduced pair (frame, offset, status, data1, data2, cycle, sample, XRUN):

```
159744 64 144 61 100 151 38400 20
159744 48 176 20  66 152 38656 20
```

JACK repeated frame 159744 in two consecutive callbacks. Absolute frame+offset
regressed; actual callback order and cumulative sample+offset did not. Another
actual repeat occurs in the corrected 512/STRESS capture. This is timestamp
ambiguity, not proof of a producer emission-order violation. The analyzer checks
**every** offset, callback identity, same-callback order, cycle/sample consistency
and cumulative chronology. Producer diagnostics still check every successful
`jack_midi_event_write` for exact within-callback ordering. Wrong same-callback
order and corrupt receiver positions fail deterministic tests. Clock repeats,
jumps and raw timestamp regressions are retained/reported separately; this does
not make absolute JACK transport timing trustworthy through an XRUN.

## 3. STOP / UPDATE ownership boundary

Previously `checkpoint()` verified stopped state, then the updater stopped the UI.
A physical PRESS/CC or browser command could resume music between those operations.
A second check still has the same race. The native processing thread now grants
an owner-specific admission lease (op 50) only at a stopped callback boundary:
no incoming/backlogged MIDI, pending musical command in the same cycle, notes,
queued output, sustain, PHRASE/REC/overdub, MOVEMENT, morph, held or pending Smart
Switch. Existing STOP/PANIC behavior is preserved; UPDATE does not force a stop.

While fenced: no physical MIDI admitted or buffered; musical/config commands
refused; Controller/legacy writers and musical execution frozen. PANIC/read/save
remain available, and owner-authenticated restore is allowed. PANIC cannot release
the lease. Wrong owners/sessions cannot release it. The owner is never exposed in
HTTP state or accepted as an HTTP command field.

The worker atomically publishes a startup fence and acquires every managed native
processor under a worker-only startup file lock. Adapter startup shares that lock
until ready, and newly created/restored processors start fenced. Checkpoint is
captured **inside** the boundary. Activation, health checks and automatic rollback
remain inside it; rollback failure retains the fence. RECOVER after a completed
activation with interrupted release performs release only, without switching
executables again. No locks/I/O/JSON parsing are added to the MIDI callback.

Nine native tests cover actual held-note/REC refusal, held empty Smart Switch,
frozen Controller GLIDE, concurrent startup, partial acquire rollback, stale
checkpoint race, restart fencing and failed rollback recovery. Real JACK input
at 256 verifies suppressed notes/CC/sustain/PRESS while closed, no deferred attacks,
owner checks and resume. Actual emitted Note Ons: **62, 66, 67**, never the gated
60/64. Service restart/health are peripheral fixtures; native leases and MIDI are
production paths, not fabricated output. Raw MIDI is committed.

**Compatibility / limitation:** older binaries/adapters without the managed
admission capability are rejected before activation. The first reviewed bootstrap
of this native+adapter pair must use the existing reviewed setup workflow; an old
unsafe runtime cannot gain this boundary without being replaced. Rollback to an
incompatible old candidate is refused by preflight. Portable project schemas and
routing are unchanged. The existing updater still restarts the **Zynthian UI
service**, interrupting all UI-managed chains, not just MBMF. JACK service is not
restarted. This limitation requires a stopped performance and explicit review;
this PR does not redesign Oram process hosting.

## Reproduce / gates

Use the prepared Cloud environment from AGENTS.md, pinned native dependencies and
an existing checkout. Never run private-server fixtures on the performing Pi.

```sh
scripts/headless-build.sh
scripts/realtime-trace-test.sh
"$TEST_PYTHON" tests/test_midi_cycle_diagnostics.py
"$TEST_PYTHON" tests/test_update_admission.py
scripts/admission-jack-test.sh
MOVEMENT_RT_TEST=tests/movement_live_profiles.py scripts/movement-realtime-test.sh \
  --output /tmp/mbmf-live-focused --buffers 256,512 \
  --profiles LIVE_LIGHT,STRESS --seconds 20
# Explicitly intrusive historical reproduction:
MOVEMENT_RT_TEST=tests/movement_live_profiles.py scripts/movement-realtime-test.sh \
  --output /tmp/mbmf-live-intrusive --buffers 256 \
  --profiles IDLE,LIVE_LIGHT --seconds 20 --detailed-cpu
scripts/jack-idle-control.sh --output /tmp/mbmf-no-engine --seconds 20
# Only after targeted corrections pass, on final delivered HEAD:
"$TEST_PYTHON" scripts/combined-test.py --native --jack --browser chromium \
  --web-access --timeout 240
MOVEMENT_RT_TEST=tests/movement_live_profiles.py scripts/movement-realtime-test.sh \
  --output /tmp/mbmf-live-final --buffers 512,256 --seconds 20
```

Keep build/browser jobs separate from timing measurements. All LIGHT/NORMAL/STRESS
activity is explicitly scheduled in `tests/movement_live_profiles.py`; recorded
source/instance maxima and notes/CC per second must accompany timing results.
Immutable focused traces/logs and SHA256 manifest are under
[evidence/rc-live-fixes](evidence/rc-live-fixes/sha256.json). They precede the final
combined run; final HEAD and final results are supplied in the draft fix PR.
No new screenshot campaign: no Web DOM/CSS changed. REAPER remains frozen.
The original 25 issue-54 WIP files in the original checkout remain untouched;
shared tracked runtime/adapter entry points necessarily receive the isolated
UPDATE fix in this integration checkout.

## Controlled V4 qualification, after review only

No automatic deployment instructions executed here. Save/export the current
project and record installed SHA. At rest, install the reviewed native+adapter
pair through the existing setup/rollback procedure. Verify three routed synth
channels, Helix PRESS and expression, sustain then STOP/PANIC. Without browser,
run LIGHT then NORMAL at 512 and 256; measure wall/CPU, XRUN, emitted notes/CC and
physical audio continuity. Try UPDATE while holding a note/REC/Smart Switch:
refusal must precede any service restart. Release everything, verify fenced
activation/restart/recovery and saved project restore. Test interrupted update on
a recoverable test snapshot, never during a performance.

Review of the concrete fixes is possible; **concert reliability is not qualified**
while stress deadline misses and Cloud XRUNs remain. No claim of physical V4,
ARM64, Oram restart or hardware rollback validation. No phase G, merge or release.
