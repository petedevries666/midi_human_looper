# V2 DICKINSON RC integration and evidence ledger

Status (2026-10-23): source integration and isolated qualification complete on `integration/v2-dickinson-rc`. Draft PR #108 contains the candidate. No Pi installation, service restart, live routing change or merge to `main` has occurred. Hardware acceptance remains open.

## Selected lineage and decisions

- PR #103 (`51b8892f25adef305cd61e13256c84a32a3d9741`) is the full native foundation. It descends through #93 (playable ECHOCITY Harris), #97 (ARP STEP MAX/ONCE and Program Change), #98 (HUMANIZER/VELOCITY CURVES), and #99 (ONCE retrigger, velocity decay and note ownership). Its own scope adds typed Conductor STOP/RESET/PANIC actions and HOLD wrap.
- PR #107 (`b4cb5e0eeb32fe58c8e829b8b0b635ecb2cd8f4a`) supplies later host and Web improvements: shared manual/MIDI recall, Zynthian SOLO fixture, Smart Switch panel, block copy/paste, Movement TEACH, source recovery and mapped-slider feedback. These were overlaid once onto #103. The duplicate #107 ARP-range edit was rejected in favor of #103's native-only enum bridge; `midi_human_looper.jsfx` remains byte-identical to #103.
- PR #106 is design-only and excluded. #95/#96 are superseded HUMANIZER/VELOCITY CURVES foundations, not extra implementations. ECHOCITY remains the Harris 1.0 feature set; no Freeze/Reverse or other effect expansion was imported.
- Relevant #103 native blobs (`midi_human_looper.jsfx`, `headless/engine.cpp`, `native_capacity.py`, `echocity_runtime.hpp`, `native_note_scheduler.hpp`, `native_arp.py`) are unchanged in the RC source merge. The only merge repair was a missing final newline in new files; this corrected the Zynthian SOLO patch application.

## Validation matrix

| Subsystem | Existing evidence / tested commit | Applicability | Integration risk and incremental check | Final status |
| --- | --- | --- | --- | --- |
| Native engine, JACK routing, note ownership, ONCE/LOOP/HOLD | PR #103 isolated workflow [39756519549](https://github.com/petedevries666/midi_human_looper/actions/runs/39756519549), `51b8892f` | Native implementation and frozen JSFX blobs unchanged | RC [39870388847](https://github.com/petedevries666/midi_human_looper/actions/runs/39870388847) routing safety and [39870388848](https://github.com/petedevries666/midi_human_looper/actions/runs/39870388848) isolated native integration passed at `5c9d7f2e361231b2c97df49daf047a8ff1195665` | Isolated validated; Pi audio/JACK pending |
| Conductor ACTION and Smart Switch gestures | PR #103 [39756519549](https://github.com/petedevries666/midi_human_looper/actions/runs/39756519549), `51b8892f` | Native source unchanged | RC [39870388848](https://github.com/petedevries666/midi_human_looper/actions/runs/39870388848) covers real-engine ownership, HOLD/group-0 five-step wrap, config and browser recovery | Isolated validated; pedal acceptance pending |
| ARP DOWN, STEP MAX/ONCE, random modes, Program Change | #97 lineage, `f06b394746f9540b53c8e38d119fbfe1774a7f1f`; #103 green at exact head | Native bridge inherited unchanged | RC [39870388848](https://github.com/petedevries666/midi_human_looper/actions/runs/39870388848) and POSIX recall [39870388869](https://github.com/petedevries666/midi_human_looper/actions/runs/39870388869) passed | Isolated validated; physical MIDI recall pending |
| ECHOCITY Harris 1.0 | #93 `040b15c3c807a884ca8d54e61ed5eafda1c34f75` and #103 source lineage | Native ECHOCITY and scheduler blobs unchanged from #103 | RC native smoke passed; exact source running on Pi has not been read | Source integrated; audible equivalence pending |
| HUMANIZER and VELOCITY CURVES | #98 foundation `9ee8feb651fcf7b23ff4badc46c27c2802c0f1c1` inherited via #103 | Integrated native source unchanged | RC native and browser regressions passed; no Pi CPU/timing measurement | Isolated validated; performance and musical acceptance pending |
| Zynthian snapshot/patch recall, SOLO | #107 host/Web changes `b4cb5e0e` | New combination with #103 | RC [39870388869](https://github.com/petedevries666/midi_human_looper/actions/runs/39870388869) POSIX recall, [39870388803](https://github.com/petedevries666/midi_human_looper/actions/runs/39870388803) SOLO patch, local four-case manual recall test all passed | Isolated validated; Pi snapshots/chains pending |
| Web panels, assigned-slider feedback, recovery | #107 panel and mapped-slider source plus #103 editor | Combined render model | RC [39870388905](https://github.com/petedevries666/midi_human_looper/actions/runs/39870388905) slider and [39870388858](https://github.com/petedevries666/midi_human_looper/actions/runs/39870388858) panel workflows passed; five-size native screenshot artifact reviewed | Browser validated; physical Web session pending |
| RC install, backup and rollback wrapper | New `scripts/v2-dickinson-rc.py`, `5c9d7f2e361231b2c97df49daf047a8ff1195665` | New code | Local isolated preflight/backup test passed; actual updater retains its transactional rollback | Procedure prepared; Pi preflight/install/rollback unexecuted |

All six RC workflows above were green at `5c9d7f2e361231b2c97df49daf047a8ff1195665`. The screenshot workflow used a synthetic PR merge commit with tree SHA `32a6d2dfda405d1da39737a7baa9556f8658b4aa`, identical to the RC head tree. Its artifact contains 214 native browser screenshots at 320x240, 800x480, 1366x768, 1440x900 and 1904x1032; all contact-sheet views were visually reviewed with no obvious clipping. The artifact is linked from run 39870388848. The existing committed screenshot files have not yet been replaced with that artifact's PNGs; this remains a repository-evidence gate under AGENTS.md. A static screenshot cannot qualify continuous live repaint.

## Release gates and remaining work

- [x] Dedicated integration branch and draft PR; no change to `main` or the Pi.
- [x] Dependency/evidence audit before merge; compatible #103 native and #107 host/Web sources selected.
- [x] Frozen REAPER JSFX and source identities preserved; no extra ECHOCITY effects or #106 design added.
- [x] Newline conflict repaired; six applicable RC CI workflows green.
- [x] Versioned preflight, mandatory private backup, transactional updater/rollback wrapper and isolated backup test.
- [x] Changelog, exclusions and manual acceptance list in `docs/v2-dickinson-rc.md`.
- [ ] Commit current five-size PNGs and manifest, or record an explicitly approved alternate evidence path.
- [ ] Read current Pi source and config, run read-only preflight, then install only with explicit approval.
- [ ] Test FEAR & LOATHING / ROAD, existing chains/snapshots, real pedal gestures, ARP, HUMANIZER/VELOCITY CURVES and Harris ECHOCITY, plus XRUNs and restart recovery on Pi.
- [ ] Merge into `main` only after separate explicit approval.

## Architecture notes

The merge retained the existing native note scheduler/ownership contract and did not refactor musical algorithms. The host recall path is shared between manual and MIDI selection; snapshot and patch persistence remain owned by the existing host/updater. The RC wrapper adds only a preflight/archive boundary around that updater. Unfinished PAUSE/RESUME, cursor-only RELEASE advancement, recursive/recall ACTION types, MASTER redesign, PR #106 entry/exit semantics and further ECHOCITY effects remain future work. No optimization is claimed without Pi measurement.

Resume at the first unchecked gate. Do not repeat the repository audit or broad native suites unless source or dependency hashes change, CI reports a new failure, or hardware finds a concrete defect.
