# Expressive phrase playback / CONDUCTOR implementation checkpoint

Dependency: PR #44 (`integration/studio-live-rc`, b303193). This branch is the
first executable slice, not the completed four-track CONDUCTOR.

## Implemented

The shared EEL Phrase Engine appends two playback policies to existing ONCE:

- **ONCE / NO RETRIGGER:** PRESS starts at its MIDI timestamp. PRESS while
  running stops owned notes; RELEASE does nothing. PRESS after natural completion
  starts a new pass, including when completion and PRESS occur in one block.
- **PRESS / RELEASE:** PRESS starts immediately, source timing repeats while
  held, and RELEASE stops at its timestamp. Note On velocity zero is RELEASE.
  Additional PRESS while held does not create another voice.

Legacy LOOP=0, ONCE=1 and HOLD=2 retain their descriptors and normalization.
The new descriptor `phrase_playback_policy` (kind 25) is independent: 0 LEGACY,
1 NO RETRIGGER, 2 PRESS / RELEASE. It applies only when legacy mode is ONCE.
This avoids reinterpreting existing Controller/Snapshot three-bin mappings.
Changes use the existing deferred parameter application and Controller ownership.
Changing the policy during playback waits until the Phrase Engine is safe.

The existing 12 voice slots, source event store, instrument router and ownership
ledgers are reused. Held looping advances the same absolute sample position;
there is no new timer or scheduler. Its minimum source period is
`max(128, samplesblock / 8)` samples after TIME DECAY. Admission rejects a shorter
period, limiting a block to eight source cycles plus boundary processing.
Existing source capacity remains 2,048 events per phrase.

Native API requests enter the existing block mailbox: ysfx clears MIDI output
before opening a block, so emitting a Note On from a pre-block command would
lose it. Browser pointer/keyboard RELEASE waits for PRESS acknowledgment and
is not discarded by the pending-request UI guard. Browser timing is block
quantized; physical learned MIDI retains its input offsets.

Both policies conservatively reject active mono/legato or ARP routing. Their
legacy source ownership is insufficient for selective STOP alongside live
sources. The UI reports this rejection. Polyphonic pitch/range/velocity routing
is supported; the shared ownership ledger preserves an unrelated live owner of
the same output channel/pitch. MIDI sustain remains channel-wide: a held physical
pedal may keep released notes audible until that pedal is released.

## Platforms and persistence

- REAPER JSFX and standalone native ysfx execute the same policy code.
- REAPER project serialization, the companion patch Lua script and patch banks
  preserve the policies. JSON schema 8 appends a marker and 16 policy values;
  schemas 1–7 migrate to policy 0 without changing their old modes.
- Portable version 2 carries non-neutral schema-8 policy data. A known all-zero
  extension canonicalizes to schema 7 so legacy revision hashes and restart
  fingerprints remain stable. Unknown fields are not stripped.
- Updated SEND/GET leaves source MIDI unchanged; updated PUSH/PULL transports
  policy configuration. Older readers reject schema 8 / portable v2.
- Native Controller mappings and Snapshots include kind 25. Patch SAVE retains
  committed Controller bases, while Snapshot capture retains effective values,
  as before. REAPER still rejects native-only Controller/Snapshot execution data.
- The native **Zynthian chain adapter remains fixed synchronized LOOP**. Its mode
  controls stay disabled; learned/API gesture playback is explicitly rejected
  rather than silently executed without reliable transport cleanup. This is a
  limitation of this slice, not a claim of Zynthian CONDUCTOR support.

## Automated checks and manual use

Run the focused shared-engine checks after compiling `tests/expression_host.cpp`:

```
expression_host midi_human_looper.jsfx --phrase-gestures
HEADLESS_BINARY=/path/to/midi-headless-engine python3 tests/test_phrase_gestures.py
HEADLESS_BINARY=/path/to/midi-headless-engine python3 tests/test_phrase_gesture_browser.py
```

The gesture harness exercises actual ysfx input/output offsets, not a separate
simulation. It covers one-sample taps, intra-block toggle and natural completion,
loop-boundary releases, repeated presses, live-note overlap, invalid routing,
patch banks, schema-7 migration and actual REAPER-state serialization. Rate/buffer
coverage: 44.1/48/96 kHz and 32/128/512/8192 frames.

Complete software regression command:

```
python3 scripts/combined-test.py --native --browser chromium --timeout 240
```

For desktop dummy JACK, add `--jack` with the documented JACK dependencies.
Do not start that dummy server on a running Zynthian. An XRUN/discontinuity in
this cloud environment cancelled recording during the first combined three-chain
run. A later isolated three-chain run passed, as did the standalone JACK graph
with 8 paired gesture notes, overflow recovery and timestamp ordering. The initial
failure is still recorded; a successful desktop retry does not resolve hardware
qualification. Safety guards were not
weakened. Actual Pi, Zynthian, REAPER GUI, Firefox and Helix validation is pending.

For physical REAPER validation, install this branch's JSFX and companion Lua,
record a phrase and use the existing phrase trigger Learn with a Helix note.
Cycle the JSFX mode label to `1xNR` or `P/R` (the browser uses full names). Test a
short tap, sustained hold, second PRESS, Note On velocity zero and PANIC. Save
both a patch and REAPER project, reopen and verify mode/assignment restoration.
Use a polyphonic chain without ARP for these new modes. Test release with a
physical sustain pedal separately because sustain affects the whole channel.

## Verification recorded for this slice

- Combined native/software/Chromium suite passed: 5,969 shared EEL/GUI/MIDI
  checks, 41 portable MIDI parity checks, Controller core and sanitized host
  checks, project rollback/restart, SMF interchange and browser workflows.
- Focused gesture harness: 153 checks, including rate/buffer combinations.
- Native gesture API: two workflow tests (Controller/Snapshot/patch included).
- Chromium gesture workflow passed, including release behind a pending PRESS.
- Actual desktop JACK graph passed: lifecycle, bounded overload recovery,
  chronological timestamps and 8 paired gesture notes.
- Three native Zynthian-adapter chains with Chromium editors passed in isolation.
  The earlier combined XRUN/discontinuity recording cancellation remains an
  observed limitation. No physical-hardware qualification has been performed.

## Exact next implementation step

**Before adding four-track storage, give each existing voice its own bounded
output ownership ledger and implement selective voice cancellation.** Today
`NOTE_REF_BASE` and `I_ONCE_OUT_BASE` aggregate ONCE output and
`last_trigger_layer` enforces exclusive phrase entry. Four independent track
lifecycles must not be implemented by calling the existing global choke helper.
Add actual shared-engine tests with two voices sharing a pitch/channel and with
a live note, then test cancellation of exactly one voice and instrument deletion.
Keep old exclusive ONCE behavior as the compatibility policy.

Then append explicitly versioned CONDUCTOR configuration and bounded per-track
source storage, with stable track IDs and an explicit single-track conversion.
Attach four tracks to one existing sample timeline, then implement PRESS/HOLD/
RELEASE admission and virtual active-note tracking. Add REVEAL only after unique
destination/channel ownership can be validated against the existing Controllers
and other instruments. Reuse the same sample clock for bounded CC7 fades.
Finally integrate compact track editing, per-track/Format-1 SMF interchange,
project migration/bridge capability checks, the native chain adapter and REAPER
execution, followed by the complete regression and hardware checklist.

**Not implemented:** four-track CONDUCTOR data/execution/editor, configurable
HOLD admission, virtual note reveal, CC7 ownership/fades, per-track MIDI
interchange, CONDUCTOR synchronization/parity and the requested bass/pad
acceptance scenario. No dummy/empty-track events or unsupported UI controls
have been introduced.
