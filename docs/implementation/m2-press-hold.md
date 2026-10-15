# M2a — native PRESS / HOLD layer admission

Implementation branch `feat/conductor-press-hold`, draft #81, stacked on #80.
Engine/compiler/editor code `8a131d5`. This is a playable increment of M2,
**not completion of REVEAL or of the master specification**. No hardware deployment.

## Actual behavior

- PRESS admits PRESS PHRASE/MOVEMENT blocks immediately. HOLD blocks wait for
  the existing Smart Switch threshold, measured on its sample clock, not browser
  timers. The threshold uses the existing configured 100–5000 ms range.
- HOLD admits its blocks once, on the selected STEP, without restarting PRESS
  instances. STEP changes leave earlier admitted independent instances alive.
- RELEASE before threshold cancels pending HOLD. At exact threshold, HOLD is
  recognized before RELEASE. Note On velocity zero is also RELEASE.
- ONCE/LOOP/latched PLAY MODE HOLD are independent of trigger gesture HOLD.
  Existing ONE_SHOT PHRASE/MOVEMENT layers survive RELEASE. Unsupported GATED,
  JOIN, REVEAL and other advanced combinations are refused, not approximated.
- TEST TAP starts PRESS. TEST HOLD admits the pending HOLD phase of that same
  STEP once; it does not advance the sequence. TEST DOUBLE remains unsupported.
- STOP ALL PHRASES, PANIC, switch deletion and configuration replacement cancel
  pending admissions. STOP ALL PHRASES still leaves already-running MOVEMENTS.
- Existing twelve-voice refusal is preserved. A HOLD refused at saturation emits
  no attack and does not recycle or destroy earlier owners.

## Implementation and persistence

The existing validated document's `trigger` override is reused; no new persistent
schema. The generic block properties expose INHERIT / PRESS / HOLD. DONE uses
existing revision/session conflict checks, CANCEL does not commit. Source settings
are untouched. SAVE/LOAD does not persist held/pending gesture state.

Worker-side `conductor::compile` retains the 68-cell STEP record: field 66 is the
HOLD PHRASE bitmask, field 67 the HOLD MOVEMENT count, and field 65 points to PRESS
then HOLD MOVEMENT IDs. Existing field 64 counts PRESS MOVEMENTS. No callback JSON
or scan of an unbounded stored library is added. One runtime pointer per existing
switch tracks its pending STEP. Admission uses the same preflight/owned-voice path
and existing bounded 64-entry host command queue. No new scheduler or controller
writer is introduced.

## Reproduction

Use the existing Cloud setup in `AGENTS.md`; no installation on a musician's Pi.

```sh
source /tmp/mbmf-b-env.sh  # prepared Cloud session only
scripts/headless-build.sh
RUN_JACK_TESTS=1 M2_EVIDENCE_DIR="$PWD/docs/evidence/m2" scripts/m2-gesture-test.sh
SCREENSHOT_PYTHON="$TEST_PYTHON" scripts/screenshots.sh
```

`test_conductor_gestures_jack.py` authors two real PHRASE references in Chromium,
sets the second trigger to HOLD, SAVE/LOADs and reconnects, then injects actual JACK
footswitch edges. It also uses browser TEST TAP/HOLD. Captured attacks are
`48,48,72,48,72`; the physical-like held pair is exactly 12000 samples apart at
48 kHz (250 ms). The first short tap contains both edges in one source callback.
The acyclic receiver asserts chronology as received, with no sorting/filtering to
hide errors. Trace is `docs/evidence/m2/browser-jack-trace.json`.

This dummy-JACK 8192-frame functional proof is **not** low-buffer timing, XRUN,
physical ARM64, Helix, or concert qualification. The known #76/#77 release timing
risks remain. Full combined/LIVE qualification is not claimed for this increment.

## REVEAL decisions and next implementation boundary

Authoritative user decisions on 15 October 2026:

1. Unknown target CC7 volume defaults to **127**.
2. LATCH: after HOLD, RELEASE leaves the revealed instance continuing normally.
3. GATE: after HOLD, RELEASE **remasks** the instance while its timeline continues;
   it must not stop/restart the instance or its notes.
4. RELEASE before HOLD stops the still-hidden occurrence and its owned notes.

These rules are recorded, **not yet executable** in M2a. The next coding task is
REVEAL hidden/revealed per-instance state and chronological CC7 ownership through
the existing Controller Host. Emit CC7=0 before initial notes; reveal without a
new attack; release-before-HOLD must release only that gesture's hidden owners.
GATE remasking must preserve the same instance/position. Account for ORIGINAL,
forced and ALL phrase channels after routing. Shared-channel CC7 conflicts warn
but remain allowed, as the master contract requires; CC7 is not audio isolation.

Existing MOVEMENT/physical-CC processing and delayed source output cannot acquire
CC7 tokens in a different chronological order from MIDI emission. A future
MOVEMENT or physical event must not incorrectly invalidate an earlier REVEAL
operation, and an old reveal must never restore over a newer owner. Solve and test
this boundary before advertising the REVEAL controls. Do not add an independent
CC7 ownership registry. Never use a velocity-zero Note On as silent REVEAL.

REAPER remains frozen and neither REAPER UI nor hardware services were changed.
