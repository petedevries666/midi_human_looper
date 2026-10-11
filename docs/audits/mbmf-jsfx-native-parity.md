# Musical recovery audit

Baseline: PR #49, `2068877441e9a539b1a2d3cfc9a11f92ad69703f`.
Dependency chain remains #44 → #47 → #48 → #49; none was merged or deployed.
This audit separates source findings from hardware qualification. The supplied
v1.20.1 screenshots establish visual geometry; current JSFX source establishes
musical behavior. They are not proof that native playback is equivalent.

| Feature | Original/current JSFX reference | Native at baseline / recovery | Browser | Discrepancy | Root cause | Test/evidence |
| --- | --- | --- | --- | --- | --- | --- |
| New take arming | `arm_layer`, `STATE_READY`: wait for a positive Note On | Baseline `ChainMode::tick` starts on two-bar boundary; recovery defaults to shared `select_phrase_record` | REC, END; global armed/recording telemetry | Wrong temporal semantics, corrected in this slice | Native `align` overwrote shared state each block; `begin` selected grid overdub rather than first-note capture | `free_capture_cases.hpp`: wait 1600 blocks (>2 bars), arbitrary phase, tempo change while armed; real API wait 4.3 seconds |
| First-block chord timing | First attack stored at zero, but second event incorrectly used block offset | Shared defect affected standalone capture too; common offset origin corrected | No export-only repair | Broken MIDI timing, corrected | `record_sample_pos=0` forgot the first attack's offset within its block | Before-fix real EEL failure: second chord note got 17, expected 0; 36 shared/native source fixtures and actual SMF ticks |
| FINISH / take length | `finish_phrase_record`: elapsed recorded samples | Baseline fixed two bars; recovery shared elapsed length, bounded missing-release closure for new native take | END routes existing finish command | Wrong temporal semantics, corrected for new native takes | Native `finish` assigned `chain_duration` derived from tempo | Source length 256−origin samples; API export length <1 second; LOOP/ONCE/HOLD preserved |
| Overdub | Existing take retained; ONCE/HOLD wait for a note, LOOP enters at shared wrap | Recovery reuses shared `select_phrase_record`; no new overdub engine | Existing REC/END | Further lifecycle qualification required | Original and grid adapter had different admission policies | Existing interchange regression covers standalone overdub; native free-time overdub with simultaneous playback and held end notes remains to qualify |
| LOOP | Existing shared phrase transport | Optional old grid preserved; free mode no longer overwrites shared position/length | LOOP tooltip still says two bars | Interaction regression remains | Browser text hardcodes the former adapter contract | Old grid JACK tests explicitly opt in; free-loop/live restart and different-length layers need additional integration coverage |
| ONCE / HOLD | ONCE voice pool; historical REAPER HOLD latched | PR #49 native HOLD repeats while pressed and releases; shared renderer retained | Actual pointer/key/MIDI release; unsupported mono/ARP HOLD rejected | Intentional platform difference; physical verification required | Native flag selects held repetition; legacy flag retains latch | `native_hold_cases.hpp`, native HOLD browser and existing JACK fanout tests; hardware not run |
| ARPEGGIATOR | `arp_process_instrument`, RANDOM=0 / UP=1 / DOWN=2; separate ARP ON/OFF @gfx button | Execution additionally requires `INST_ARP_ENABLED_BASE > .5` | Descriptor `arp` exposes mode/rate/gate/hold, **omits arp_enabled** | Broken control access; probable contributor to reported inactive ARP, not yet corrected | Default enable is zero; web module parameters omit kind 3; insertion alone does not enable execution | Source trace: `modules/catalog.json`, JSFX init, `tf_queue_process`, @gfx etyp==5. Need actual native output tests before repairing descriptor/editor |
| POLYPHONY | POLY=0 / BASS=1 / LAST=2 / LEGATO=3 | Shared note-policy code retained | Named options via browser fallback | Existing baseline retained; mapping duplication remains | Browser hardcodes enum names rather than authoritative choices | Existing shared voice/instance tests; dedicated four-mode native MIDI workflow remains to add |
| Velocity / Time Decay | Shared retrigger counter; logarithmic TIME ratio .5–2, unity default | Shared source times unchanged; recorded mode retained | Filled rails; ONCE-specific controls; dblclick reset | Working baseline, hardware pending | Same descriptor scaling and shared voice factors; no new decay policy | Parameter-contract and musical regressions; physical retrigger test remains |
| Expression assignment | Right-click popup NONE / four named sources, immediately opens curve | Native Controller Host owns mappings and takeover; legacy expression preserved | Controller editor exists, sliders have no equivalent contextual assignment menu | Interaction regression, not repaired | Generic parameter editor disables legacy-owned controls without offering the JSFX assignment workflow | `app.js::edit`; Controller integration tests do not establish contextual UI parity |
| Curves | Multipoint graph, segment bends, previews and presets | Existing curves and native mapping engine retained | Reusable graph exists in controller editing | Missing in-rail/contextual workflow | Separate controller configuration path, scalar editor presentation | Existing browser curve tests; screenshots do not establish full parity |
| Instruments / chains | Thin rectangular panels, connected modules, contextual editor below | Stable IDs and restricted processing stages retained | Horizontal connected blocks, modal editor | Visual/interaction differences remain | Web editor moved contextual controls into modal and uses different spacing | Existing screenshot matrix; screenshot comparison against supplied REAPER images still required |
| Smart Switches | Existing TAP/DOUBLE/HOLD dispatcher | Existing native actions/snapshots preserved | Compact popup configuration | Baseline retained; physical verification required | No separate switch engine introduced | Existing switch, controller and snapshot suites |
| Snapshots / controllers | Native extensions not fully executable in REAPER | Native policy ownership and morphing remain autonomous | Existing transactional controls | Unsupported full studio/live policy parity | C++ takeover/morph policy vs legacy EEL expression policy | Existing portability refuses unsupported execution rather than erasing data |
| Patch / SMF / portable project | Schema-7 source data | No schema conversion of saved takes; free mode accepts actual durations; old grid validates grid | Existing import/export/save/load | Fixed-grid guards corrected for free mode | Engine import/load and worker activation assumed every native chain was a grid | Existing SMF/project suites plus new free native API save/load test |
| CLEAR | Content-only semantics | PR #49 requires STOP/disarm before mutation | Per-phrase option + confirmation | Working restricted capability | Stopped maintenance handshake avoids active-note races | Existing clear/persistence/browser tests; live clear remains explicit rejection |
| Recording telemetry | Shared READY/RECORDING state | Recovery observes shared state after processing, not grid prediction | Global status; per-row states incomplete; diagnostics still grid-labelled | Interaction regression remains | Snapshot contains only global chain flags | Native API verifies armed→recording→finished; per-phrase UI coverage remains |
| Timing / overload | Bounded source memory and scheduler | Grid V1/V2 guards retained; free capture independent of tempo, interruption guard retained | Existing error diagnostics | Hardware verification and capacity reporting remain blockers | Cloud missed callbacks are not proof of device XRUN root cause; free event-store exhaustion needs explicit invalid-take reporting | Existing JACK ordering/overload tests; Pi CPU/XRUN measurement and port interruption not performed |

## Exact next implementation steps

1. Extend the ARP descriptor/shared parameter-row adapter with the already-existing
   `arp_enabled` parameter without renumbering its four established rows. Test
   actual RANDOM/UP/DOWN generated MIDI, gate releases, bypass and persistence.
   Do not silently change the enable state of existing patches.
2. Add free-time native overdub, sustain/end-held-note, capacity-exhaustion and
   transport-disconnection regressions. Report overflow explicitly; no silent
   source truncation may qualify as release-ready.
3. Add per-phrase authoritative recording/playback telemetry and remove stale
   two-bar browser messages, with real backend-driven ARMED/RECORDING/FINISHED
   screenshots. Keep web changes in a separate stacked draft PR.
4. Implement right-click/touch assignment using existing native sources, mapping
   IDs, curves and ownership. Resolve legacy expression ownership explicitly.
5. Restore screenshot geometry/contextual editor, derive enum labels from the
   catalog, run/inspect every required real screenshot, and qualify actual Pi/
   Helix/REAPER behavior after review. No hardware success is asserted here.

This is an incremental recovery branch, not a finished release or full parity
claim. CONDUCTOR, HUMANIZER, ECHOCITY, Motion and pitch bias are not expanded.
