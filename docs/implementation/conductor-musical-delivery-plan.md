# MBMF native: musical completion and resumable delivery contract

**Status: implementation mandate, NOT an implementation or hardware release.**  
**Base:** `integration/zynthian-release-candidate` (PR #76); PR #77 remains a separate, unmerged runtime-fix branch.  
**Installed user baseline reported:** `b4113da` (PR #62); do not assume it contains later integration changes.  
**Authoritative product contract:** [movement-phrase-conductor-master-spec.md](../movement-phrase-conductor-master-spec.md), **all sections 0–29 and tests A01–L11**. This delivery plan changes priorities, not previously approved musical rules.

## Mission

**Build the complete approved musical instrument, and deliver early, reversible Zynthian V4 builds for hands-on use.** The current failure mode is over-qualifying a limited feature slice while MUTE GROUP, gesture-driven layers, REVEAL, JOIN, actions, and consistent PLAY/STOP are not yet proven playable together. A green test suite on a partial product is NOT feature completion. Conversely, a Cloud XRUN or an intrusive tracer's false CPU attribution is NOT proof of a musical defect.

**Execution, not another audit:** perform a short code/contract comparison per milestone, implement, expose in Web, run actual engine MIDI tests, record proof, commit, and continue. Do not stop after producing a gap matrix or a plan. Keep the detailed, existing tests and safety invariants, but do not let broad repeated qualification campaigns displace unfinished musical functionality.

**Hard boundaries:** no merge, force-push, deploy, restart or update on the user's Zynthian without explicit approval; no LUMAZ/OS/JACK/Helix changes; preserve original issue-54 protected files; no new REAPER features (AGENTS.md freeze), preserve legacy projects and shared interchange; no silent schema changes, data loss, fabricated screenshots or fake MIDI outputs. Use PRs with exact SHAs and reversible dependencies. Keep #76 and #77 independently reviewable, and decide/document an explicit integration base for implementation PRs rather than assuming #77 is merged.

## First priority: recover the original PLAY MODE / PLAY-STOP contract

The user reports historical JSFX musical semantics:
- **ONCE:** successive triggers may overlap independent PHRASE instances; switching PHRASES must not implicitly choke earlier ONCE notes.
- **LOOP:** triggering a playing loop again performs PLAY/STOP toggle (not merely `TRIG=1` again).
- **HOLD:** a new trigger cancels/replaces the previous occurrence; current release-only or rejection behavior is not an acceptable silent substitute.
- **PLAY/STOP:** real controls and actual engine state must agree, including per-PHRASE vs global transport.

**Treat these as regression reports and acceptance expectations, not proof of the exact historical code path.** Trace the earliest JSFX and recorded usage, and compare direct PHRASE MIDI Learn, PHRASE Web buttons, legacy Smart Switch, native Conductor and stop/transport handlers. Specifically inspect current `midi_human_looper.jsfx` `process_phrase_trigger`, `phrase_toggle_stop`, `native_hold_release`, learned PHRASE input handling, `sw_action`, and `conductor_press`. The installed `b4113da` path appears to set LOOP trigger active without toggling, while legacy and Conductor voice policies differ. Verify with MIDI before changing it.

The master spec also establishes **independent instances and selectable JOIN EXISTING / RESTART / NEW INSTANCE**, and explicitly says **IMMEDIATE STEP transition does not imply STOP**. Do not flatten these into one global retrigger rule. Separate:
1. direct source PLAY/STOP command,
2. PLAY MODE of a source or local block,
3. gesture PRESS/HOLD/RELEASE,
4. same-source instance admission policy,
5. targeted STOP/PANIC and transport state.

Where a historical user expectation and an already approved Conductor-specific rule differ, preserve both through explicit, clearly labeled context/policy, or flag the **single exact unresolved decision** in the progress file before implementing that conflict. Do not invent an undocumented universal HOLD or LOOP rule.

**Mandatory real MIDI acceptance:**
- Two overlapping ONCE PHRASES, including identical channel/pitch: both attack and release correctly; no early Note Off, no stuck note.
- Direct LOOP: first trigger starts, next stops, next restarts, with truthful Web/engine feedback and cleanup; verify behavior when other PHRASES run.
- HOLD: original trigger/retrigger/cancel and release behavior established from historical implementation and demonstrated, not assumed.
- PHRASE PLAY and STOP controls, global transport PLAY/STOP, MIDI Learn, legacy switch and Conductor: explicit documented matrix of expected behavior and actual emitted MIDI.
- Sustain, long notes, repeated commands, missing source, restart and save/load do not corrupt unrelated instances or live keyboard notes.

**Gate M0:** a real Zynthian-compatible experimental build can demonstrate the above with a simple manual test sheet, without waiting for concert-level RT qualification.

## Milestones in dependency order

| Gate | Implement / finish | Musician-facing proof required |
|---|---|---|
| **M0 Playback regression** | Historical ONCE/LOOP/HOLD, actual PLAY/STOP, ownership, UI feedback and context-specific policies | Two ONCE overlap; LOOP start/stop/start; HOLD retrigger; correct note cleanup and transport |
| **M1 MUTE GROUP** | Source-PHRASE group property, editable in PHRASE OPTIONS, persisted; exclusive group admission, deterministic smallest source ID in same STEP; warnings update after source changes; targeted STOP | Two bass variations alternate while piano/pad and live keyboard remain unaffected; group survives SAVE/LOAD |
| **M2 PRESS/HOLD + REVEAL** | Per-block trigger independently editable from source PLAY MODE; immediate PRESS, threshold HOLD without duplicate STEP advance; REVEAL silent progression at PRESS, audible at HOLD at current time; RELEASE-before-HOLD cleanup; LATCH/GATE and CC7 warnings | MASTER sounds at PRESS; hidden pad reveals in place at HOLD, or disappears cleanly on early RELEASE |
| **M3 JOIN + instances** | JOIN EXISTING / RESTART / NEW INSTANCE, PHRASE/MOVEMENT JOIN NOW and AT LOOP START, elapsed/cycle reference, next-notes-only PHRASE join, master ownership, Q2 fallback | Join mid-song without fabricated old Note On/Off; movement duration never stretched |
| **M4 MOVEMENT completion** | Reuse existing Phase F native MOVEMENT source/curve, presets, real CC/parameter output, Controller ownership/return, soft restart, press/hold trigger and source persistence; close remaining gaps rather than rewriting it | Filter movement at HOLD, smooth return, simultaneous distinct controller targets |
| **M5 CONDUCTOR editing + traversal** | One authoritative STEP/LAYER editor; remove competing legacy sequence authoring without deleting its data; lossless adoption; block EDIT/trigger, contextual +, auto STEP, drag/drop/undo/touch; SEQUENTIAL/BACKWARD/PING-PONG/RANDOM/SHUFFLE BAG; IMMEDIATE/END OF PHRASE and QUEUED | Four chords in four presses, STEP identity, random bag, delayed transitions with correct master cancellation |
| **M6 Actions + FECK** | STOP PHRASE/GROUP/ALL, PAUSE/RESUME Q4 note policy, RESET CURSOR/BAG, STOP+RESET; FECK stops PHRASES+MOVEMENTS, retains selected STEP, next PRESS replays it (Q1), no old QUEUED | Stop phrases without stopping movements; FECK then same STEP replay, no hanging notes |
| **M7 Persistence + full contract closure** | Complete all master-spec tests A–L and recipes R1–R7, Controller TEST, migration, old patches, source IDs, honest host capability matrix; close every item with code+test | Load/save old/new projects and play complete examples on V4 |

**Milestones are gates, not a permission to abandon other requirements.** Some features already exist partially (notably MOVEMENT and Conductor); reuse and finish them. M1 should be available as a separately testable build as soon as safe. M2 should not wait for M7. If an engine dependency requires a different implementation order, explain it in the progress ledger, keep the same acceptance gates and deliverables.

## Mandatory test pyramid, proportional to development

1. **Functional MIDI first:** deterministic actual engine/JACK receiver captures, including Note On/Off, CC, ordering, ownership, cursor, gesture edges, SAVE/LOAD. No mocked API-only PASS as proof of sound.
2. **Focused regression:** existing ownership, sustain, record/overdub, Controller, routing, patch, safety and affected UI tests for each milestone.
3. **Web proof:** if `headless/web/` changes, comply with `AGENTS.md`: run `scripts/screenshots.sh`, inspect all five viewport PNGs, commit evidence/manifest; don't replace screenshots with fabricated fixtures.
4. **Runtime safety:** never allocate/parse JSON/lock/do I/O in JACK callback, never weaken note ownership or disable failing assertions. Measure relevant real workloads without intrusive timing tools and identify genuine deadline failures separately from harness/host anomalies.
5. **Full combined/release qualification only at meaningful integrated gates**, especially M7, not repeated as the primary activity between every musical feature. Preserve #77's real STOP/UPDATE safety fixes and known unresolved STRESS/256 risk; never declare concert-ready on Cloud-only results.
6. **Hardware approval boundary:** document safe experimental V4 install, exact commit, backups of patch/snapshot and rollback, existing installed SHA, no service restart or deployment until user explicitly approves. User performs musical tests and feeds back.

## Completion matrix and honest status

For every master-spec acceptance ID **A01–L11** and field recipe **R1–R7**, maintain one row with:
`ID | requirement | implementation path | test path | last actual PASS/FAIL/SKIP | host | exact SHA | hardware status`.

Never mark DONE based on a schema field, a visible button, a code comment, a UI-only test or a prior branch's PASS. Distinguish **CODED**, **MIDI-TESTED**, **V4-TESTED**, **BLOCKED**, **NOT IMPLEMENTED**. Explicitly distinguish native from frozen REAPER. Missing support must be visible, never silently approximated.

## Resume-after-interruption protocol (required)

**Persistent checkpoint:** [conductor-delivery-progress.md](conductor-delivery-progress.md) is the canonical current execution state. Update and commit it **after every meaningful implementation increment**, and before stopping/handoff. A new Codex session MUST:

1. Read `AGENTS.md`, the master spec, this plan and the progress checkpoint.
2. Verify `git status`, active branch, HEAD and open PR dependencies; **do not reset/discard user WIP**.
3. Reconcile checkpoint with actual code/tests and update discrepancies.
4. Resume **the first unfinished acceptance item in the current milestone**, not restart a comprehensive audit.
5. Implement + test + commit code and update the checkpoint with exact commands/results, remaining issue and the **next executable action**.
6. If interrupted mid-work, document uncommitted changes and incomplete tests accurately. Never claim completion without commit and evidence.
7. At a gate, create a reviewable draft implementation PR and provide a **user-runnable 5–10 minute musical test**, backup/rollback instructions and exact SHA. Continue to next gate without merging or deploying.

A stop, token cutoff or new session must cost minutes of context recovery, not two days of repeated audit.

## Definition of finished

**All approved requirements in the master spec have actual native behavior, connected usable UI, persistence where required, relevant real MIDI tests, ownership/cleanup correctness and honest known limitations.** The user can play the R1–R7 scenarios on an explicitly approved V4 experimental build. Final concert qualification is a separate gate; do not conflate it with musical feature completion.

**This PR is documentation and task control only. It does not claim any feature was implemented.**
