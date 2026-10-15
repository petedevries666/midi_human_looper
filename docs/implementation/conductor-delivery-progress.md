# CONDUCTOR MUSICAL DELIVERY — PERSISTENT CHECKPOINT

> **Read this first on every new Codex session.** Update this file in the SAME branch/PR as implementation work, after each focused commit. Never reset a checkout or merge/deploy automatically. See [the delivery plan](conductor-musical-delivery-plan.md) and [the master spec](../movement-phrase-conductor-master-spec.md).

## Current status (initial checkpoint; no implementation performed by this planning PR)

- **Current gate:** M0, original PLAY MODE / PLAY-STOP regression recovery.
- **Next exact action:** inspect historical `midi_human_looper.jsfx` behavior and native paths for direct PHRASE, learned MIDI, Web PLAY/STOP, legacy switch and CONDUCTOR. Write a short explicit expected/observed behavior matrix, then implement the first failing behavior and real MIDI regression fixture. **Do not start a new project-wide audit.**
- **Plan base:** `integration/zynthian-release-candidate`, PR #76 (base observed `58ce482b1810bc93ae564c8dc736396067f4ba91`).
- **Parallel corrective PR:** #77, `fix/rc-live-runtime-gates`, observed `6ad38ece5e9becbb810ef41b973666687f31c1cd`, **not merged**; integrate only by reviewed dependency decision.
- **User's installed Zynthian reported HEAD:** `b4113da`, from Phase F / PR #62. The current local physical deployment is NOT assumed to match this planning branch.
- **MUTE GROUP check on installed `b4113da`:** user ran grep; only `headless/conductor_document.hpp` and `headless/conductor.py` matched. This suggests recognition of an action target, **not proof of musical exclusion implementation**. Do not claim the runtime supports it until verified.
- **Routing observed on hardware:** temporary `jack_connect mbh_1:midi_out sfizz-01:input`; it bypasses the intended ZynMidiRouter chain filter and is not a production routing fix.
- **No V4 build installed or validated by this PR. No code changed. No tests run by this PR.**

## Gate board (do not mark DONE without exact commit + MIDI proof)

| Gate | Status | Implementation PR/HEAD | Real MIDI proof | User hardware |
|---|---|---|---|---|
| M0 Historical ONCE/LOOP/HOLD + PLAY/STOP | NOT STARTED | — | — | — |
| M1 SOURCE MUTE GROUP | NOT STARTED | — | — | — |
| M2 PRESS/HOLD + REVEAL | NOT STARTED | — | — | — |
| M3 JOIN + instance policies | NOT STARTED | — | — | — |
| M4 MOVEMENT completion (reuse Phase F) | PARTIAL PRE-EXISTING; NEEDS VERIFICATION | PR #62 and integration | prior branch evidence not yet reconciled | — |
| M5 CONDUCTOR editor/traversal/transitions | PARTIAL PRE-EXISTING; NEEDS VERIFICATION | PR #76 integration | prior branch evidence not yet reconciled | — |
| M6 Actions/PAUSE/FECK | NOT VERIFIED | — | — | — |
| M7 Full master-spec closure/migration | NOT STARTED | — | — | — |

## M0: immediate behavior matrix to fill using code AND emitted MIDI

| Entry point | ONCE overlap | LOOP trigger PLAY/STOP | HOLD retrigger/release | UI state / STOP | Evidence |
|---|---|---|---|---|---|
| Original JSFX historical | USER REPORT: overlap | USER REPORT: toggle | USER REPORT: new trigger cancels old | USER REPORT: currently regressed | verify historical revision |
| Installed `b4113da` direct MIDI Learn | NOT VERIFIED | CODE SUGGESTS sets active, not toggle | CODE SUGGESTS rejects active native HOLD; release stops | NOT VERIFIED | reproduce |
| Installed `b4113da` Web PHRASE PLAY/STOP | NOT VERIFIED | NOT VERIFIED | NOT VERIFIED | NOT VERIFIED | reproduce |
| Legacy Smart Switch | NOT VERIFIED | NOT VERIFIED | NOT VERIFIED | NOT VERIFIED | reproduce |
| Native Conductor | CODE SUPPORTS independent admission; context differs | NOT VERIFIED | HOLD PLAY MODE supported; HOLD trigger gesture not implemented in earlier slice | NOT VERIFIED | reproduce |

**Conflict handling:** original direct-source semantics and the approved master spec's Conductor instance policies may differ. Do not silently rewrite the latter. Isolate the smallest unclear decision; continue unambiguous work in parallel. Distinguish PLAY MODE `HOLD`, gesture `HOLD`, and REVEAL.

## Detailed acceptance tracking

Populate the complete A01–L11 and R1–R7 matrix from the master spec incrementally as each feature is touched, with exact code location, test name, SHA and environment. Never mark a row DONE without actual native MIDI/parameter evidence. Do not fabricate a full matrix of green rows from existing PR prose.

## Current task / handoff fields (overwrite at each checkpoint)

- **Active implementation branch:** none yet (this is a planning PR).
- **HEAD:** to be filled by executing Codex session after checking out its branch.
- **Working tree changes:** none made by this planning PR beyond these two documentation files.
- **Latest committed functional change:** none.
- **Tests executed in this implementation task:** none.
- **Current blocker:** none for investigating and implementing M0.
- **Next executable action:** create a focused implementation branch/PR with explicit reviewed base, reproduce ONCE overlap and LOOP toggle on native engine, and add real emitted MIDI tests before modifying playback. Then implement/fix the first discrepancy.
- **Stop/handoff:** record exact files changed, test commands and exit codes, uncommitted changes, next test to run, branch and SHA.

## First musician test sheet template (fill with real controls before offering an install)

1. Record installed SHA, back up current patch/snapshot and document rollback.
2. Load two short ONCE phrases with a common channel/pitch; trigger both and listen for overlap and complete release.
3. Trigger a LOOP three times: start, stop, start. Confirm Web status follows audio.
4. Trigger HOLD twice and release: verify the historically agreed replacement/cancellation behavior and no stuck notes.
5. Switch between two MUTE GROUP bass phrases while a piano/pad and live keyboard continue.
6. PRESS/HOLD a MASTER + REVEAL pad: hidden timeline progresses and reveals in place; release before HOLD cleans it up.
7. Stop only the target phrase/group, then FECK: check note cleanup and preserved STEP.
8. SAVE, reload stopped, repeat key actions; capture version, MIDI evidence and observed limitations.

**Do not give installation commands until a specific reviewed build and rollback path exist.**
