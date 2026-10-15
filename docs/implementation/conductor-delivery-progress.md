# CONDUCTOR MUSICAL DELIVERY — PERSISTENT CHECKPOINT

> **Read this first on every new Codex session.** Update this file in the SAME branch/PR as implementation work, after each focused commit. Never reset a checkout or merge/deploy automatically. See [the delivery plan](conductor-musical-delivery-plan.md) and [the master spec](../movement-phrase-conductor-master-spec.md).

## Current status — M2 implementation in progress

- **Branch:** `fix/m0-phrase-playback-contract`, explicitly stacked on PR #78 HEAD `493b13bc259d4e8649a2a4750d1a61b6d90b37b3` / #76. #77 (`6ad38ec`) stays independently reviewable, not implicitly integrated or deployed.
- **Implemented:** native contract 2: direct LOOP toggle shared by Web/MIDI Learn/legacy Smart Switch; cross-source ONCE overlap; HOLD source-once with retained notes, PRESS cut/restart, RELEASE ignored; explicit source STOP. Native mode edits no longer pre-arm LOOP. REAPER execution keeps contract zero, no `@gfx` changes or feature port.
- **Actual MIDI:** focused default `scripts/m0-playback-test.sh` exit 0: 114 LOOP + 17 ONCE + 51 HOLD + 56 shared-entry checks. Native constructor used. Conductor NEW INSTANCE remains independent; twelve-slot saturation remains a clean refusal. Raw before/after logs in `docs/evidence/m0/`.
- **Native/JACK:** rebuilt production binary; `tests/test_m0_playback_jack.py` exit 0 at 48k/8192, actual attack pitches 60,62,64,64,65, HOLD Off-before-On, LOOP STOPPED/PLAYING/STOPPED, PANIC cleanup, no overflow, observed chronological ordering. No sorting/model/API MIDI echo.
- **Regression:** 18,508 full shared EEL checks exit 0; ownership 6698, old contract-zero HOLD 864, CONDUCTOR 125, native CONDUCTOR 3 tests and free capture/overdub 6 tests pass. Actual source SMF fixtures: 18 capture + 36 free captures pass. Browser pointer/keyboard/learned MIDI and source STOP/PANIC pass. No complete combined/LIVE rerun in this musical increment; prior #76/#77 Cloud risks remain open.
- **Visual:** screenshot workflow exit 0; all 184 manifest images across five sizes inspected in contact sheets. Actual existing compact layout retained. Manifest records the honest dirty revision; capture preceded the final native-only mode-arming fix. This is not final-SHA/hardware visual qualification.
- **HOLD approved 15 October 2026:** maintain phrase notes; next PRESS cuts and restarts, RELEASE ignored. Direct replacement preserves independent Conductor occurrences. Explicit source STOP stops all its occurrences. Unsafe mono/ARP restrictions remain.
- **Historical reference:** v1.23.0, `72b92db091d5aef05d37b45057b62ffca390c867`. It chokes cross-source ONCE and latches HOLD; graphical second click stops only. Native corrections intentionally follow user approval, not a false claim of historical equivalence.
- **Details and five-minute musician test:** [M0 native contract](m0-native-playback-contract.md). No build deployment without explicit review; no V4 qualification. Protected issue-54 originals: 25/25 SHA256 unchanged.
- **M0 next action at that checkpoint:** M1 was subsequently implemented below; resume from the latest M1 checkpoint, not this historical instruction.

## Latest milestone: M1 source MUTE GROUP

- **Branch:** `feat/phrase-source-mute-groups`, stacked on M0 #79 HEAD `2037269`. Draft [#80](https://github.com/petedevries666/midi_human_looper/pull/80); no merge/deploy. Engine code `f743b9146c3820caba9e2da1716b0a9a106b5d0f`, rebuilt and four native acceptance tests rerun successfully.
- **Implemented:** source-only groups, existing guarded config transaction, version-3 internal extension (schema-7 source MIDI unchanged); bounded source-owned release; deterministic smallest PHRASE ID in conflicting STEP, warning recalculation; compact PHRASE OPTIONS; old v1/v2 migration and preserved MOVEMENTS.
- **Real MIDI:** 64 focused shared DSP checks exit 0, including LOOP/ONCE replacement, physical shared pitch and sustain, unrelated source, unsafe-route refusal, conservative capacity refusal. JACK exit 0: On60 → Off60 → On62, unrelated HOLD/retrigger/LOOP, PANIC, zero output overflow, chronological receipt. Cloud dummy 48k/8192, not V4 proof.
- **Regression:** full shared 18,508 checks exit 0; M0/ownership gates pass; supplemental shared-entry tests now 100 checks (actual learned/switch ONCE overlap and HOLD cut/retrigger); 23 CONDUCTOR + 5 MOVEMENT + 20 extension preservation + 3 CONDUCTOR native tests pass. Four native group/portable/bank/fresh-engine tests under ASAN/UBSAN pass; diagnostic files zero. Real browser authoring/playback/warning refresh/save-load passes. Full combined/LIVE not repeated; prior timing risks remain.
- **Visual:** final screenshot command exit 0; 185 manifest views, five sizes visually inspected; three extra real group warnings inspected. A real startup race found in screenshots was corrected with DOMContentLoaded startup and deterministic delayed-editor regression. No unrelated redesign.
- **Known limits:** conservative twelve-slot refusal before victim stop; grouped mono/ARP refused; QUEUED/END_OF_PHRASE cancellation and STOP GROUP action not yet executable (later milestones); old runtimes reject v3, rollback requires matching old project. No V4/Helix qualification.
- **Details/evidence:** [M1 contract and musician recipe](m1-phrase-source-mute-groups.md), `docs/evidence/m1/` and source-hash manifest. Original issue-54 25 files unchanged.
- **Next precise implementation:** M2 separate stacked branch: extend the existing Smart Switch PRESS/HOLD dispatcher and worker-compiled STEP records to admit PRESS layers immediately and HOLD layers at the configured existing threshold; test short taps/release-before-threshold before adding REVEAL/CC7 ownership. Do not create another scheduler; do not conflate latched PLAY MODE HOLD with a long-press gesture. M2–M7 remain unfinished.

## M2 current implementation checkpoint

- Branch `feat/conductor-press-hold`, stacked on #80 HEAD `c956496`.
- PRESS/HOLD actual DSP: 451 checks pass, including 44.1/48/96 kHz, 128/256/512/8192 frames, early release and exact-threshold release, repeated attacks, STOP pending cancellation and TEST TAP/HOLD. Native/API three tests pass, including held ONE_SHOT MOVEMENT and silent LOAD.
- Runtime STEP record retains its 68-cell bound at this increment: 12 PHRASE entries filtered by HOLD bitmask, PRESS and HOLD MOVEMENT lists prepared separately on worker. No JSON, dynamic allocation or unbounded stored-list scan in callback. HOLD uses existing Smart Switch sample clock and configurable threshold.
- UI TRIGGER inheritance/override is implemented but browser/screenshot qualification still pending at this checkpoint. REVEAL is not yet executable.
- User resolved 15 October 2026: REVEAL unknown CC7 volume defaults to 127; REVEAL/GATE RELEASE remasks while retaining timeline, does not stop the instance. Record these decisions; do not ask again.
- Next exact action: implement REVEAL note/timeline lifecycle and token-owned CC7 output via existing Controller Host. Preserve real event chronology: do not let post-DSP controller processing let future replacement/physical events cancel an earlier event incorrectly. Same-CC7 MOVEMENT overlap requires explicit safe restriction or chronological unification, not competing writers.

## Gate board (do not mark DONE without exact commit + MIDI proof)

| Gate | Status | Implementation PR/HEAD | Real MIDI proof | User hardware |
|---|---|---|---|---|
| M0 Historical ONCE/LOOP/HOLD + PLAY/STOP | MIDI-TESTED: contract 2; grid/global qualification pending | this branch; commit history | 238 focused checks + actual JACK trace | NOT TESTED |
| M1 SOURCE MUTE GROUP | MIDI-TESTED: source admission + warnings/persistence; later QUEUED/actions pending | separate stacked branch | 64 DSP checks + actual JACK | NOT TESTED |
| M2 PRESS/HOLD + REVEAL | IN PROGRESS: PRESS/HOLD MIDI tested; REVEAL and browser pending | feat/conductor-press-hold | 451 DSP checks + 3 native tests | NOT TESTED |
| M3 JOIN + instance policies | NOT STARTED | — | — | — |
| M4 MOVEMENT completion (reuse Phase F) | PARTIAL PRE-EXISTING; NEEDS VERIFICATION | PR #62 and integration | prior branch evidence not yet reconciled | — |
| M5 CONDUCTOR editor/traversal/transitions | PARTIAL PRE-EXISTING; NEEDS VERIFICATION | PR #76 integration | prior branch evidence not yet reconciled | — |
| M6 Actions/PAUSE/FECK | NOT VERIFIED | — | — | — |
| M7 Full master-spec closure/migration | NOT STARTED | — | — | — |

## M0: observed behavior matrix

| Entry point | ONCE | LOOP | HOLD | Evidence |
|---|---|---|---|---|
| Frozen historical v1.23.0 | Actual code chokes earlier cross-source occurrence | Graphic toggle differs from native regression | Recorded Off suppressed; second graphic click stops only | historical source SHA above; not hardware rerun |
| User's installed baseline | NOT requalified | NOT requalified | NOT requalified | physical runtime untouched |
| Native direct Web / API | independent sources and physical shared-pitch owner retained | PLAY / STOP / PLAY, no implicit mode-arming | latched, cut/retrigger, RELEASE ignored | M0 DSP/JACK + real native browser tests |
| Native learned MIDI | distinct sources overlap | second PRESS emits Off only | second PRESS emits Off then On, RELEASE ignored | `docs/evidence/m1/m0-entry-extended.log` |
| Native legacy Smart Switch | distinct sources overlap | second PRESS emits Off only | second PRESS emits Off then On, RELEASE ignored | same actual full-DSP trace, native contract 2 |
| Native CONDUCTOR | independent NEW INSTANCE retained | independent repeating admission | independent latched occurrence, source STOP releases | M0 shared/API tests; no gesture-HOLD qualification |

**Conflict handling:** original direct-source semantics and the approved master spec's Conductor instance policies may differ. Do not silently rewrite the latter. Isolate the smallest unclear decision; continue unambiguous work in parallel. Distinguish PLAY MODE `HOLD`, gesture `HOLD`, and REVEAL.

## Detailed acceptance tracking

Populate the complete A01–L11 and R1–R7 matrix from the master spec incrementally as each feature is touched, with exact code location, test name, SHA and environment. Never mark a row DONE without actual native MIDI/parameter evidence. Do not fabricate a full matrix of green rows from existing PR prose.

## Current task / handoff

- M0 code `49a14b9`, checkpoint `2037269`, draft #79 published.
- M1 draft #80, branch `feat/phrase-source-mute-groups`, engine code `f743b9146c3820caba9e2da1716b0a9a106b5d0f`; final evidence/test-only checkpoint follows. Production engine/config/editor, MIDI/API/ASAN/browser tests and screenshots committed/published. No remaining uncommitted implementation at checkpoint.
- Next milestone M2 as above. M0 optional grid/global transport corner qualification and full combined/LIVE remain explicit release follow-ups, not declared complete. No hardware installation approved.

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
