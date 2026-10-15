# CONDUCTOR MUSICAL DELIVERY — PERSISTENT CHECKPOINT

> **Read this first on every new Codex session.** Update this file in the SAME branch/PR as implementation work, after each focused commit. Never reset a checkout or merge/deploy automatically. See [the delivery plan](conductor-musical-delivery-plan.md) and [the master spec](../movement-phrase-conductor-master-spec.md).

## Current status — M0 implementation, increment 1

- **Branch:** `fix/m0-phrase-playback-contract`, explicitly stacked on PR #78 HEAD `493b13bc259d4e8649a2a4750d1a61b6d90b37b3` / #76. #77 (`6ad38ec`) stays independently reviewable, not implicitly integrated or deployed.
- **Implemented increment:** native free-time direct LOOP PLAY/STOP/PLAY. Previously the second PLAY emitted another Note On; it now queues the existing source-owned stop, then a third PLAY restarts at zero. No new scheduler, schema, UI or REAPER changes.
- **Actual software MIDI:** `scripts/m0-playback-test.sh`, before exit 1 (`second=[[144,60,100]]`), after exit 0 / 114 checks (`second=[[128,60,0]]`) at 128/512/8192 frames, 48 kHz, through production `ChainMode` + full ysfx DSP MIDI output. This is deterministic actual engine MIDI, **not a JACK or hardware test**. Evidence: `docs/evidence/m0/loop-before.log`, `loop-after.log`.
- **HOLD arbitration, user approved 15 October 2026:** **maintain phrase notes; next PRESS stops previous occurrence and restarts at zero; RELEASE ignored**. This supersedes native repeat-while-held behavior for HOLD. Do not confuse PLAY MODE HOLD with gesture HOLD or future GATED block admission.
- **Historical reference:** `midi_human_looper.jsfx`, v1.23.0 header, `72b92db091d5aef05d37b45057b62ffca390c867`. Actual code chokes cross-source ONCE voices and latches HOLD with recorded Note Off suppressed; graphical HOLD second click stops only. The new native contract intentionally corrects cross-source ONCE and follows the user's explicit HOLD retrigger decision; do not claim these corrections already existed in that revision.
- **Next exact coding action:** extend the focused real-DSP fixture for ONCE overlap and approved HOLD; fix native/shared entry paths with a native-only policy flag, preserve frozen REAPER behavior and Conductor independent admission. Then add actual JACK + browser/API path tests and finish M0. Only then M1 source MUTE GROUP.
- **Not yet implemented:** learned MIDI/legacy Smart Switch LOOP toggle; ONCE cross-source correction; approved HOLD; complete per-source STOP/global transport consistency; M1–M7. M0 is **not complete**.
- **No V4 installation/qualification.** User-reported installed baseline remains `b4113da`. #77 final evidence shows Cloud XRUN and grid/MOVEMENT reception/pagination failures; do not repeat broad qualification in place of musical development.

## Gate board (do not mark DONE without exact commit + MIDI proof)

| Gate | Status | Implementation PR/HEAD | Real MIDI proof | User hardware |
|---|---|---|---|---|
| M0 Historical ONCE/LOOP/HOLD + PLAY/STOP | IN PROGRESS: direct LOOP increment | this branch; commit history | 114 actual ysfx MIDI checks | NOT TESTED |
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

## Current task / handoff

- **Current code:** the commit containing this checkpoint; tested working-source increment over plan HEAD `493b13bc` (no self-referential SHA claim). The next checkpoint records its concrete commit ID.
- **Changed:** `headless/chain_mode.hpp`; focused real-DSP test/runner in `tests/m0_playback_cases.hpp`, `tests/expression_host.cpp`, `scripts/m0-playback-test.sh`; evidence and this ledger.
- **Next executable action:** ONCE overlap + HOLD retrigger/latched Note Off policy fixtures, then shared native-only fix and real JACK/API coverage. Preserve Conductor instance policies and the 12-instance bound.
- **PR:** create one focused draft M0 implementation PR stacked on #78 once production-path cases are covered; no merge/deployment.

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
