# Hardware recording follow-up

Branch `fix/native-recording-origin` is stacked on PR #48 (`92a3416`), which
requires #47 and #44. It does not merge PR #45: that PR explicitly rejects
native-chain gesture playback and introduces schema-8 policies. Reusing its
standalone UI is insufficient for native HOLD ownership.

## Implemented fixes

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

`tests/run_host_tests.sh` runs actual EEL recording through ChainMode for LOOP, ONCE and
HOLD, timing V1/V2, and three arbitrary arming phases. Attacks arrive 128 samples
after the grid origin. Stored chord attacks must be zero; later releases at 128/192/384 samples and
a later attack at 256 samples retain their intervals, channels and velocities.
Leading CC data precedes the chord at zero. The production SMF writer exports
these actual memory fixtures; MIDI delta ticks are checked for all eighteen takes.
The fixture checker uses only the Python standard library and existing parser.

```sh
YSFX_SOURCE=/path/to/pinned/ysfx tests/run_host_tests.sh
python3 scripts/combined-test.py --native --jack --browser chromium --timeout 240
```

JACK tests launch private desktop dummy servers, not the physical Zynthian.
Physical V4/Oram ARM64, sustain, Helix and REAPER tests remain required. This is
not a release candidate or an instruction to deploy unreviewed code.

## CLEAR and native HOLD

CLEAR MIDI is a confirmed, content-only action in phrase options. It preserves
names, settings, other phrases and Instruments. Playback, held notes, recording
and armed recording reject it: STOP/PANIC and FINISH first. Live selective clearing
is deliberately unavailable until loop-specific note ownership is proven. Tests
cover cancellation, empty SMF export and SAVE/LOAD restoration.

Native HOLD uses PR #45's shared bounded voice rendering and selective release,
without importing its schema-8 policies. A PRESS starts immediately, repeated
PRESS while held does not restart, and RELEASE stops the source voice and releases
its owned notes/sustain. Browser pointer, cancellation, focus loss and keyboard
edges use the existing native mailbox; learned MIDI Note Off / velocity zero uses
the same EEL release path with its event offset. A short tap retains both edges.
STOP/PANIC cancels queued presses. Saturated edge queues retain RELEASE via
a bounded per-phrase release mask; rejected extra presses cannot lose cleanup. Phrase changes retain the existing global
voice-pool choke semantics; this is not a multitrack CONDUCTOR implementation.

Native HOLD is supported only for polyphonic non-ARP routes. Mono/legato and ARP
admission is explicitly rejected rather than pretending selective release is
safe. Native browser controls consult the actual engine capability before enabling
HOLD. Physical channel-wide sustain still affects notes on that channel: RELEASE
does not forcibly lift an independently held live pedal. PANIC remains the emergency
cleanup. REAPER retains its existing latched HOLD behavior; native repeat-while-held
is an explicit host difference, not a claim of complete parity.

The updater and rollback commands are documented in
[zynthian-runtime-update.md](zynthian-runtime-update.md). They preserve installation
registration and configuration and restart the UI-owned runtime only after
preflight/checkpoint/backup. The Zynthian UI restart interrupts performance; JACK
and unrelated services are not restarted. Physical Oram/ARM64 validation remains
mandatory.

## Automated validation

- Actual shared-EEL recording at eighteen mode/timing/arming combinations, including
  chords, channels, staggered durations, rests, leading CCs and exported MIDI ticks.
- Native held playback/release at 44.1/48/96 kHz and 32/128/512/8192-frame blocks,
  short taps, PANIC, source sustain cleanup and explicit ARP rejection.
- Actual dummy-JACK three-processor isolation and single-instance three-channel
  fanout, held playback/release, source capture and ordered output.
- Actual Chromium pointer/keyboard/short-tap and learned MIDI release against
  the running native engine; confirmed CLEAR and persistent empty export.
- Update filesystem transactions, failed activation, repeated activation, rollback
  retaining musical data, interrupted activation journal and actual native preflight.
  Service transitions are mocked; no hardware service restart is claimed.

Browser network loss prevents delivery of a release command. The autonomous engine
continues independently; use a physical release or STOP/PANIC if connectivity is
lost while holding a browser trigger. Offline physical MIDI performance does not
require the browser. This network limitation is explicitly pending stronger
browser-owned admission leases, not concealed as complete disconnect safety.

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
