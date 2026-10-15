# Current capability and qualification matrix

Updated 15 October 2026 for issue #75. This is the current capability authority;
older checkpoints and #63 traces are historical, not qualification of this build.
**Integration PR is draft until its final-HEAD regression and review gates pass.**

## Product direction

REAPER JSFX is frozen legacy. No new REAPER features or parity ports. Existing
JSFX/projects/patches and relevant shared-core/interchange tests remain preserved.
See [freeze decision](reaper-legacy-freeze.md). The master specification imported
byte-for-byte from #55 (`73cdee5`) is the musical reference; its old dual-platform
feature-development language is superseded by this freeze.

## Integration and review map

Current candidate: `integration/zynthian-release-candidate`, freshly based on
main `ab37a752693bf7d2d126a3a9e1ca1c863a5826a9`, tracking issue #75.
The [integration report](release-candidate-75.md) and
[complete source-PR inventory](release-candidate-75-pr-inventory.md) distinguish
integrated ancestry, superseded overlapping branches and unimplemented designs.
The exact tested SHA and full results are published on the integration PR.

Included: #30 → #34 → #37 → #38 → #40 → #41 → #42 → #43 → #44 → #47 → #48
→ #49 → #50 → #56 → #57 → #58 → #60 → #61 → #62 → #64 → #66 → #67 → #68
→ #71 → #72 → #73 → #74; plus #69 AZ hub and reconciled #63 optional diagnostics.
Main's #27/#29 merge history is retained. #45/#46 overlapping implementations
are superseded; #25/#28 experimental foundations remain isolated. Designs do not
constitute completed modules. No hardware deployment or concert qualification.

Controller source reconfiguration now resets only its own mapping runtimes,
without revoking unrelated MOVEMENT/Snapshot/physical leases. Explicit PANIC
continues to cancel all automation. Native A/B configuration edits still retain
their existing explicit cancellation behavior; no broad ownership rewrite.

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
| Local Web entry / AZ | Not applicable | #66 mbmf.local trusted/token gateway; #69 separate az.local portal integrated | Dynamic active process/port identity; optional Webconf installation, checked service status |
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

Setup/procedure: [current integration and rollback](release-candidate-75.md),
[historical studio/live candidate](consolidated-release-candidate.md),
[studio/live bridge](studio-live-bridge.md),
[timing versions](chain-timing-v2.md), [restart authority](project-authority.md),
[shared parameter contract](shared-parameter-contract.md).
