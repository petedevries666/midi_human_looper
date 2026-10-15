# CONDUCTOR MUSICAL DELIVERY — PERSISTENT CHECKPOINT

> **Read this first on every new Codex session.** Update this file in the SAME branch/PR as implementation work, after each focused commit. Never reset a checkout or merge/deploy automatically. See [the delivery plan](conductor-musical-delivery-plan.md) and [the master spec](../movement-phrase-conductor-master-spec.md).

## Current status — M0 implementation, increment 2

- **Branch:** `fix/m0-phrase-playback-contract`, explicitly stacked on PR #78 HEAD `493b13bc259d4e8649a2a4750d1a61b6d90b37b3` / #76. #77 (`6ad38ec`) stays independently reviewable, not implicitly integrated or deployed.
- **Implemented:** native contract 2: direct LOOP toggle shared by Web/MIDI Learn/legacy Smart Switch; cross-source ONCE overlap; HOLD source-once with retained notes, PRESS cut/restart, RELEASE ignored; explicit source STOP. Native mode edits no longer pre-arm LOOP. REAPER execution keeps contract zero, no `@gfx` changes or feature port.
- **Actual MIDI:** focused default `scripts/m0-playback-test.sh` exit 0: 114 LOOP + 17 ONCE + 51 HOLD + 56 shared-entry checks. Native constructor used. Conductor NEW INSTANCE remains independent; twelve-slot saturation remains a clean refusal. Raw before/after logs in `docs/evidence/m0/`.
- **Native/JACK:** rebuilt production binary; `tests/test_m0_playback_jack.py` exit 0 at 48k/8192, actual attack pitches 60,62,64,64,65, HOLD Off-before-On, LOOP STOPPED/PLAYING/STOPPED, PANIC cleanup, no overflow, observed chronological ordering. No sorting/model/API MIDI echo.
- **Regression:** 18,508 full shared EEL checks exit 0; ownership 6698, old contract-zero HOLD 864, CONDUCTOR 125, native CONDUCTOR 3 tests and free capture/overdub 6 tests pass. Actual source SMF fixtures: 18 capture + 36 free captures pass. Browser pointer/keyboard/learned MIDI and source STOP/PANIC pass. No complete combined/LIVE rerun in this musical increment; prior #76/#77 Cloud risks remain open.
- **Visual:** screenshot workflow exit 0; all 184 manifest images across five sizes inspected in contact sheets. Actual existing compact layout retained. Manifest records the honest dirty revision; capture preceded the final native-only mode-arming fix. This is not final-SHA/hardware visual qualification.
- **HOLD approved 15 October 2026:** maintain phrase notes; next PRESS cuts and restarts, RELEASE ignored. Direct replacement preserves independent Conductor occurrences. Explicit source STOP stops all its occurrences. Unsafe mono/ARP restrictions remain.
- **Historical reference:** v1.23.0, `72b92db091d5aef05d37b45057b62ffca390c867`. It chokes cross-source ONCE and latches HOLD; graphical second click stops only. Native corrections intentionally follow user approval, not a false claim of historical equivalence.
- **Details and five-minute musician test:** [M0 native contract](m0-native-playback-contract.md). No build deployment without explicit review; no V4 qualification. Protected issue-54 originals: 25/25 SHA256 unchanged.
- **Next executable action:** after committing this exact code/evidence, start a separate stacked M1 source-only MUTE GROUP PR: versioned source metadata, bounded preparation into existing runtime, targeted release after successful admission; deterministic smallest-source-ID arbitration and recomputed warnings in CONDUCTOR, compact phrase options, save/load and actual MIDI tests. Do not implement JOIN/REVEAL or arbitrary capacities.

## Gate board (do not mark DONE without exact commit + MIDI proof)

| Gate | Status | Implementation PR/HEAD | Real MIDI proof | User hardware |
|---|---|---|---|---|
| M0 Historical ONCE/LOOP/HOLD + PLAY/STOP | MIDI-TESTED: contract 2; grid/global qualification pending | this branch; commit history | 238 focused checks + actual JACK trace | NOT TESTED |
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

- **Implementation PR:** [#79](https://github.com/petedevries666/midi_human_looper/pull/79), draft, branch `fix/m0-phrase-playback-contract`, base #78.
- **Code:** new native runtime contract (no schema change), shared EEL default preserves REAPER, truthful API capability and HOLD browser interaction, integrated focused regression runners and actual JACK test.
- **Next:** commit checkpoint with resulting code SHA, publish to #79, then start source MUTE GROUP on a separate stacked branch. M0 grid capture/global transport corner cases and broad Cloud timing release gate remain explicit follow-ups; do not mislabel full master-spec completion.

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
