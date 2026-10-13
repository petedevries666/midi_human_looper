# PR E: CONDUCTOR STEP / LAYER editor

Stack: #60 `48417cfdfe39ebd92dcd9d544d693903efa32bad` → #58 → #57 → #56 → #50.
Contract: PR #55 `73cdee5604992ca3bd68e4c6c3b97c545333b127`, read in full;
Q1/Q2/Q4 remain resolved, Q3 remains open. No merge or hardware deployment.

## Musical workflow

Open a Smart Switch's **CONDUCTOR** button. STEP 01 has a MASTER `+` and a second
empty layer. `+` opens PHRASES with actual source names and empty/populated state.
Selecting a source adds a stable UUID reference and automatically reveals the
next empty STEP. Four selections create four persisted STEPS; the fifth empty
insertion column is a draft affordance and is not saved accidentally.
Saving a completely empty editor retains one valid EMPTY STEP, as C requires;
it never starts playback. Unsupported stored types are marked UNAVAILABLE.

STEPS are horizontal columns, LAYERS vertical rows. Small viewports wrap columns
and scroll vertically. EDIT exposes local MODE/VEL/V.DEC/T.DEC INHERIT/OVERRIDE;
source settings/events remain untouched. Buttons move/delete steps/layers.
STEP-header drag inserts the whole column; block drag moves/replaces, CTRL swaps,
ALT duplicates with a new block ID and the same source reference. The contextual
MOVE/REPLACE controls provide a touch/keyboard equivalent. LAYER 01 remains PHRASE
or EMPTY even when loaded unsupported blocks are moved; incompatible moves are
refused. UNDO restores draft configuration, never promises to undo emitted MIDI.

DONE commits the complete draft through C's existing validated native transaction,
then observes the new revision **before closing**, so immediate SAVE cannot send
the pre-commit revision. TEST feedback uses D's authoritative cursor/result.
CANCEL, ESC and outside dismissal discard it. Then SAVE PATCH persists it to disk.
LOAD restores configuration but never starts playback. Existing TEST TAP executes
D's real PRESS path; a fifth PRESS wraps. Physical learned input uses the same
engine. No new musical dispatcher or demonstration backend is introduced.

## Authority and concurrency

GET `/api/v1/conductor` now returns its captured `engineSessionId` and `revision`
alongside the existing document/diagnostics/runtime. Those values come from the
same guarded native capture. Edits preserve the complete source registry, other
switches and unsupported options. Legacy sequence OPTIONS is retained separately;
opening E does not implicitly turn old sequence indices into new blocks.

For a legacy patch, opening creates an explicit draft adoption of the existing
phrase slots using fresh UUIDs. They persist only on DONE. UUID generation uses
`crypto.getRandomValues`, which works on ordinary LAN HTTP; it does not depend
on secure-context-only `crypto.randomUUID`. Existing UUIDs are never recreated.
Missing references are retained and visibly marked with their stored identity;
slot reuse cannot silently bind them to another source.

Native activation is **STOP-only**. Held notes, running phrases/recording or
morphs cause a visible refusal with the draft retained. Edits in another browser
invalidate this draft's session/revision; DONE refuses instead of overwriting.
Controls are locked while DONE is awaiting its real native reply; late edits cannot
be accepted and then lost on close. Cancel/reopen to merge deliberately. Telemetry updates status independently and
never rebuilds the draft. No blind conflict retries or implicit PANIC occur.

The existing UI's enabled mode edit now queues behind pending commands instead
of being dropped. Queued actions retain their engine session, use the current
revision when executed, and cancel if the engine changes. Explicit revision
contracts remain explicit. During pointer-down, structural telemetry repaint is
deferred until after the click event; engine observations still update normally.
The A/B/C/D pending-PANIC and lost-EDIT fixtures are upgraded to assert successful
real POST/native application and a retained pointer target/working EDIT.

## Scope and limitations

Only D's SEQUENTIAL/IMMEDIATE/PRESS PHRASE subset is playable. MOVEMENTS are
clearly unavailable. Unsupported stored configurations are preserved and reported,
not translated. No JOIN/REVEAL/FECK, extra voice capacity, unsafe independent
mono/ARP, new schema or portable-format changes. Existing 12-voice whole-batch
admission/refusal remains authoritative. There is no REAPER authoring/execution
parity claim; C's explicit native-data preservation/refusal remains unchanged.

This is an editor over the proven native model. Removing a block removes only
its reference; removing a layer/step cannot delete a source. There is no new
source-library deletion or source adoption/rebinding tool. Correct a missing
reference by deliberately replacing it with an available identity.

Draft undo is local, not shared across unrelated editors or persisted to disk.
No saved undo restores historical MIDI. Existing TEST TAP is PRESS-only; a HOLD
source requires physical RELEASE or the existing STOP/PANIC controls. This slice
does not add a new browser gesture-testing system. Runtime active STEP is observed from D;
it does not infer per-layer playback states unsupported by the engine. Unsupported
existing overrides remain intact when the four supported options are edited.

No callback, scheduling/ownership code, JSFX `@gfx`, REAPER adapter, installer,
authentication or issue #54 files are changed. Networking/UI and the metadata
response are outside MIDI processing. HTTP's existing 32 KiB command ceiling
still rejects oversize drafts explicitly; no truncation or new Q3 musical cap.

## Validation

Production paths: browser authoring → C transaction → persisted native patch →
D instance admission → actual JACK output. `test_conductor_editor_jack.py` reuses
D's unchanged MIDI assertions with browser-authored steps/layers and browser TEST.
The browser fixture tests local overrides, ID isolation, move/delete/duplicate,
UNDO, stale sessions, missing references, reconnect and silent SAVE/LOAD.

```sh
scripts/headless-build.sh
python3 tests/test_conductor_editor_browser.py
COMPARE_ROOT="$PWD" python3 tests/conductor_diagnostics/pending_edit.py
COMPARE_ROOT="$PWD" python3 tests/conductor_diagnostics/editor_click.py
scripts/combined-test.py --native --jack --browser chromium --timeout 240
scripts/screenshots.sh
```

Use the existing pinned Cloud ysfx/JACK/Chromium environment described in AGENTS.md.
Screenshots include empty editor, source menu, four STEPS/two LAYERS and local
properties at all five required viewports. Visually inspect PNGs, not just the
layout detector. Actual command results, source/binary hashes, raw MIDI and phase
verdict belong in `docs/evidence/conductor-step-layer-editor/` after final validation.
Hardware V4 ARM64/Helix/Firefox and low-buffer XRUN qualification remain pending.
