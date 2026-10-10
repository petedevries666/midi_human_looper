# REAPER ↔ Zynthian bridge (design proposal)

Status: design only; no working bridge is claimed in this PR.

## Goal
Minimize actions between composing MIDI in REAPER and performing the same phrases, processors and control behaviors on standalone Zynthian. A one-click PUSH TO LIVE and PULL FROM LIVE must be possible without copying files or touching removable media.

## Architecture choice
First build a **ReaScript/REAPER extension companion + local bridge service**, reusing the existing MIDI engine and browser UI. Do not require a VST3 rewrite to prove the workflow. A later VST3 can wrap the same portable engine and protocol if necessary. JSFX remains useful for in-DAW MIDI processing but should not be responsible for networking, HTTP uploads or filesystem orchestration.

### Data plane vs control plane
- Data plane: portable versioned project snapshot and per-phrase SMF payloads.
- Control plane: local HTTP API or authenticated LAN transport for discovery, status, upload, download, validate, stage and activate.
- Network I/O runs outside the audio thread. Never block REAPER processing or JACK on LAN operations.
- Zynthian owns its active local revision; remote clients request a staged change, not arbitrary in-place memory edits.

## Minimum user journeys
### A. REAPER MIDI item → phrase
1. Select an item in REAPER, choose 'Send selected MIDI item to phrase' from ReaScript action/context menu.
2. Read the actual MIDI take events through REAPER APIs, not by assuming browser drag contains a .mid file.
3. Choose target song/instrument/phrase (remember last mapping).
4. Preview replacement and loop-length mismatch, then send transactionally.
5. Preserve notes, velocities, duration, PPQ positions, and explicitly warn about unsupported MIDI messages.

### B. Phrase → REAPER MIDI item
1. In REAPER, 'Insert phrase from live' opens the remote phrase picker.
2. Fetch source MIDI and insert into a MIDI item at edit cursor or selected track.
3. Alternatively allow browser export of a .mid file for drag where browser/OS support permits.
4. Do not promise universal direct drag of native REAPER items into a web page or virtual browser files into REAPER: test platform limitations first.

### C. PUSH TO LIVE
- Show target hostname, online status, active revision, changed phrases/modules and pending validation.
- Send only changed assets when feasible, with integrity hashes and revision IDs.
- Stage and validate on Zynthian; activate at safe musical boundary; acknowledge final revision.
- Never overwrite an unpulled live change without explicit conflict resolution.

### D. PULL FROM LIVE
- Import live-recorded phrases and supported project state into REAPER, retaining their stable IDs and original source MIDI.
- Protect local unsaved modifications; provide replace, duplicate or cancel.
- Preserve the previous version for rollback.

## UX principles
- One click after initial target and mapping setup.
- No repeated browse/export/copy/import loop.
- Clear labels: LOCAL, LIVE, SYNCED, OUT OF DATE, CONFLICT, OFFLINE.
- Mobile/browser remote can edit the same Zynthian project; remote browser is not a second audio engine.
- If disconnected, studio editing continues locally; live performance continues with last activated revision.

## Security and robustness
- LAN discovery with manual host fallback; explicit device pairing/token, not unauthenticated arbitrary writes.
- Atomic writes, payload size limits, schema/version negotiation and checksum validation.
- Bounded queue and non-blocking progress; reconnect/resume when practical.
- No live edits applied mid-note without defined safe-boundary policy.
- No destructive auto-sync. Keep audit metadata and rollback.

## Acceptance criteria for a future implementation PR
1. REAPER selected two-bar MIDI item → Zynthian phrase with no manual .mid export.
2. Live-recorded phrase → REAPER item at cursor, timing and velocity intact.
3. PUSH entire compatible song configuration, unplug network, perform from Zynthian.
4. Reconnect and PULL edited phrase without silently losing studio edits.
5. Failed transfer leaves last working live revision intact.
6. Verify on Windows/macOS/Linux REAPER as applicable, documenting limitations; simulate without Pi, label hardware tests separately.

## Dependencies
PR #34 per-phrase SMF import/export is complementary but not sufficient. Depend on a tested portable project contract and existing Zynthian native API. Coordinate with PR #30. Avoid duplicating implementation in VST3 and JSFX.

## Delivery phases
Phase 1: ReaScript selected-item ↔ phrase bridge.
Phase 2: versioned snapshot PUSH/PULL and conflict handling.
Phase 3: compact plugin-like REAPER panel and reliable drag/drop affordances.
Phase 4: optional VST3 front-end only if it improves local playback and workflow.
