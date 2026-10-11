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

1. CLEAR is implemented as a content-only, revision-checked maintenance operation
   with confirmation in phrase options. It preserves names, parameters and other
   phrases. Playback, held notes, recording and armed recording reject CLEAR;
   explicitly STOP/PANIC and FINISH recording first. Live selective clearing
   remains deferred until phrase-selective loop ownership is proven. API/browser
   tests cover rejection, cancellation, empty export and SAVE/LOAD restoration.
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

Native HOLD and the one-command updater are not implemented by this slice.
CLEAR is available in phrase options and requires a stopped, disarmed processor.

## Physical recording acceptance after review

Back up the current project first. On the reviewed runtime, choose an empty
phrase and ONCE. With transport already running, arm REC at an arbitrary point,
wait for the synchronized capture window, wait about half a second, then play a
chord and a second note after a deliberate rest. Finish recording. Verify ONCE
is still selected. Export that phrase and import it at project start in REAPER:
the first chord must start at item-relative tick zero, with its original note
lengths and the rest before the second note intact. Repeat with LOOP and different
arming phases. Then overdub an existing phrase and confirm its original notes do
not move. Repeat with multiple MIDI channels and notes held across capture end;
STOP/PANIC must release all audible notes. Record the actual running revision,
sample rate, JACK period and any reported capture discontinuity with the result.
Do not suppress discontinuity errors or relax safety guards to complete a take.
