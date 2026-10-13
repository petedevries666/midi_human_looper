# PR B — emitted notes and instance lifecycle

Dependency: PR56 `0e21ac5853a77370d536ecae80f4ed3332854cda`, itself based on
PR50 `25fcb1e458ffdce7286ff4c60cd4546d586e19a4`. Functional contract: PR55
[`73cdee5`](https://github.com/petedevries666/midi_human_looper/blob/73cdee5604992ca3bd68e4c6c3b97c545333b127/docs/movement-phrase-conductor-master-spec.md).
Q1/Q2/Q4 are resolved. This implements ownership foundations, not CONDUCTOR,
FECK, JOIN or PAUSE/RESUME. Q3 future capacity decisions remain open.

## Execution contract

Each admission receives a monotonic, runtime-only ID and a generation. STOP
requires both, within the existing engine-session/CAS scope. Reused voice slots, PANIC, patch replacement and retired instances
invalidate old tokens. The shared EEL implementation runs in REAPER and the
native ysfx host; C++ queues control requests and observes state, without a
second note scheduler. Generations never enter patch data.

Before routing a source attack, reserve a fixed ledger row. After transformations,
record only destinations accepted by `midisend`: channel, pitch and stable
instrument ID, plus the source input claim. Filtered attacks reserve FIFO
placeholders but own no emitted output. Matching Offs consume source-key FIFO
records, including Note On velocity zero, and release the saved output rather
than recomputing current pitch/routing. CC120/123 release only this instance's
claims for the source channel; tombstones prevent later old Offs from cutting
new attacks. Instrument removal invalidates its old claims before slot reuse. Pedal destinations also retain stable instrument IDs
and exact output channels, so deletion cannot leave a stale pedal or release
a surviving destination sharing that channel.

The native JACK adapter retains its existing bounded, timestamp-sorted output
queue and emergency recovery. Ledger acceptance means acceptance by the shared
engine output buffer, not confirmation by a hardware synthesizer. A JACK queue
failure still invokes the existing emergency PANIC. Actual JACK port output is
also asserted in the new integration test.

An Off is emitted only when the last owner of the effective channel/pitch ends.
Physical input, independent phrase instances and legacy LOOP claims participate
in that check. Pedal claims preserve another phrase's or physical player's
sustain. MIDI 1.0 cannot give two simultaneous identical channel/pitch notes
independent audible articulation, nor isolate sustain per logical source on a
shared channel. This retains the existing last-owner release policy; receivers
with a strict stacked-Note-On counter need separate destination channels.

## Admission and bounds

- Legacy ONCE cross-source choke remains explicitly separate and compatible.
  Native legacy admission now uses the existing DSP FIFO: releasing the old
  source before ysfx opened its output buffer previously lost its MIDI Off.
  Its baseline XFAIL denotes a requirement for future independent layers, not
  a hidden change to legacy behavior.
- New shared `phrase_admit_independent(layer,offset)` and headless
  `phrase_play_independent` admit sources without legacy cross-source choke.
  `instance_stop` accepts the returned observation's ID/generation.
- Existing 12 voice slots are reserved before a new attack. A thirteenth request
  returns an explicit refusal, emits no MIDI, and leaves all 12 survivors intact.
- Each owner has 2048 source attack records, reusing the existing source event
  bound. Exhaustion refuses the unrepresentable attack and retires only that
  instance. No global destruction presented as single-voice recycling.
- Independent admission rejects active mono/ARP routes conservatively and cancels
  an independent voice if an unsafe route becomes active during playback. Their
  legacy implementations remain tested, but isolated concurrent mono/ARP
  ownership is **not supported**. No silent fallback or bypass.
- `instanceError`: 2 voice capacity, 3 unsupported/invalid admission, 4 ledger
  exhaustion, 5 exact numeric identity range exhausted, 6 shared output-buffer rejection. `instanceRejected`
  counts refusals. `reservedAttacks` and `ownedOutputs` are distinct;
  `ownershipSupported` explicitly identifies legacy unsafe routes.

There are 12 existing voice owners plus 16 legacy LOOP source owners. Ledger
storage is 1,959,120 EEL cells (15,672,960 bytes, ~14.95 MiB), including
pedal destination claims and the generation queue; it is pre-touched at
initialization; reservation/release uses fixed arrays and source-key FIFOs.
Cleanup traverses at most 2048 records × nine destinations per owner, with 28
existing owners. No allocation, filesystem work, networking or new scheduler
is introduced into the callback. This bounded worst case is **not Raspberry Pi
latency qualification**. Cloud sparse-render measurements are retained in
`docs/evidence/midi-instance-ownership/baseline.json`; they do not set Q3 limits.

## MIDI before / after

Original PR A traces remain in `docs/evidence/conductor-a-baseline.json`.

| Case | Before | B actual MIDI |
|---|---|---|
| Voice saturation | 12 → 1; Off48, On48 | 12 → 12; no MIDI, explicit refusal |
| Legacy choke with physically held48 | Off48, On72 | On72 only; physical release later emits Off48 |
| Independent admission | Legacy path chokes prior source | On48 then On72; no Off48 |
| Targeted STOP with same-pitch physical owner | Prior blanket release was unsafe | No Off until physical owner releases |

The JACK test records `[destination,frame,offset,status,pitch,velocity]` and
requires the exact port sequence: physical On60, instance On60, independent
On62, physical final Off60, targeted final Off62. The first targeted STOP must
produce **no** Off60. Each timestamp must be nondecreasing.

## Validation and remaining scope

Use the binary built from this branch, never PR A's shared comparison binary:

```sh
scripts/headless-build.sh
scripts/combined-test.py --native --jack --browser chromium --timeout 240
```

The native regression runner includes `tests/test_instance_ownership_native.py`;
the JACK runner includes `tests/test_instance_ownership_jack.py`. The EEL suite
includes real emitted MIDI ownership, routed/transposed releases, repeated pitches,
sustain, source-channel clear tombstones, filtered attacks, stale tokens, capacity
reservation, destination deletion/reuse with shared and separate pedal channels,
legacy LOOP, independent LOOP/HOLD cycles, and exact offsets at 44.1/48/96 kHz with
128/256/512/8192-frame blocks. Recording, overdub and SMF fixtures are unchanged.
Controller tests run normally and with ASAN. Additional focused EEL host
ASAN/UBSAN checks link the existing uninstrumented ysfx library; they are not
full-library sanitizer qualification.

Two existing UI counterexamples remain failures and are tested separately using
`tests/conductor_diagnostics/pending_edit.py` and `editor_click.py`. No web UI,
installer, authentication, catalog or schema changes belong to B. No physical
Zynthian/REAPER/Helix validation, merge or deployment has occurred. Native
independent admission is an API foundation, not a new UI or multitrack feature.

Executed results and gate verdict are in the adjacent evidence manifest and logs.

## JACK test startup correction

One full run stopped in the JACK timestamp fixture before the ordering probe
could connect. Controlled 500 ms delay before activation reproduces probe exit
**3** on clean PR50 and B with the unchanged fixture. Socket creation precedes
JACK activation; it is not a readiness guarantee. The fixture now waits for an
actual command/callback round trip before connecting. Its exact timestamp,
same-block and equal-time Note On/Off assertions are unchanged. With the same
forced delay, actual output remains `16,120,120,220,400` in one block.

Reproduce with `tests/conductor_diagnostics/jack_readiness.py` and its accompanying
`delayed_jack_activate.cpp` shared-library shim. The shim affects private Cloud
fixture startup only; it is never installed, used on hardware, or linked into
the engine. Failed global and diagnostic logs remain published. A separate global
run interrupted by an in-session source edit/syntax error is retained as invalid
mixed-source validation; the syntax error was fixed before the frozen rerun.

## Actual output-buffer rejection and recovery

A real 65,536-byte, non-extensible ysfx buffer accepts 4,369 of 5,120 attempted
attacks in the focused fixture. Previously the rest were silently dropped;
a full-buffer CC burst could also lose a scheduled Off after its owner record
was retired. Error 6 now marks this distinct output failure, defers the existing
PANIC to a fresh block, and emits bounded CC123/120 emergency cleanup. Calls
outside ysfx's DSP output window are not classified as buffer exhaustion.

Native processing forwards the shared fault latch into its existing emergency
queue recovery, discarding queued stale attacks. The actual JACK stress fixture
emits 64 partial attacks, then 64 captured emergency CC messages, has no attacks
after emergency cleanup, leaves no stacked receiver notes, and preserves all
2,048 source events. This is an explicit global output-failure PANIC; voice
admission exhaustion (error 2) and per-instance ledger exhaustion (error 4)
retain their isolated behavior. No output capacity or safety guard was increased.

Legacy basic mono/ARP execution remains available through the original path,
with per-instance ownership unsupported. A previously safe legacy voice may
enter that path only with no outstanding ledger/pedal claims. Unsafe transitions
with outstanding claims retire the affected source explicitly. These restrictions
are deliberate and are not claims of safe arbitrary layered mono/ARP routing.

## Final executed gate

Production build: `ffdc4d0ba829ba07b3e6c40d9c947ab31f70aa76`.
[Manifest, hashes and all outcomes](evidence/midi-instance-ownership/summary.json).

| Check | Result |
|---|---|
| Complete combined native/JACK/Chromium regression | PASS, exit 0 |
| Actual EEL/GUI/MIDI | 18,383 checks PASS |
| Capture / free-capture SMF | 18 / 36 fixtures PASS |
| Controller normal and ASAN | 162,709 core + 558 adapter checks each PASS |
| Focused actual EEL ownership host ASAN/UBSAN | 6,698 checks PASS |
| Separate three-chain JACK, no Chromium load | 2/2 PASS |
| Controlled private callback interruption | PASS guard: error 1, stopped capture/playback, no active notes/output overflow |
| Pending-command UI counterexample | FAIL exit 1, unchanged signature and successful idle control |
| Telemetry EDIT counterexample | FAIL exit 1, unchanged signature and successful idle control |
| Legacy cross-source ONCE | Explicit XFAIL retained in shared/native contexts; separate independent tests PASS |

**Conditional GO for scoped PR B review.** This is not a release or physical
hardware qualification. The failed/interrupted earlier global runs, diagnostics,
actual MIDI before/after and their classifications are retained beside the final
logs. No new runtime regression was found after the fixes. Source/hash verification
confirms all six web files, the entire JSFX `@gfx` section and the original 25
issue54 working files are unchanged. No merge, installation or deployment occurred.
