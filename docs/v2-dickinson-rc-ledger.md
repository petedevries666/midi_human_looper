# V2 DICKINSON release-candidate ledger

Status: integration source selection and merge staging. No installation, Pi change, merge to `main`, or physical qualification. Resume from the first unchecked item below; do not repeat the repository audit.

## Baseline and selection (2026-10-23)

- RC branch: `integration/v2-dickinson-rc`, initially forked from Harris-safe PR #107 at `b4cb5e0eeb32fe58c8e829b8b0b635ecb2cd8f4a`; the selected full-feature source tree is now PR #103 at `51b8892f25adef305cd61e13256c84a32a3d9741`, an ancestor chain through #93/#97/#98/#99. The upstream base is PR #92 (`fa7e1ac851458f02f1774f5ba67611e2158d3bd9`), itself part of the earlier native/Zynthian stack. Keep the REAPER JSFX frozen. The #107 shared ARP range edit is deliberately excluded because #103 fixes the native enum bridge without changing legacy EEL.
- #107 already selects the non-ECHOCITY portions of #93 and the independent #100/#101/#102/#105 work: block copy/paste, Movement TEACH, MIDI source recovery, shared manual/MIDI recall, snapshot bank, SOLO proposal, Smart Switch panel and mapped-slider feedback. Do not transplant these again.
- #97 (`f06b394746f9540b53c8e38d119fbfe1774a7f1f`) is the source for native ARP STEP MAX/ONCE and the stronger loaded-session Program Change rule. Reconcile its recall changes with #100 rather than installing a second recall service.
- #99 (`071ff7572e43b24e54b832ac55bb814d7f575436`) is the source for ONCE retrigger/owned Note On and 200% velocity decay. It also changes ECHOCITY terminal ownership: isolate the common note-output contract before porting.
- #103 (`51b8892f25adef305cd61e13256c84a32a3d9741`) is the source for the typed STOP/RESET/PANIC Conductor ACTION subset, after #99. Double tap remains a Smart Switch action gesture, not a Conductor advance gesture. Its RELEASE setting currently delays admission until release; cursor-only release advance is not implemented.
- #98 (`9ee8feb651fcf7b23ff4badc46c27c2802c0f1c1`) is the preferred HUMANIZER/VELOCITY CURVES foundation: it adds host wiring, persistence and UI beyond the incomplete alternative #95/#96 foundations. It depends on #97 and on #93's shared output machinery. Its head has no successful full browser workflow. Do not label it hardware-qualified or fully playable in this RC until integrated and tested.
- #93 (`040b15c3c807a884ca8d54e61ed5eafda1c34f75`) bundles playable ECHOCITY with unrelated work. #107 deliberately contains no `headless/echocity_*` or `native_note_scheduler.hpp` files; these cannot be assumed present merely because ECHOCITY Harris 1.0 is installed on the Pi. Identify the exact source/behavior of the user's Harris 1.0 before taking ECHOCITY code from #93. Preserve the existing audible DRY/WET behavior; do not import further ECHOCITY features or silently omit the effect from the final RC.
- #106 is a design-only entry/exit and release-advance proposal; exclude it from runtime integration. #95/#96 are superseded foundations, not separate modules to merge. PAUSE/RESUME, recursive/recall Conductor ACTIONs, MASTER redesign, Freeze/Reverse and speculative transformer work remain excluded.

## Integration order and risks

1. Verify the provenance of Harris 1.0 and establish its shared note scheduler/output contract on this branch without changing its musical parameters. This is the principal unresolved source-selection risk.
2. Port #97 ARP STEP MAX/ONCE, native kinds 27/28 and `nativeArp` patch carrier; retain #107's ARP DOWN range fix. Compare matching-PC no-op semantics with #100 and keep one authoritative recall path.
3. Port #99's non-duplicate retrigger/velocity-decay changes. Check repeated same-pitch On/Off ownership in dry, HOLD, LOOP, ONCE and any active ECHOCITY path; this is a shared MIDI-output risk.
4. Port #103's typed ACTION subset onto the resulting engine. Keep legacy document/schema defaults and gesture arbitration; leave unsupported actions explicit.
5. Port #98's expressive stage using its existing implementation. Integrate with the selected scheduler once, preserving note pairs, fixed-capacity admission and patch compatibility. Keep it opt-in/bypassed by default until target tests and hardware review.
6. Resolve only observed conflicts; compare resulting registry kinds, patch-carrier versions and file-level source hashes. Commit each subsystem separately. No speculative broad refactor.

## Evidence applicability and minimal additional checks

| Subsystem | Existing evidence / tested commit | Applicability | Integration risk | Additional check / current status |
| --- | --- | --- | --- | --- |
| #107 ARP DOWN and mapped slider | Browser workflows 39867107042 and prior 39866607059; `b4cb5e0e` and `de0e9d44` | Valid while relevant code remains unchanged | ARP kind expansion may interact with #97 | Targeted enum/STEP MAX round-trip after #97; current browser tests pass |
| #107 routing, recall and SOLO fixture | M3 39867107122, POSIX 39867107170, SOLO 39867107039; `b4cb5e0e` | Valid for unchanged source/fixtures | Engine recreation and host snapshot interaction | One RC startup/recall/recovery smoke; Pi hardware pending |
| #107 Smart Switch UI | 39866607059 passed at `de0e9d44`; later `b4cb5e0e` run 39867107354 still compiling when this ledger was written | Partially valid; later commit only changed routing test fixture | #103 editor additions may change layout | Review latest run and five-size real PNGs only after UI integration |
| #97 ARP traversal/recall | PR description reports 7,177 focused EEL + 25,426 legacy checks and isolated JACK; head `f06b3947` workflow 39770071770 was cancelled | Partial; test logs/head provenance need verification | Catalog/native range, patch carrier, #100 recall overlap | Targeted native ARP + patch migration + matching-PC no-op; no wholesale rerun |
| #99 retrigger/decay | PR description: 397 focused real-engine checks at `071ff757`; no linked green workflow | Partial until result artifacts are checked | Shared note ownership and ECHOCITY output | Same-pitch overlap/STOP/PANIC and decay 50/100/200% on integrated engine |
| #103 typed Conductor ACTIONs | Isolated workflow 39756519549 passed at exact head `51b8892f` | Valid for its source, partial after rebasing | Mixed layers, LONG_HOLD/release and MASTER | Small raw MIDI five-step HOLD/group-0 and action-phase checks |
| #98 expressive core | Native core workflow 39777887330 passed at `06ae2a7b`; broad ARP/browser workflow 39777887353 failed at that SHA; current head `9ee8feb6` not covered by those runs | Partial | Shared scheduler, output note pairing, patch codec | Targeted integrated C++/native/JACK + browser authoring; Pi CPU/callback and listening pending |
| ECHOCITY Harris 1.0 | User previously reported audible repeats on Pi, but exact source SHA/provenance is not established in this ledger | Not transferable as RC source evidence yet | #93 scheduler and #99/#98 integration | Identify exact source; isolated dry/echo/note-order/PANIC smoke, then physical user acceptance |

Reuse unchanged subsystem evidence. Before each new test, record changed file hashes and the specific interface at risk. Do not rerun broad suites merely because this branch exists. A final isolated smoke must cover startup, patch load, MIDI in/out, phrase, Conductor, host communication, shutdown and recovery. Physical Zynthian acceptance is a separate gate.

## RC packaging gates

- [x] Dedicated branch from #107; no change to `main` or the Pi.
- [x] Dependency/evidence ledger before code integration.
- [ ] Identify Harris 1.0 source SHA and preserve its behavior.
- [ ] Integrate selected #97, #99, #103 and #98 changes with focused commits and tests.
- [ ] Freeze an immutable RC commit SHA and concise changelog.
- [ ] Provide a versioned preflight/update procedure with mandatory backup of application checkout, configuration, patches and Zynthian snapshot references; refuse unmet prerequisites.
- [ ] Provide a verified rollback procedure and a short manual musical acceptance checklist.
- [ ] Record open limitations and hardware-only checks. Do not deploy or merge without the user's explicit approval.

## Integration decision (2026-10-23)

PR #103 is the full-feature source tree. It descends from #93 (ECHOCITY), #97 (ARP STEP MAX/ONCE and recall), #98 (HUMANIZER/VELOCITY CURVES), and #99 (ONCE retrigger/decay). PR #107 contributes later recall/SOLO/Smart Switch/mapped-slider work. Its non-ECHOCITY edits are overlaid onto #103; unchanged or already-present hunks are not reapplied. Conflict resolutions: retain #103's native-only ARP enum bridge and frozen JSFX; retain its current screenshot gesture flow and ECHOCITY-aware render model; add #107 mapped-slider regression to the existing recovery fixture. The code merge requires CI and visual evidence before this can be called an RC.

The exact source commit currently running on the Pi remains unverified because remote SSH is unavailable from this sandbox. #93 is the repository's documented playable Harris 1.0 foundation; this integration preserves that lineage and does not deploy or claim hardware equivalence.
