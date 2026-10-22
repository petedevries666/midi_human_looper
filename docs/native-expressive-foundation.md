# Native extreme HUMANIZER + VELOCITY CURVES: first coding increment

Branch based on PR #93, issue #94. This is a **C++ runtime foundation**, not yet a
playable instrument transformer. It does not modify the frozen REAPER JSFX.

## Implemented
- Deterministic signed timing modulation, -2000 to +2000 ms bias, 0..2000 ms
  jitter, bounded Gaussian/uniform distributions, FIXED/EVOLVING random seed and
  coherent GROUP versus dispersed NOTES timing.
- Velocity variation 0..100%, independent random stream and untouched velocity
  zero; 16-point velocity response curves, inverted shapes, linear interpolation
  and 0..100% AMOUNT.
- `PairRuntime` reuses the native-note scheduler and output ledger for
  complete recorded pairs. `StreamRuntime` additionally accepts a live Note On
  before its Note Off, captures one shift per voice, pairs overlapping equal
  pitches oldest-first, preserves Note-Off velocity, handles module/instrument
  cancellation and downstream channel clears, and uses fixed preallocated event
  storage. Both have bounded admission and explicit PANIC recovery contracts.
  `liveLookaheadMs` makes live latency explicit; without enough lookahead a
  negative shift clamps to the arrival time and is never emitted in the past.
- Real C++ tests compiled against the repository's native scheduler in the
  dedicated GitHub CI workflow. Coverage includes deterministic FIXED versus
  EVOLVING timing/velocity, invalid-parameter fail-closed behavior, curve blend
  endpoints, streaming Note On/Off pairing, release velocity, equal-pitch overlap,
  module-scoped cancellation and channel clear.

## Important limits
- The adapter accepts *known note pairs*. It is **not connected** to live
  incoming MIDI, instrument transformers, phrases, snapshots or Zynthian synths.
  No Web editor, module descriptor, Controller mapping or patch persistence yet.
- Live Note Off is not known at Note On time, so the production adapter must
  acquire voice identity and seal delayed releases safely. Do not pretend a
  note-pair test is a live-recording proof.
- Negative times are clamped to the currently available clock boundary;
  actual lookahead requires a phrase pre-scheduler or explicit live latency.
  No event can be emitted before it is received in real time.
- The scheduler's maximum event horizon is 60 seconds. A pair beyond that
  limit is rejected in full. Same channel/pitch instances are coalesced by
  the existing output ledger, as in ECHOCITY.
- An isolated PairRuntime must **not** be wired in series with ECHOCITY by
  treating their output ledgers as independent physical MIDI ownership. Review
  unified ownership and transformer continuation before engine integration.

## Required next PR slices
1. Bridge to native source/voice lifecycle with a shared output ledger and
   explicit transformer stage placement. Prove real JACK instrument playback,
   sustained/repeated notes, phrase loop boundaries and ECHOCITY interactions.
2. Register stable module IDs / native descriptors and versioned patch schema
   with migrations. Capture fixed seed/iteration and active parameters per voice.
3. Web module picker, compact HUMANIZER parameters and VELOCITY CURVES point
   editor, transaction-safe Apply/Cancel and SAVE/LOAD/snapshots.
4. Qualification: true synthetic JACK, queue overload and real Zynthian/Helix
   musician testing; do not claim live-ready before those gates.

Repro:
```sh
g++ -std=c++17 -O2 -Wall -Wextra -Werror -pedantic -Iheadless tests/native_expressive_transformers.cpp -o /tmp/mbmf-native-expressive
/tmp/mbmf-native-expressive
```
