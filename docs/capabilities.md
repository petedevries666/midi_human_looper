# Current capability and qualification matrix

Updated 10 October 2026. This is the current status authority; archived checkpoints
are history, not instructions to repeat completed work. **Draft implementation is
not merged or hardware-qualified release functionality.**

## Dependency and review map

`main` → #30 (core/lifecycle/native snapshots/UI) → #34 (SMF interchange) → #37
(portable carrier) → #38 (ReaScript/sync) → #40 (sample-grid transport correction)
→ #41 (shared parameter contract) → #42 (project restoration authority)
→ shared browser observation / named controller choices.

No PR was merged during consolidation. #30 remains a large review dependency;
review lifecycle/ownership, native snapshots and UI separately before integrating.
The full software regression suite is a gate, not automatic permission to label
physical routing, REAPER API execution or Pi latency qualified. Keep #25 and #28
separate pending scheduler continuation and playable-module integration; #32 is
still a Motion specification. #35/#36 are design antecedents, #39 is the audit.

## Implemented execution

| Capability | REAPER | Native/JACK/Zynthian adapter | Interchange / limits |
|---|---|---|---|
| Phrase recording/play/overdub | Existing JSFX engine | Same EEL core; fixed synchronized two-bar native chain mode | Source data preserved; no transport chase or variable meters |
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
| HUMANIZER/ECHOCITY/Motion | Not released | Not playable modules | #25 algorithms/#28 scheduler/#32 design remain isolated |

Compact phrase/instrument controls and six phrases/page exist. Controllers remain
collapsed by default. Phrase labels are generated; phrase Transformer rows are
not implemented. Native chain mode remains LOOP-only. Whole-project multi-JSFX
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
