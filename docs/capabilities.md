# Current capability and qualification matrix

Updated 14 October 2026; fresh audit includes #64–#71. This is the current status authority; archived checkpoints
are history, not instructions to repeat completed work. **Draft implementation is
not merged or hardware-qualified release functionality.**

## Product direction

REAPER-specific new features/UI/parity ports are frozen. Native Zynthian + Web
are the active targets. Existing JSFX/projects/patches and source-MIDI interchange
remain preserved. See [freeze decision](reaper-legacy-freeze.md) and the
[fresh audit through #71](engineering-audit-2026-10.md).

## Dependency and review map

`main` → #30 (core/lifecycle/native snapshots/UI) → #34 (SMF interchange) → #37
(portable carrier) → #38 (ReaScript/sync) → #40 (sample-grid transport correction)
→ #41 (shared parameter contract) → #42 (project restoration authority)
→ #43 (shared browser observation / named controller choices).

Named integration candidate: [PR #44](https://github.com/petedevries666/midi_human_looper/pull/44)
(`integration/studio-live-rc`), based on #43 commit
`57910e7`. All eight fetched PR heads were verified as ancestors on 10 October
2026. Its build identity and read-only reliability monitor aid qualification;
they do not establish physical acceptance. See [V4 first test](zynthian-v4-first-test.md)
and [REAPER acceptance](reaper-studio-live-acceptance.md).

No PR was merged during consolidation. #30 remains a large review dependency;
review lifecycle/ownership, native snapshots and UI separately before integrating.
The full software regression suite is a gate, not automatic permission to label
physical routing, REAPER API execution or Pi latency qualified. Keep #25 and #28
separate pending scheduler continuation and playable-module integration; #32 is
still a Motion specification. #35/#36 are design antecedents, #39 is the audit.

## Current unmerged recovery stack (14 October)

Fresh GitHub audit: #47 and #48 are review-ready and mergeable into their bases;
#50/#56/#57/#58/#60/#61/#62/#63 remain drafts. #49 remains draft. #27 and #29
are merged into main. Main differs from the #62 ancestry only by those two merge
commits; their implementation commits are already in the stack. No merge was
performed in this resumption. Earlier #44-only status is historical.

Dependency path: #44 → #47 → #48 → #49 → #50 → #56 → #57 → #58 → #60 → #61
→ #62. #63 is independent realtime qualification on #62. Native-destination
routing fixes are also based on #62, without #63 instrumentation. Neither branch
is a hardware-qualified release. The #63 final combined diagnostic run failed a
Chromium EDIT timeout; the native-routing branch subsequently passed the full
combined suite. This does not resolve intermittent live timing or qualify hardware. See
[movement qualification](https://github.com/petedevries666/midi_human_looper/blob/d6169f9/docs/movement-realtime-qualification.md) on #63.

## Implemented execution

| Capability | REAPER | Native/JACK/Zynthian adapter | Interchange / limits |
|---|---|---|---|
| Phrase recording/play/overdub | Existing JSFX engine | Same EEL core; first-note-origin free-time recording by default, FINISH, overdub, LOOP/ONCE/HOLD | Source data preserved; optional legacy/grid capture remains versioned; no general transport chase |
| Independent instruments | JSFX independent instance IDs | Independent instances and separate processors | Eight instrument slots/16 phrases per processor; no phrase-owned effect chain |
| Existing Transformers | Shared EEL stages | Same EEL stages | Restricted ordering, stateful duplicates refused; no arbitrary pedal order |
| Timing v2 | Free-time behavior unchanged | Opt-in exact sample-grid two-bar length, in-buffer record boundaries | New installs v2, old config/CLI v1; incompatible grids refused, no silent retime |
| Parameter identity and conversion | Generated embedded EEL bounds/scale/normalize | Generated C++ identity/scale/normalize | All 25 kinds share descriptor rules; no new deployment include |
| Controller Engine | Legacy expression behavior | Learn, mappings, token ownership/takeover/return | Native policy execution not yet shared with REAPER |
| Snapshot manager | Native execution unavailable | Capture/update/rename/duplicate/reorder/delete/inclusion, recall/timed/A-B, switch actions | Native extensions preserved; REAPER execution refused |
| Smart Switches | Existing JSFX gestures/config | Existing gesture dispatcher + native snapshot overrides | Native popup is not complete legacy configuration editor |
| SMF import/export | ReaScript take transfer | Browser preview/replace/download + native playback | Format 0/1, notes-only, bounded validation; tempo never changed implicitly |
| SEND/GET | Async companion, direct selected phrase/item | Existing phrase endpoints | No manual SMF export; actual REAPER APIs need physical qualification |
| PUSH/PULL | One recognized track JSFX across open projects | Immutable staged revision, guarded STOP-only activation | UUID/revision/session/hash checks; no unattended background sync |
| Restart authority | RPP saved by REAPER; bridge baseline is pairing metadata | Explicit committed portable project; explicit Zynthian snapshot overrides | Legacy slot SAVE is manual, not automatic restart authority |
| Headless operation | Studio host required | Browser/worker/network can disconnect after committed transfer | Restore stopped, never autoplay |
| Velocity Decay Pitch Bias | Response helper only, inactive | Same inactive EEL helper | Controls, playback integration, descriptors and migration remain [unimplemented](velocity-decay-pitch-bias-checkpoint.md) |
| CONDUCTOR PHRASE | No equivalent execution yet | Stable STEP/LAYER references, browser authoring, sequential immediate PRESS, independent ONCE admission | #58/#60/#61 draft; missing references diagnosed; mono/ARP independent admission restricted |
| MOVEMENT | No equivalent execution yet | Linear/stepped CC curves, 10/25/50/100 Hz, ownership/replacement, parallel soft GLIDE, native STEP integration | #62 draft; actual engine/JACK tests; performance/hardware qualification incomplete |
| Native chain destinations | Frozen host routing | #67 dedicated MB source into ZynMidiRouter, filtering by receiving channel | #64 direct shortcuts suppressed; graph/chain/snapshot/feedback hardware qualification remains |
| PHRASE output channel | Existing shared source retained | #68 ORIGINAL / ALL / CH1–16, playback-only policy, latched owned destinations | Instrument OUT ALL is not implemented; MOVEMENT explicit channel unchanged |
| Local Web entry / AZ | Not applicable | #66 mbmf.local trusted/token gateway; #69 separate az.local portal draft | Dynamic active process/port identity; #69 is not yet on #71 ancestry |
| Reviewed UPDATE | Not applicable | #71 native/Web controls, common separately authorized worker | No published eligible release; UI-wide restart; physical activation/rollback unqualified |
| Live BYPASS / MIDI LOG | Legacy behavior preserved | #70 requirements only, not implemented in #71 | No transparent native BYPASS/log claim |
| HUMANIZER/ECHOCITY | Not released | Not playable modules | #25 algorithms/#28 scheduler remain isolated |

Compact phrase/instrument controls and six phrases/page exist. Controllers remain
collapsed by default. Phrase/instrument names are editable and persistent; phrase Transformer rows are
not implemented. Native chain mode supports LOOP/ONCE/HOLD in the recovery stack; hardware qualification remains separate. Whole-project multi-JSFX
studio pairing and full REAPER Controller/Snapshot parity remain incomplete.

## Proof and release gates

Software evidence: actual EEL execution, native HTTP worker, dummy-JACK three
processors, counted note cleanup and timestamp ordering, controller ownership,
snapshot transitions, source-MIDI round trips/restart, bridge conflict/rollback,
and Chromium editor workflows. Shared conversion tests are not full musical parity.

Required physical tests: actual REAPER actions/source API and effect state save,
Firefox full editor, Raspberry Pi CPU/RSS/deadlines/XRUNs at playable buffers,
Zynthian native graph and snapshot precedence, Helix learn/takeover, device/port
reconnection, STOP/PANIC, interrupted transfer/power loss. Desktop tests use large
buffers for VM stability and cannot certify live latency.

Setup/procedure: [consolidated candidate](consolidated-release-candidate.md),
[studio/live bridge](studio-live-bridge.md),
[timing versions](chain-timing-v2.md), [restart authority](project-authority.md),
[shared parameter contract](shared-parameter-contract.md).
