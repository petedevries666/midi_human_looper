# DICKINSON completion checkpoint

Base: PR #93 / 03ade326d38b2777c65396cd94d05d0eb32cd6da. Includes #89–#92;
#95/#96 are deliberately excluded. No hardware deployment, merge or JSFX edit.

Milestone 1: Program Change no-op

- Native session exposes `loadedPatchSlot`: zero at startup/new patch/unidentified
  restore, set only after a successful LOAD carrying `loaded_patch N`.
- Web LOAD/PASTE and host restoration supply that identity; SAVE/selection do not.
- MIDI requests coalesce to the latest intent, then check native loaded identity
  under the library lock before files, STOP, snapshots or export. Explicit RECALL
  remains a reload. Rollback restores the old *loaded* identity, not persisted UI
  selection. Internal snapshot-origin PCs remain suppressed.
- Executed: native build/FIFO gate exit 0; 16 recall orchestration tests exit 0;
  12 scoped-chain recall tests exit 0; real native/API test exit 0 (ten same-patch
  recalls with held note and unsaved name preserve revision/session/ownership).
- During development the new native test first caught use of the reserved LOAD
  argument; corrected to a separate optional wire marker, preserving portable
  guarded activation. A test command typo was corrected, not an engine assertion.

Next: STEP MAX + ARP traversal lifecycle, native extension, generic editor,
actual emitted MIDI and screenshots. Full regression pending.

Milestone 2: native ARP settings/traversal

- Added kinds 27/28, generic Web binding, native Controller/snapshot resolution,
  versioned nativeArp carrier, old-patch defaults, atomic target validation.
- Actual EEL output: 7,177 focused checks + unchanged 25,426 random-ARP checks pass.
- Actual native/API: three focused tests pass; 25 native-capacity tests pass.
- Actual private JACK 48k/1024: two complete UP traversals, matched releases,
  receiver chronology, zero output overflow, eight production-host MIDI PC no-ops.
  Full receiver trace retained in jack.json. Physical hardware NOT RUN.
- Browser controls, keyboard, CANCEL, SAVE/LOAD/refresh and five layout/PNG checks
  pass; visually inspected all five targeted images. Global screenshot workflow
  fails on unchanged Smart Switch TEST-label clipping at 320px, not claimed green.
- Native source still has same mode 9/11 and 10/12 semantics. See exact traversal
  and restart policies in docs/dickinson-arp-and-recall.md.
- Remaining validation: sanitizer completion, final native rebuild/regressions,
  snapshot adapter identity fixtures, evidence summary, push and Draft PR.
