# Issue #18 implementation checkpoint

Resume feature work from branch **`feat/humanizer-engine`**; use **`fix/jack-midi-ordering`**
for the first Zynthian demo. Do not rebuild the project
from main or duplicate #19–#22. Nothing has been merged automatically.

## Published dependency chain and implemented work

`main` → #19 `feat/zynthian-runnable-mvp` → #20 `feat/module-descriptors-editor`
→ #21 `feat/controller-policy-core` → #22 `fix/zynthian-first-demo`
→ #23 Controller integration `feat/controller-host-integration` → #24 timestamp
delivery correction `fix/jack-midi-ordering` → HUMANIZER foundation `feat/humanizer-engine`.

The current integration includes 16 logical note/CC sources, one exclusive Learn
lease, explicit conflict confirmation, FORGET, 32 mappings, real parameter application,
DIRECT/PICKUP/GLIDE/SLEW, idle/release/command return, snapshots, ownership arbitration,
curves/bends, generic editing, phrase TIME/VEL DECAY targets, configuration-v1 persistence
and separate guarded REAPER base export. Extra Transformer instances and deferred
held-note bases are tested. The runnable JACK host remains independent of the browser.

[First-test commands](zynthian-first-test.md) cover build, read-only JACK preflight,
exact MIDI ports, LAN token and Firefox demo. [Controller boundaries](controller-engine-integration.md)
cover the headless extension, capacities and remaining compatibility work.

## Last complete regression

Native: 2,764 checks and three stable concurrent GUI render hashes. HTTP/native:
14 baseline plus nine Controller integration tests. Registry: three tests. Lua: five.
Controller core: 160,381 synthetic checks, plus 523 adapter checks, both normal and
ASan/UBSan. Three Chromium browser suites pass. Actual named dummy JACK graph passes
normal routing, deliberate FIFO saturation with channel release/PANIC recovery,
and exact same-block timestamp/tie delivery. HUMANIZER foundation: 3,153,134 algorithm
checks, normal/sanitizers, plus 436 EEL2 reference checks included in the native total.
Desktop callback timing remains diagnostic, not a realtime Pi guarantee.

```sh
HEADLESS_BINARY="$PWD/.build/midi-headless-engine" YSFX_SOURCE="$PWD/.build/ysfx" \
  NATIVE_PATCH_FIXTURE=/tmp/midi-native-patch.json \
  python3 scripts/combined-test.py --native --jack --browser chromium
```

Use a Python virtualenv with `lupa playwright selenium`; Chromium path defaults to
`/usr/bin/chromium`. JACK test needs `jackd` and development headers. `--jack` starts
only a named desktop dummy server: never run that option on a working Zynthian.

## Outstanding work, in priority order

1. Physical Raspberry Pi/Zynthian + Helix + stock Firefox acceptance. No device/SSH
   access is available. Stock Firefox automation times out in this container and
   Playwright's Firefox downloads hit a domain filter; neither is a passing test.
2. Complete Controller compatibility: migrate legacy expression curves/assignments
   atomically with DIRECT defaults, then shared JSFX/project persistence and REAPER
   policy processing. Current safeguards preserve original headless files through
   explicit base export; full bidirectional new-policy support is not implemented.
3. HUMANIZER at both Phrase and Instrument scopes, following #11's design. The deterministic C++/EEL2 foundation is implemented and tested, but **the module
   is not connected to the scheduler or routing**. Continue on `feat/humanizer-engine`;
   [exact next edits](humanizer-implementation-checkpoint.md) identify pairing,
   timing queues, ownership, schema and editor tasks.
4. VELOCITY CURVES, following #12, on `feat/velocity-curves-engine` after Humanizer.
   **No VELOCITY CURVES implementation has been delivered.**

## Concrete next engine edit

Audit `send_to_instruments()` and its ordered chain, `arp_process_instrument()`,
`process_phrase_trigger()`, LOOP playback and the `VOICE_*` ONCE/HOLD scheduler in
`midi_human_looper.jsfx`. The voice already captures TIME DECAY and VEL DECAY factors
and stable Instrument IDs. Humanization must retain original event identity and pair
Note On/Off by voice plus original note/event identity; a post-JACK-output filter
cannot recover that information and is not a valid substitute.

Implement deterministic per-note/group hashes with separate timing/velocity streams,
then a bounded absolute-time scheduler with generation cancellation, before exposing
HUMANIZER. Preserve actual T=0 groups, retain nonzero first attacks, paired durations,
FIXED/EVOLVING iteration identity, loop spill, STOP/PANIC and delete/load ownership.
Append versioned module configuration without shifting frozen legacy payload offsets;
extend JSFX/Lua validation and both banks together. Register Phrase and Instrument
scope descriptors; do not add another hardcoded page.

For VELOCITY CURVES, register an independent stable Transformer instance and separate
response curve from the expression curve controlling AMOUNT. Reuse the shared bend
math and browser curve component, then the existing REAPER multipoint editor with
independent target addressing. Process future Note Ons only, preserve velocity-zero
Note Off semantics, and test all 1…127 inputs at AMOUNT 0/0.5/1 plus stacking/ARP/order,
patch round-trips and instance deletion. Do not represent a design document or a
standalone algorithm test as a completed module.
