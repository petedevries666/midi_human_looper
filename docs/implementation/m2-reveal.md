# M2b — native REVEAL / GATE implementation

Base: draft #81 (`e8785f3`). Branch `feat/conductor-reveal`, stacked on
`feat/conductor-press-hold`. No deployment or merge. REAPER remains frozen.

## Musical contract

REVEAL requires gesture HOLD. At PRESS the existing independent PHRASE instance
starts normally, with CC7=0 emitted before its initial notes. HOLD restores the
previously observed effective CC7, or **127** when unknown. LATCH survives RELEASE;
GATE remasks on RELEASE while the same instance/timeline continues. Early RELEASE
stops only the hidden instance admitted by that gesture. Shared-channel CC7 is
explicitly warned about and allowed; it cannot isolate two instruments on the same
MIDI destination/channel. Sources containing their own CC7 are refused before STEP
attacks, rather than introducing competing volume writers. Missing references keep
the existing diagnostic and never bind to another source.

## Implementation boundary

No patch schema change: existing entry/release overrides are compiled into the
internal STEP record (72 cells, previously 68). Twelve PHRASE instance slots remain.
CC7 leases reuse Controller Host tokens and MOVEMENT's existing raw-CC identity.
Capacity is reserved before attacks. Physical CC7 passes intact and takes over;
stale HOLD/RELEASE/cleanup never reacquires a replaced token. A losing MOVEMENT may
retire its target only if releasing its own token succeeded.

Private native bus-15 control markers carry timestamp, instance ID and channel mask
through the actual DSP output, and are consumed before JACK output. They are never
external MIDI. Native pre-DSP cleanup reuses the existing bounded host queue because
ysfx's midisend APIs cannot emit outside its DSP context. Chronological control and
MIDI output use the existing bounded callback batch. There is no second scheduler,
JSON parsing, blocking I/O or allocation added to the callback. Stored models remain
worker-side.

## Defects reproduced during implementation

- Old native PANIC could enqueue 2048 dummy Note Offs plus pedal messages ahead of
  real subsequent attacks. PRESS/PANIC in one block exposed this backlog. Native
  cleanup now releases registered notes/ARP voices plus bounded channel safety
  messages. Frozen REAPER keeps its old path.
- Native observed `activeNotes` could remain nonzero after CC120/123 cleanup,
  causing later configuration transactions to reject with 409. Observation now
  clears the corresponding channel's held counters on those actual emitted events.
- An old MOVEMENT cleanup could retire a raw-CC target after a different token had
  taken ownership. Conditional retirement preserves the winning REVEAL owner.

## Validation status

Final qualification is recorded in [the evidence report](../evidence/m2-reveal/README.md). The strict combined gates remain red; this is a draft for code review, not a qualified release.
Earlier actual JACK/browser run demonstrated mute-before-On, exact 12000-sample
HOLD at 48 kHz, GATE timeline continuity, source STOP, physical takeover, replacement
of a real CC7 MOVEMENT, and same-block PANIC. The strengthened short-tap test and five native tests now pass on the delivered implementation. See the evidence report for actual raw results and retained failures.

One new fixture initially attempted to import CC7 using the notes-only SMF path;
that request was rejected and its status was not checked. The corrected fixture
uses the production legacy patch loader and explicitly checks success. No import
validation was relaxed. Functional Cloud dummy JACK at 8192 frames does not qualify
small-buffer deadlines, ARM64, synth CC7 support or physical Zynthian safety.

Draft #82 is stacked on #81. Focused native/JACK, sanitizers and five-size visual evidence are committed. Next: qualify external/shared-channel sustain and full MIDI-buffer burst cleanup, then reconcile the old-contract test gates before advancing M3. No JOIN, FADE or hardware installation in this slice.

## Physical acceptance (after explicit review/installation approval)

1. Use a bass on CH1 and a CC7-capable pad on CH2. Keep other parts off CH2;
   the warning deliberately permits sharing and does not promise audio isolation.
2. Record/import a long bass PHRASE and a pad containing a sustained note at zero
   plus another note later. Keep their source MIDI channels; assign both to STEP1.
3. Bass: PRESS/TRIGGER. Pad: HOLD/REVEAL/LATCH. DONE, SAVE, reload stopped.
4. Short press: bass starts immediately; pad receives hidden notes, then RELEASE
   releases those notes. No HOLD reveal should occur later.
5. Long press: bass starts immediately; pad starts silently, reveals at the
   configured HOLD threshold without reattack; LATCH keeps playing after RELEASE.
6. Change only pad REL to GATE. HOLD, RELEASE: pad remutes; the later source note
   remains at its original time. No instance restart or bass stop.
7. Send physical CH2 CC7: it must pass intact and replace the REVEAL lease. Later
   RELEASE/STOP must not restore a stale value over this physical controller.
8. Source STOP, natural completion and PANIC: no hanging notes or stale volume
   automation. Repeat with overlapping gestures, sustain and the intended actual
   receiving synth. Unknown CC7 restoration is intentionally 127, per user choice.
9. Repeat SAVE/restart/LOAD and verify silence until the next trigger. Disconnect
   the browser during playback. Capture ARM64 CPU/XRUN and small-buffer timing
   separately; Cloud screenshots and 8192-frame dummy JACK do not establish these.

FADE/JOIN remain outside this slice. A synth ignoring CC7 cannot support audible
REVEAL through this MIDI mechanism. No installation commands are authorized here.

## Regression discovered and corrected before delivery

The broader MOVEMENT fixture exposed a real change in this branch: two adjacent
PRESS starts for one target at the same sample emitted `[25,102]` rather than the
established latest-owner-only `[102]`. Chronological native control processing
now defers initial emission across adjacent same-timestamp MOVEMENT starts. Other
controls remain barriers. The unchanged real JACK fixture now verifies `[102]`,
all four exact CC cadences, physical takeover, soft restart and final values.

Separately, one old cyclic probe run attributed CC26 offsets 6800 then 528 to the
same receiver frame (a backwards delta of 6272 = 8192−1920). The MOVEMENT runner
now reuses the existing acyclic source/sink probe, with one `jack_last_frame_time`
snapshot per receiver callback and pre-faulted observation pages. No recorded
output is sorted, filtered or retimed. Original chronology and exact cadence
assertions remain unchanged. This fixes diagnostic attribution; it is not proof
that general Cloud scheduling/XRUN risks have disappeared.

## Admission work bounds and timing qualification

At admission, CC7 preflight and mask capture each scan at most 2048 stored events
per PHRASE, across the existing maximum 12 voices: at most 49152 event records for
these two new scans in a full STEP. This is a structural bound, not a measured CPU
budget or permission to raise capacities. Runtime storage is fixed/preallocated.

An earlier functional Cloud run recorded REVEAL max callback wall time 48.7241 ms
with 4 XRUN notifications; the expanded sustain/browser run recorded 12.2213 ms
with 3 notifications, and MOVEMENT 40.8713 ms with 2 notifications. Both used
48 kHz/8192 frames, non-real-time private dummy JACK. Earlier runs overlapped
browser regression campaigns and native sanitizer compilation; expanded fixtures
include setup/configuration, actual browser editing and subsequent MIDI testing. Exact MIDI cadence assertions passed; output
queue overflow was zero. CPU time was not separately sampled in these fixtures.
These measurements **do not** establish isolated engine cost, a cause for the
XRUNs, safe 256/512-frame performance, or Raspberry Pi qualification. Do not call
this live-qualified or reuse these maxima as an admission policy.
