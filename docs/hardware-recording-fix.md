# Hardware recording follow-up

Branch `fix/native-recording-origin` is stacked on PR #48 (`92a3416`), which
requires #47 and #44. It does not merge PR #45: that PR explicitly rejects
native-chain gesture playback and introduces schema-8 policies. Reusing its
standalone UI is insufficient for native HOLD ownership.

## Implemented slice

Native first takes now retain the selected playback mode. The first actual
positive-velocity Note On establishes a common source-time origin. All later
captured events subtract that origin, preserving intervals, durations, channels,
velocities and overlapping notes. Earlier controller events are retained at zero
in their original order. Orphan releases are excluded by the existing bounded
capture ownership table. A note crossing the fixed capture end receives a release
at the shifted end, not at the old transport phase. Existing overdubs retain their
source timeline; previously saved phrases are not rewritten.

Recording still arms at the next synchronized two-bar boundary and uses the
existing bounded window. This patch removes leading time from new source data;
it does not change synchronization, quantize individual events, or repair export
in isolation. Selecting ONCE remains ONCE after REC. Explicit PLAY starts its
one-shot playback; REC no longer changes the mode to obtain looping playback.

The gate now applies to native timing V1 as well as V2. REAPER and standalone
paths leave the native gate disabled and retain their existing behavior.

Both the ysfx CMake setup and application compilation request `-fsigned-char`.
This is a compiler setting, not a third-party source edit. Existing ARM64 ysfx
builds must be rebuilt with this setting; adding it only to the application cannot
correct an already compiled WDL library.

## Reproduction and evidence

`tests/run_host_tests.sh` runs actual EEL recording through ChainMode for LOOP and
ONCE, timing V1/V2, and three arbitrary arming phases. Attacks arrive 128 samples
after the grid origin. Stored attack time must be zero and release time must be
128 samples. It then exports those actual memory fixtures through the production
SMF writer and parses MIDI delta ticks: all twelve attacks must be at tick zero.
The fixture checker uses only the Python standard library and existing parser.

```sh
YSFX_SOURCE=/path/to/pinned/ysfx tests/run_host_tests.sh
python3 scripts/combined-test.py --native --jack --browser chromium --timeout 240
```

JACK tests launch private desktop dummy servers, not the physical Zynthian.
Physical V4/Oram ARM64, sustain, Helix and REAPER tests remain required. This is
not a release candidate or an instruction to deploy unreviewed code.

## Exact next implementation steps

1. Add a dedicated content-only CLEAR operation. Do not call `clear_layer`, which
   also resets mute, solo and base velocity. Use selective phrase note ownership
   for live clearing; otherwise reject while playing/recording with an explicit
   finish/stop requirement. Add confirmation in phrase options, persistence and
   exported-empty-SMF tests, and the required real browser screenshots.
2. Adapt shared HOLD press/release to native ChainMode and its command mailbox.
   Validate phrase-selective cleanup for both loop and voice-pool ownership,
   including sustain and repeated pitches. Then enable browser pointer/keyboard
   release and native MIDI release; retain the unsupported flag until proven.
3. Implement a separate reversible runtime updater using the installed config
   and pinned release directories. Preserve registration, token, ports and data;
   build/validate outside the running runtime, atomically switch and roll back
   failed startup. Test fresh/existing/repeated updates and failed activation.
4. Run the complete combined suite on the finished stack and physical acceptance
   checklist. No automatic deployment or merge.

CLEAR, native HOLD and the one-command updater are not implemented by this slice.
