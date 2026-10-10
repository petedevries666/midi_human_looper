# Studio ↔ Live parity contract (design proposal)

Status: proposal, not implemented. This PR adds a design and acceptance contract only.

## North star
A musical behavior authored in REAPER must be reproducible on Zynthian without manual reconstruction. REAPER is the studio workspace; Zynthian is a fully autonomous live instrument. Neither runtime depends on the other being online.

## One engine, multiple adapters
- Keep phrase/event semantics, MIDI processors, ordering, parameter descriptors, snapshots, motions, smart switches and controller policy in platform-neutral code.
- REAPER adapter: host tempo/transport, DAW MIDI in/out, local persistence, UI integration.
- Zynthian adapter: JACK MIDI, Zynthian transport, headless operation, browser editor.
- Transport, filesystem, HTTP, network discovery and UI must never be called from the real-time MIDI callback.
- No duplicated musical algorithms between adapters. Existing JSFX/ysfx implementation is the baseline to audit, not something to replace casually.
- Deterministic scheduling: define PPQ conversion, sample offset rounding, tempo changes, loop wrap, note ownership, and random seeds for repeatable HUMANIZER and other stochastic effects.
- Audio patch/instrument timbre is outside MIDI parity unless both environments use the same sound engine/preset. Do not promise identical audio from different synths.

## Portable project snapshot v1 (proposal)
Define a versioned schema, ideally reusing existing persistence instead of introducing a competing format:
- schema_version, project_id, revision_id, parent_revision_id, content_hash, created_at
- song_id and song name; musical tempo/meter metadata and transport policy
- instrument IDs and routing intent (stable IDs, not machine-specific JACK ports)
- phrase IDs, length in ticks, MIDI source events, loop/overdub settings
- ordered module instances and their parameter values
- controller mappings, takeover policies, Smart Switch bindings
- global snapshots, motions and assignments when supported
- optional target-specific bindings under namespaced adapters (e.g. Zynthian MIDI destinations), with warnings for unresolved resources

The schema must round-trip unknown future fields where practical and explicitly version/migrate older snapshots. Avoid embedding absolute file paths or hardware-only identifiers as canonical musical identity.

## Publish/activate model
- A studio 'publish' produces a validated immutable revision, not a blind overwrite.
- The live device downloads/uploads outside RT, validates compatibility and resource limits, saves atomically, and acknowledges its staged revision.
- Activation only at a safe boundary (stop, phrase boundary or user-selected bar) with note-off/ownership cleanup.
- Live must continue playing the previous revision if transfer, validation or activation fails.
- Live device must be able to boot and perform entirely offline with last activated revision.
- Conflicts: compare revision IDs, preserve both branches, never silently overwrite edits recorded live.

## MVP vertical slice
1. Round-trip a recorded two-bar phrase and one transformer chain between local host and native Zynthian using a portable snapshot.
2. Confirm pitches, velocities, note-off timing and parameter values match.
3. Save/restart/load both runtimes and repeat.
4. Add one-click publish only after deterministic parity and atomic persistence tests.
5. Defer audio rendering, whole-DAW project synchronization and cloud accounts.

## Acceptance tests
- Offline Zynthian playback after studio computer disconnected.
- Same MIDI events for same phrase, BPM, random seed and module chain (with documented sample/tick tolerance).
- Existing project patches load unchanged.
- A failed sync never corrupts the active live state.
- No host-specific call on RT processing path.
- Changes in one instrument do not leak to other chains.
- Unknown module types and unavailable devices yield actionable warnings.

## Dependencies and coordination
Review current main and PR #30 (native integration), #34 (SMF phrase import/export), #25 (HUMANIZER) and #28 (scheduler). This is not a request to merge them blindly. Reuse the phrase SMF implementation as an interchange tool, but do not confuse .mid with a full performance project.

## Follow-up implementation
Implement in small tested PRs: portable snapshot tests → parity harness → staging/activation → REAPER adapter → remote UI. Keep this proposal separate from the working live engine until tests exist.
