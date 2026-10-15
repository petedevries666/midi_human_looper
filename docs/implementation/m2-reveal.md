# M2b — native REVEAL / GATE implementation checkpoint

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

Checkpoint only: final regression and screenshot qualification are in progress.
Earlier actual JACK/browser run demonstrated mute-before-On, exact 12000-sample
HOLD at 48 kHz, GATE timeline continuity, source STOP, physical takeover, replacement
of a real CC7 MOVEMENT, and same-block PANIC. The strengthened short-tap test and
four native tests must pass on final code before delivery. Do not treat existing
trace files or this checkpoint as final qualification.

One new fixture initially attempted to import CC7 using the notes-only SMF path;
that request was rejected and its status was not checked. The corrected fixture
uses the production legacy patch loader and explicitly checks success. No import
validation was relaxed. Functional Cloud dummy JACK at 8192 frames does not qualify
small-buffer deadlines, ARM64, synth CC7 support or physical Zynthian safety.

Next: finish focused tests, full combined regression, sanitizer gates, generate
and inspect the required five-size browser PNG campaign, commit evidence and open
M2b as a draft stacked on #81. No JOIN, FADE or hardware installation in this slice.
