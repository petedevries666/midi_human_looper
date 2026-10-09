# HUMANIZER implementation checkpoint: deterministic foundation

**Incomplete module.** This branch adds executable C++ and importable EEL2 algorithm
implementations. Neither is connected to phrase playback or Instrument routing yet.
There are no HUMANIZER controls, scheduling queues, schema changes or persistence
claims. This is the first implementation slice after design #11, not completed PR D.
Use `fix/jack-midi-ordering` for the first Zynthian demo.

## Implemented and proven

`headless/humanizer.hpp` and `headless/humanizer-eel.jsfx-inc` implement the same
unsigned 32-bit seeded hash, scope/instance/phrase/group/note/iteration identities,
independent timing/velocity streams, FIXED/EVOLVING selection, paired timing shift,
T=0 protection, bounded velocity variation and zero/disabled transparency.
EEL2 uses 16-bit multiplication limbs to preserve exact unsigned arithmetic despite
floating-point storage. Extreme seeds and iteration IDs agree with C++ exactly.
All EEL scratch is local; no GUI/audio scratch or mutable global PRNG is introduced.

Timing groups use original simultaneous attack identity, while velocity uses original
note/event identity. Changing timing amount does not reshuffle velocity draws.
For a naturally later attack, clamping retains at least sample 1; the same clamped
shift applies to its paired Note Off, preserving the duration after TIME DECAY.
The velocity helper is for Note Ons only; the future dispatcher must preserve Note
Off velocities and status. Velocity-zero Note On remains zero. No original event
stream is mutated by these helpers.

UNIFORM uses one signed uniform. BOUNDED GAUSSIAN is a documented six-uniform
bell-shaped approximation with support [-1,1], not an unbounded Box-Muller draw.
A distribution test caught correlated stream IDs during implementation; avalanche
mixing fixes that and passes the center-concentration invariant.

Tests: 3,153,134 algorithm checks across 1,000 seeds, both scopes, both variation/feel
modes, duration factors and MIDI velocities, normal and ASan/UBSan. The native harness
adds 436 EEL2 differential/anchor/velocity checks; the complete native total is 2,764
with the existing three stable concurrent rendering cases. These results do **not**
prove actual event scheduling, voice ownership, PANIC or module persistence.

```sh
scripts/humanizer-test.sh
SANITIZE=1 scripts/humanizer-test.sh
YSFX_SOURCE="$PWD/.build/ysfx" tests/run_host_tests.sh --humanizer
HEADLESS_BINARY="$PWD/.build/midi-headless-engine" YSFX_SOURCE="$PWD/.build/ysfx" \
  NATIVE_PATCH_FIXTURE=/tmp/midi-native-patch.json \
  python3 scripts/combined-test.py --native --jack --browser chromium
```

## Exact next edits on this branch

1. Add immutable recorded Note On/Off pairing by original event index and voice,
   including same-pitch overlap and orphan releases. A channel/pitch-only cache is
   insufficient. Do not mutate the recorded event arrays.
2. Integrate phrase timing at LOOP and ONCE/HOLD scheduling sites (currently around
   lines 2720/2790 in `midi_human_looper.jsfx`), after existing TIME/VEL DECAY semantics.
   Capture seed/config/iteration per voice or iteration so parameter edits cannot
   change the paired Note Off displacement after its Note On has been emitted.
3. Add a bounded absolute-time event queue with stable tie ordering, iteration/voice
   generation cancellation and owned-note release on STOP/PANIC/LOAD/deletion. Extend
   voice lifetime for tail spill. Already fixed JACK timestamp delivery is necessary
   but does not replace this scheduler.
4. Integrate Instrument HUMANIZER with stable Transformer IDs and deliberate stage
   ordering. `route_emit_note`, `send_to_instruments`, `send_once_to_instruments` and
   `arp_process_instrument` own current note accounting. Do not wrap only final
   `midisend`: suppressed overlapping Note Offs and delayed retriggers require the
   logical ownership identity before physical output. Define live-gesture anchoring
   when no phrase origin is available, and verify before/after-ARP behavior or expose
   a tested restriction explicitly.
5. Append versioned shared module storage and update JSFX/Lua schema validation, both
   banks, project serialization and native PatchModel together. Freeze all schema-7
   prefix addresses. Register Phrase/Instrument descriptors and generic editor hooks;
   then expose the feature and complete actual MIDI/patch/lifecycle tests.

Current engine/Controller work remains intact. VELOCITY CURVES follows only after
these lifecycle hooks are safe; its response curve and AMOUNT expression curve must
remain independent. Do not present this foundation as either completed new module.
