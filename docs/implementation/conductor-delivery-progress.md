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
- UI TRIGGER inheritance/override is implemented and production browser authoring → SAVE/LOAD/reconnect → actual JACK passed. REVEAL is not yet executable. Draft #81 is the M2a increment, not the completed M2 gate.
- User resolved 15 October 2026: REVEAL unknown CC7 volume defaults to 127; REVEAL/GATE RELEASE remasks while retaining timeline, does not stop the instance. Record these decisions; do not ask again.
- Next exact action: implement REVEAL note/timeline lifecycle and token-owned CC7 output via existing Controller Host. Preserve real event chronology: do not let post-DSP controller processing let future replacement/physical events cancel an earlier event incorrectly. Same-CC7 MOVEMENT overlap requires explicit safe restriction or chronological unification, not competing writers.

### M2a qualification checkpoint — 15 October 2026

- Draft **#81**, `feat/conductor-press-hold`, stacked on #80; core code `8a131d5`.
- Final focused DSP **692 checks, exit 0**, extending the earlier 451 with velocity-zero release, configured DOUBLE-window PRESS isolation and HOLD saturation without victim destruction. Twelve-voice budget unchanged.
- Real Chromium authoring → transactional commit → SAVE/LOAD → reconnect → acyclic JACK: attacks **48,48,72,48,72**; held pair exactly **12000 samples** apart at 48 kHz. Receiver chronology asserted directly, zero output overflow. Exit 0; Cloud dummy 8192, not physical or low-buffer qualification.
- Native three tests and the same three on newly built **ASAN/UBSAN**, exit 0, no diagnostic files (ASAN leak detection disabled; pinned ysfx library is not sanitizer-built). Existing native Conductor three, persistence 23 + MOVEMENT five, Controller 162709 + host 579, ownership 6698 and M0/M1 targeted tests pass.
- Full shared host **18508 checks**, actual capture/export **18 + 36 fixtures**, exit 0. Exact source/binary hashes and logs are under `docs/evidence/m2/`. No claim of a new complete combined/LIVE run.
- Final `scripts/screenshots.sh` exit 0: **192 real PNGs**, all five viewports inspected, no detector findings. TRIGGER shortened to visible TRIG while full accessible labels remain; scrollable 320×240 properties and bottom controls inspected.
- Failures retained, not erased: first campaign ADD POINT timeout plus fixture teardown timeout; second campaign native configuration HTTP timeout; third campaign immediate old-DOM DOWN assertion. Six orphaned private fixture engines from earlier failed tests were retired after recording their exact PID/parent/command. Native DOWN values were already correct; the recovery test now requires the actual asynchronously rendered DOWN text through the unchanged default Playwright timeout. Standalone recovery and two subsequent full screenshot campaigns passed. The earlier ADD POINT/config timeout origins are not established; no claim that all Cloud/browser intermittence is resolved. Initial sanitizer compilation was deliberately stopped while the environment stalled, then built and tested sequentially successfully. One manually mis-invoked full-host run supplied a nonexistent baseline path; corrected invocation with the repository's actual `fa200857` baseline passed.
- **M2 remains incomplete**: no REVEAL, CC7 ownership, LATCH/GATE execution, or advanced GATED MOVEMENT is advertised. Next coding action remains chronological shared Controller CC7 ownership and per-instance hidden/revealed lifecycle as specified in `m2-press-hold.md`. No pending product question about GATE/default CC7; both are resolved. M3–M7 not started by this increment. No merge/deploy; protected original 25 files unchanged.

## Gate board (do not mark DONE without exact commit + MIDI proof)

| Gate | Status | Implementation PR/HEAD | Real MIDI proof | User hardware |
|---|---|---|---|---|
| M0 Historical ONCE/LOOP/HOLD + PLAY/STOP | MIDI-TESTED: contract 2; grid/global qualification pending | this branch; commit history | 238 focused checks + actual JACK trace | NOT TESTED |
| M1 SOURCE MUTE GROUP | MIDI-TESTED: source admission + warnings/persistence; later QUEUED/actions pending | separate stacked branch | 64 DSP checks + actual JACK | NOT TESTED |
| M2 PRESS/HOLD + REVEAL | MIDI-TESTED: PRESS/HOLD + REVEAL LATCH/GATE; global qualification blocked | draft #81 → #82, feat/conductor-reveal | 692 DSP checks, 5 REVEAL native/ASAN tests, real Chromium→JACK | NOT TESTED |
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
- M1 draft #80, branch `feat/phrase-source-mute-groups`, engine code `f743b9146c3820caba9e2da1716b0a9a106b5d0f`, final HEAD `c956496`; MIDI/API/ASAN/browser evidence committed/published.
- M2a draft #81: `feat/conductor-press-hold`, first code `8a131d5`, qualification commit follows. Working native PHRASE/MOVEMENT PRESS/HOLD; real browser trigger override and JACK; no REVEAL execution yet. Continue directly with the CC7 ownership boundary in [M2 implementation contract](m2-press-hold.md), not another global audit. Both user decisions are recorded there. No additional product approval is pending for GATE or the default volume.
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

### M2b active checkpoint — REVEAL / GATE

Branch `feat/conductor-reveal`, based on delivered #81 `e8785f3`.
Implementation is present across native DSP, Controller-token CC7 ownership,
chronological JACK output, and existing transactional editor. Final qualification
is pending; see [M2b implementation and exact next actions](m2-reveal.md).
Default volume 127 and GATE remask-with-continuing-timeline are the explicit user
choices. No physical device touched. No M3 work started.

### M2b delivery checkpoint — draft #82

- Code: `74a8f3d457fb6509dec7e26e218e923034375bdb`, branch `feat/conductor-reveal`,
  stacked on #81. Evidence/documentation commits follow without musical changes.
- Implemented: timestamped native CC7 leases, silent REVEAL PRESS, exact HOLD,
  early-release cleanup (including source-owned sustain), LATCH, GATE remask without timeline restart, transactional
  editor/persistence, physical takeover and stale MOVEMENT cancellation protection.
- Actual JACK/browser and 5 native/ASAN tests passed; all four MOVEMENT CC rates
  and same-timestamp replacement passed after the diagnosed coalescing fix.
- 200 actual PNGs generated; every generated view inspected across five sizes.
- Strict combined suite **exit 1**. Old ONCE choke assertion is incompatible with
  contract 2; exact parent #81 comparison has identical emitted notes. Native
  baseline and dedicated-chain HOLD assertion similarly fail on exact parent.
  No assertions were removed or weakened. Cloud XRUN qualification remains open.
- Full results, command exits and raw traces: `docs/evidence/m2-reveal/README.md`.
- Exact next coding step: add real-port REVEAL external/shared sustain
  and full MIDI-buffer burst tests, fix any demonstrated lifecycle defect; then give the
  three legacy-vs-contract-2 fixtures explicit versioned coverage. Keep the old
  expectations as legacy tests rather than silently deleting them. Resume M3 only
  with these MIDI-safety gates understood. No global audit restart required.
- All 25 protected issue #54 files remain unchanged. No merge/deployment, no
  physical qualification, no new REAPER capability or schema migration.
