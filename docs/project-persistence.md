# Project state and integration validation (v1.27.1)

The REAPER project serializer now stores the working patch **and both patch banks**,
including all dynamic instrument/switch IDs, Transformer records, mappings, original
phrase events and global settings. Working edits are retained independently of the
last bank SAVE. External patch JSON and the companion Lua SAVE/LOAD remain available
and retain schemas 1–7. Project snapshots have their own versioned envelope.

Runtime notes, retrigger voices, Learn listeners and uncommitted Smart Switch drafts
are deliberately excluded. Reopen starts stopped with no active notes. Both host
orders are supported: deserialize before @init, or after @init. A complete snapshot
is staged separately and published to @init/@block; partial/truncated or unknown
snapshots cannot partially modify the live configuration. Older projects without
serialized data initialize normally and can load their external patch files.

ysfx's serializer stores float32 values. Four exact integer limbs encode each JSFX
double, preserving curves, stable IDs and sample offsets above 16,777,216. This
increases the uncompressed plugin state to roughly 8 MB with both banks; REAPER can
compress its predominantly empty phrase storage. Serialization is a host state
operation, not an audio callback or web operation. Serializer counters (`ps_*`) and
restore locals (`pr_*`) remain separate from MIDI and GUI scratch.

Integration regressions exercise all popup families: Transformer selection,
expression assignment, controller OPTIONS, Learn conflict, Smart Switch editor,
switch deletion, Instrument deletion and phrase CLEAR context. Dismissal frames
remain shielded from underlying controls. Phrase CLEAR gained X/ESC/right-click
outside dismissal and was moved to the overlay pass; OPTIONS follows the viewport
when scrolled. Instrument X is drawn above its panel background.

Native tests restore a fresh host (including deserialize before first init), verify
both banks and unsaved working values, preserve precise timestamps/curve bends,
reject a truncated snapshot, cancel Learn/drafts and leave voices stopped. Three
concurrent MIDI/GFX cases include legacy, repeated CC and appended Instrument curves.
These tests use actual ysfx/WDL EEL2, MIDI and LICE rendering; they do not replace
manual REAPER/Helix testing or a real REAPER restart on the user's machine.

Restoring into an already running host also cancels its prior voices/ownership, pending phrase requests, retrigger context and editing focus before applying the loaded configuration.
