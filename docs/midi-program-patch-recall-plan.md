# MIDI patch and Zynthian snapshot recall

Implemented for native Zynthian and Web; REAPER remains frozen.

## Use

CONFIG / MIDI OUTPUT contains PATCHES / MIDI PROGRAM CHANGE. Enable MIDI RECALL,
choose a channel (1–16), choose patch-only or linked Zynthian snapshot recall and
press APPLIQUER. Settings are global, outside musical patches and processor IDs.
The Zynthian master channel is rejected to avoid competing snapshot commands.
The tested installation is left opt-in/disabled with channel 15 selected.

MIDI data byte 0 is ignored; 1 selects PATCH 01 and 127 selects PATCH 127.
Controllers displaying byte 0 as program 1 need their display offset accounted
for. All 127 slots support save/load/rename and switch-preset propagation.
Bank Select is not implemented. Unwritten MIDI slots fail before stopping;
ordinary Web LOAD of an empty slot retains its existing new-patch behavior.

SAUVER PATCH + SNAPSHOT ZYNTHIAN saves the current stopped patch and rig into the
selected slot. Its confirmation explains that the selected patch is replaced.
The proposed snapshot is `MBMF/004-MONZTER.zss` for patch 4 MONZTER. LIER/DÉLIER
associate an existing snapshot; RAPPELER PATCH tests the configured recall policy.
Associations store an explicit relative path and host-chain bindings, not a
filename search. Renaming a patch preserves its association; moving/renaming the
snapshot file requires relinking. Saving under a new name retains the old snapshot.
Unrelated existing snapshots with the proposed filename are not overwritten.

## Execution and protection

A host-owned worker intercepts matching PC before Oram controller/ZS3/preset
dispatch and survives native/editor recreation. Both two-byte MIDI and Oram's
padded three-byte events are accepted. Native command 53 reserves the selected
channel's PC packets so MBMF cannot forward them into synth presets. This global
reservation is not serialized into musical patches. Dedicated routing is retained.

Recall validates patch and snapshot before stopping, retains local recovery state,
stops owned voices, loads the Zynthian snapshot, discovers the fresh engine session
and explicitly restores the selected library patch. An older MBMF state inside a
snapshot cannot overwrite the selected patch. Saved host bindings are restored;
missing destinations fail rather than being declared ready. Patch-only recall
uses saved associated bindings, or manual authored routes when unlinked.

Rapid external requests coalesce to the latest target. Repeating the active
target cancels a queued different target without restarting the active load.
Internal PC events during restoration are suppressed. Other channels retain their
normal handling. Failure attempts recovery of the prior rig and resident patch;
failed recovery is reported explicitly. Recall never rewrites saved patches.

Paired save stages the snapshot, retains originals and uses a persistent rollback
journal when publishing patch, snapshot and association. A cross-process library
lock prevents Web patch writes racing host recall/pair save. Recovery files and
musical test files remain local and are never public repository artifacts.

## Qualification and limits

Twelve host tests cover all channels, PC0, padding, consumption, slot 127,
missing/corrupt files, path escape, fresh sessions, latest-request handling,
snapshot failure recovery, failed pair save and interrupted publication recovery.
Native HTTP integration saves/names/loads slot 127, round-trips ARP mode 12 and
checks native reservation bounds. Seven catalog and five snapshot-key tests pass;
generated frozen JSFX is unchanged.

Physical CH15 PC127 entered the existing isolated physical MIDI input and restored
a temporary patch/snapshot pair, producing a new engine session, identical source
and Conductor, and both Surge XT/Sfizz destinations. PC0 left the session unchanged.
Saved user patches were byte-identical during this test. Temporary musical files
were moved into private evidence storage, user slot selection restored and recall
disabled. JACK kept its existing 44100 Hz / 512 frames / 3-period process.

That complete rig recall took approximately 19.7 seconds: it interrupts sound and
is suitable between songs, not seamless switching. Patch-only avoids instrument
engine reload. The 24 existing native capacity tests produced 23 passes and one
short-tap fixture classified as HOLD because its 100 ms threshold included HTTP
overhead. It passes with explicit network-test timing (500 ms DOUBLE / 1000 ms
HOLD / 1500 ms LONG HOLD); production gesture thresholds are unchanged. The added
slot-127 test also passes separately.

Visual validation follows the user's previously approved direct-interface waiver
of the full screenshot suite. At documentation time authenticated inspection is
pending user token entry in the Codex browser; the old credential is redacted by
the browser. The live API, static script route and rendered configuration controls
are verified. No mocked screenshot is substituted for authenticated evidence.
