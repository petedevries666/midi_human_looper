# PR B — emitted notes and instance lifecycle

Dependency: PR56 `0e21ac5853a77370d536ecae80f4ed3332854cda`, itself based on
PR50 `25fcb1e458ffdce7286ff4c60cd4546d586e19a4`. Functional contract: PR55
[`73cdee5`](https://github.com/petedevries666/midi_human_looper/blob/73cdee5604992ca3bd68e4c6c3b97c545333b127/docs/movement-phrase-conductor-master-spec.md).
Q1/Q2/Q4 are resolved. This implements ownership foundations, not CONDUCTOR,
FECK, JOIN or PAUSE/RESUME. Q3 future capacity decisions remain open.

## Execution contract

Each admission receives a monotonic, runtime-only ID and a generation. STOP
requires both. Reused voice slots, PANIC, patch replacement and retired instances
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
- Independent admission rejects active mono/ARP routes conservatively. Their
  legacy implementations remain tested, but isolated concurrent mono/ARP
  ownership is **not supported**. No silent fallback or bypass.
- `instanceError`: 2 voice capacity, 3 unsupported/invalid admission, 4 ledger
  exhaustion, 5 exact numeric identity range exhausted. `instanceRejected`
  counts refusals. `reservedAttacks` and `ownedOutputs` are distinct.

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
