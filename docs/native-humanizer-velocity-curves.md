# Native HUMANIZER / VELOCITY CURVES: executable foundation

This incremental PR is **not** an installed or playable transformer. It adds
portable allocation-free helpers plus an executable C++ test. It does not
change the frozen REAPER JSFX, native engine callbacks, live instrument menus,
patch storage, Zynthian configuration or the current ECHOCITY runtime.

- `native_expression::VelocityCurve`: normalized response graph, 2–16 ordered
  points, piecewise linear mapping, amount blending, Note On 1..127, velocity
  zero preserved. Settings are data structures, not registered patch schemas.
- `native_expression::Humanizer`: 0..2000 ms range, ±2000 ms bias, uniform or
  bounded six-draw Gaussian, deterministic independent timing/velocity streams,
  fixed/evolving instances, 0..100% velocity scatter.
- `delayedSample` is an absolute-sample helper. The caller must pair by original
  voice identity. Its clamping alone is **not sufficient** to preserve note
  duration for negative shifts near origin; the future integration must capture
  a single effective offset per note, preserve off velocity, and define
  lookahead/phrase anchoring explicitly.

Build standalone test:
```sh
c++ -std=c++17 -O2 -Wall -Wextra -Werror tests/native_expression_transforms.cpp -o /tmp/mbmf-expression-test
/tmp/mbmf-expression-test
```

## Missing before this is a musician-ready feature
1. Reconcile PR #25 seed/differential behavior, reuse #93 scheduler/ledger and
   source journal; handle overlapping pitches, sustain, phrase boundary and
   all lifecycle cancellations without real-time allocation.
2. Wire native module IDs, transform ordering, snapshots/patch migration,
   Controller descriptors, editor curve and timing rails, APPLY and SAVE/LOAD.
3. Instrument-domain GROUP vs NOTE scatter, bounded future scheduling and
   measured overflow/rejection/recovery.
4. Real engine/JACK generated MIDI tests through 2 s timing delays, subsequent
   ARP and ECHOCITY, STOP/PANIC, and all reset/rollback paths. Hardware requires
   separate permission and qualification.
5. Never claim that early attacks can occur on already received live MIDI input
   without explicitly introduced lookahead latency.
