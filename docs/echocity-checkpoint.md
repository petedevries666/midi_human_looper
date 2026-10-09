# ECHOCITY implementation checkpoint

## Status: scheduler foundation, not an ECHOCITY module

ECHOCITY cannot yet be inserted or configured. This branch is a prerequisite
implementation; it does **not** satisfy the musician-facing definition of done.
No ECHOCITY patch data is written, so existing schema-7 patches remain unchanged.
Do not present this branch as the completed core or merge it as a released feature.

## Repository audit and dependency choice

Base: main `17e0ac6`, containing the stable runnable host, module descriptors,
Controller policy/host integration, and JACK timestamp-ordering fix from PRs
#19–#24. Open implementation PR #27 adds native Zynthian chain registration but
is optional for a Transformer inside the shared JSFX engine. Draft PR #25 is a
HUMANIZER algorithm foundation, not working playback; neither is included here.
Draft design PRs #11 and #12 are independent of ECHOCITY. No OS, LUMAZ, hardware
services or Zynthian configuration are modified.

Integration points:

* `midi_human_looper.jsfx`: `send_to_instruments`, `send_once_to_instruments`,
  `tf_pitch`, `tf_velocity`, `route_emit_note`, `arp_process_instrument`.
  Existing pitch and velocity processing is grouped, not a generic ordered
  event pipeline. ARP captures notes in a separate final-stage hook. Delaying
  the final MIDI output would bypass the required downstream-stage behavior.
* `headless/registry.py`, generic web editor, Controller host bindings:
  extend the shared contracts; do not create another editor or MIDI Learn core.
* `payload_addr`, project serialization, companion Lua patch IO, native Model:
  schema 7 freezes the six legacy type/slot dimensions and payload addresses.
  Append a versioned section with stable instance IDs instead of increasing
  those legacy constants or repurposing CC MOD configuration.
* `headless/engine.cpp`: retains the preallocated, stable timestamp/ordinal
  JACK output sort. Scheduled EEL events use this existing output path.

## Implemented shared runtime

The EEL engine owns a fixed min-heap of 512 pending events and a pool of 256
paired-note voices. Pair admission reserves both attack and release or rejects
both. Runtime pages are initialized outside processing; no callback IO, locks
or additional host scheduler are introduced. Heap order is absolute sample
position followed by admission order. A zero-duration pair attacks before its
release. Events at a block's right edge wait for the next block.

A voice captures Instrument ID, optional Transformer ID, output channel and
pitch. Reused slots have different generations, so stale releases cannot kill a
new voice. Sounding notes use the existing per-Instrument ownership ledger;
repeated same-pitch owners release physically only when the final owner ends.
Ownership leases defer normal structural/parameter edits until completion.
Instrument deletion cancels that Instrument's voices; disabled or missing owners
are polled every block. PANIC and phrase STOP cancel all scheduled voices.
Runtime does not enter patches or snapshots. The horizon is 60 seconds; the
counter is bounded below the exact-integer limit of an EEL double.

Internal DSP-only API:

```
scheduled_pair(gi, module_id, absolute_on_sample, absolute_off_sample,
               channel_0_to_15, pitch_0_to_127, velocity_1_to_127, next_stage)
scheduled_start(gi, module_id, absolute_on_sample, channel, pitch, velocity, next_stage)
scheduled_seal(gi, module_id, voice_token, absolute_off_sample)
scheduled_cancel(gi_or_minus_one, module_id_or_zero, block_offset)
```

Admission returns 1 or 0; `scheduled_rejected` counts refusals. Cancellation
compacts stale heap entries immediately. These functions are **not GUI APIs**;
future editor commands must pass through the existing audio-owned command path.

Deliberate foundation restrictions:

* Only final POLY continuation (`next_stage == TRANSFORM_SLOTS`) is accepted.
  Other continuation positions are rejected, never silently bypassed.
* MONO and ARP admission is rejected. Their stateful note lifecycle has not been
  generalized. This is not a freely placeable Transformer implementation.
* `scheduled_start` reserves an attack and a 60-second watchdog release before
  the duration is known. `scheduled_seal` fills that release exactly once, only
  for the correct owner/token. Late releases clamp to the current block start;
  gate extension is clipped to the original watchdog. ECHOCITY still needs
  bounded source-note tokens linking each source release to its echo voices.
* Scheduled ownership is currently phrase-origin; STOP cancels all scheduled
  tails. Add explicit source provenance before live/phrase selective cancellation.
* Tempo changes do not retime absolute queued sample positions. A future musical
  mode must define tempo-change policy and calculate each generation from the
  shared host tempo. Freeze, transport-reset policy and per-module GUI actions
  are not implemented.
* Individual cancellation uses the existing note router, not a new sustain
  engine. A full ECHOCITY sustain/channel-mode policy remains mandatory.

## Validation

`tests/run_host_tests.sh` executes the complete JSFX under ysfx, using a temporary
callback fixture for scheduler cancellation. The fixture is never shipped in
production. Tests exercise admission, channel/pitch snapshots after edits,
block edges, zero-duration ties, repeated notes, chords, reverse heap admission,
capacity, cancellation releases, generation reuse, unsafe continuation/ARP
rejection, MIDI bounds, fixed horizons, tempo changes, bypass, patch exclusion,
PANIC, independent Instruments, deletion and STOP.

`tests/test_jack_graph.py` additionally runs the real host and JACK graph with
three reverse-admitted channel pairs; it checks exact offsets, chronological
output and correct next-block releases. Existing out-of-order/tied timestamp
and overflow emergency-release tests remain active.

Reproduce on a development machine (not by starting a second JACK server on
Zynthian):

```sh
YSFX_SOURCE=/path/to/pinned/ysfx tests/run_host_tests.sh
HEADLESS_BINARY=/path/to/midi-headless-engine \
YSFX_SOURCE=/path/to/pinned/ysfx \
python3 scripts/combined-test.py --native --jack --browser chromium
```

Build/setup requirements remain in `docs/zynthian-first-test.md`. The executable
loads the current JSFX at startup. Dummy JACK and Chromium are development
validation; no physical Raspberry Pi, Helix, external synth, real REAPER or
Firefox validation is claimed.

## Next implementation sequence

1. **Stage continuation and source lifetime**: shared ordered dispatch by stable
   stage ID, captured Note Off routing, source provenance, source-note token ledger integrating the reserved Note Off
   start/seal API. Preserve the
   legacy processing path for existing patches. Define supported MONO/ARP
   placement explicitly and test delayed downstream changes at emission time.
2. **ECHOCITY CORE**: stable independent instances; dry/wet, milliseconds/sync,
   first offset, feedback plus explicit repeat termination, gate/gate decay,
   velocity decay, channel ping-pong, pitch step. Real live/phrase engine tests,
   chords, overlap, sustain, Note On zero, edits, removal and transport cleanup.
3. **ADVANCED ECHOCITY**: shared deterministic seeded generator; channel sequence,
   drift/wrap/bounce/stop/random; velocity ping-pong/curves/accents/random;
   pitch sequences/scales/bounds; groove and up to 16 bounded taps. Define taps
   relative to each generation, and snapshot queued events at admission.
4. **UI, CONTROLLERS, PERSISTENCE**: descriptor-driven primary/advanced sections,
   transactional DONE/CANCEL, lightweight sequence preview; existing Controller
   sources/mappings/takeover/return and Smart Switch actions; append versioned
   schema across JSFX/Lua/native/editor/project restore. Unsupported platforms
   must preserve configuration and report capabilities. Test reconnect/restart,
   independent instances, migrations, controller output and Firefox.
5. **CREATIVE MODES AND HARDENING**: six presets configuring one engine; bounded
   Freeze capture/release/admission/evolution; overload policy, cleanup under all
   lifecycle transitions, combined suite, actual JACK integration and precise
   Raspberry Pi/Firefox/REAPER test procedure.

Do not call ECHOCITY complete until all five stages and the requested real
engine tests are implemented. Do not auto-merge any implementation PR.

## Resume point

Next branch: `feat/echocity-stage-continuation`, based on
`feat/echocity-scheduled-events` after its scheduler review. Start with the shared
JSFX stage dispatcher and source-token ledger, not a browser-only descriptor.
Do not use PR #25 or #27 as mandatory dependencies. The scheduler APIs and tests
are already present; extend them rather than adding another timer or event queue.
The remaining ECHOCITY module, advanced transforms, UI/controller/persistence
integration and Freeze work are all unimplemented at this checkpoint.

## REVERSE addendum — advanced feature after the stable core

REVERSE is an ECHOCITY section, not another Transformer. These are implementation
requirements, **not implemented capabilities**. They must not postpone or change
basic forward echo behavior. All dimensions use the shared scheduler, instance
IDs, note ownership, descriptor editor, Controller mappings and Smart Switch
commands. This reverses MIDI sequencing and transformations; it does not reverse
synthesizer audio, samples, attacks or release tails.

### Reverse sequence

Capture a bounded per-instance window in milliseconds or host-tempo beats/bars.
Provide NORMAL / REVERSE / ALTERNATE playback. Freeze the window's sample endpoint
and tempo at capture start; subsequent tempo changes affect the next window,
not already captured note times. Report capture and finalization latency in the
editor and transport diagnostics. Non-clocked free-time capture remains available.

Represent captured notes as paired source tokens with onset, duration, channel,
pitch and velocity, not as an independently reversed list of raw MIDI bytes.
Replay onset groups in reverse chronological order, keeping simultaneous attacks
simultaneous and retaining each note's duration. Define reversed onset as
`latest captured onset - source onset`; the new release is that onset plus the
original duration. This is musical onset-order reversal, **not** a byte-stream
reversal or strict geometric reflection of both endpoints (which would split
chord attacks when note durations differ). Polyphony and overlapping notes retain
independent tokens; every release uses its own emitted channel/pitch.

Boundary policy: capture attacks in `[window start, window end)`. Notes already
held before capture are excluded by default. Attacks exactly at the right edge
belong to the next window. After closing admission, finalize crossing notes from
their corresponding source releases, using a bounded tail wait. On timeout,
truncate unresolved durations explicitly and report the truncation. Account for
this extra latency rather than silently losing releases. STOP, PANIC, transport
reset, deletion or bypass cancel capture/finalization and pending playback.

Before enabling capture, set and test fixed limits for captured pairs, overlapping
windows, tail-wait duration, playback voices and total pending events. Reverse
must share the core pool/budget; no second unbounded scheduler. Reject or stop
capture as a whole when it cannot retain pairing. Never drop a captured Note Off
alone. Sustain and channel-mode messages require an explicit policy consistent
with the core, not arbitrary reverse-byte playback.

### Reverse echo envelope and trajectories

Independently reverse velocity, gate, accent and pitch trajectories. Evaluate the
same configured finite progression at reversed indices; velocity reversal allows
crescendos. Do not infer repeat lifetime from velocity or feedback amplitude.
Increasing values still obey explicit repeat count, voice/event limits, MIDI
bounds, gate watchdog and termination rules. Infinite/Freeze operation reverses
within a bounded configured cycle, never across an undefined infinite array.
Test linear/exponential/logarithmic/multipoint curves and accents in both
orientations. Gate reversal never changes the release of an already emitted note.

### Reverse routing

Channel step, channel ping-pong, ordered channel patterns and pitch sequences
have independent FORWARD / REVERSE directions and optional ALTERNATE per feedback
cycle. Define the cycle's endpoint before scheduling its events. Snapshot each
queued event's direction, output channel and pitch. Changing direction or routing
cannot retarget its release. Preserve existing wrap/bounce/stop-at-end semantics;
reverse a ping-pong cycle's traversal rather than adding duplicate endpoint taps.
Seeded random behavior stays reproducible; it is not mislabeled as reversible
unless a finite generated cycle is stored and traversed backwards.

### Reverse mix, editing and persistence

Provide independent normal/reverse contributions. Define MIDI mix using velocity
scaling, with zero contribution excluding events; any probabilistic inclusion is
explicit, seeded and optional. MIDI mix is not an audio crossfade. Each included
stream gets its own voice token even when channel and pitch coincide. The shared
ownership ledger prevents one stream's release from prematurely ending the other;
STOP/PANIC cancels both streams and their pending releases.

Expose capture window/sync, sequence mode, reverse enable, each direction and
normal/reverse mix through the same descriptor-driven advanced section and
transactional DONE/CANCEL workflow. Controller/Smart Switch enable, direction,
capture/clear and mix controls reuse existing source/mapping/takeover/return and
command dispatch. Persist all settings with versioned ECHOCITY configuration,
independent instances and backwards-compatible defaults (Reverse disabled).
Runtime capture/voices are not implicitly serialized as permanent phrase data.
Unsupported platform adapters preserve configuration and advertise capability.

Required actual-engine/JACK regressions: reversed chords with unequal durations,
overlapping/repeated pitches, capture-edge attacks, held-in/crossing/truncated
notes, free-time and beat/bar windows, tempo changes before/during/after capture,
NORMAL/REVERSE/ALTERNATE modes, independent envelope/routing directions, crescendo
bounds, normal/reverse duplicate ownership, controller edits, save/load, multiple
instances, bypass/deletion/STOP/PANIC/transport resets and capture/playback overload.

Sequence: stabilize the shared scheduler and forward ECHOCITY core first, then
add trajectory/routing reversal to the advanced engine. Deliver captured-sequence
Reverse and mixed-stream playback as a separate tested advanced PR once the live
source-token ledger and bounded Freeze lifecycle are established. No Reverse UI
may imply usable capture until the actual engine and cleanup tests are complete.
