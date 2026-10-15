# Phrase MIDI import/export (issue #33)

The native browser Phrase OPTIONS popup offers IMPORT MIDI and EXPORT MIDI.
Choose a .mid/.midi file, review its note count, track count and duration, then
REPLACE PHRASE. CANCEL, ESC or dismissal leaves the phrase untouched. Stop the
owning processor and finish recording before replacement. Other processors/chains
continue independently. Export downloads `mbmf-phrase-04.mid`, for example.

## Timing and bounds

Read SMF Format 0 and 1, PPQ divisions, running status, note-on velocity zero,
chords, polyphony, repeated pitches, rests, channels, tempo maps and meter metadata.
Import interprets the file's tempo map into source event offsets in seconds, then
rounds to the engine sample rate. Tempo/meter metadata is informational: global
JACK transport tempo and meter never change. The existing engine stores samples,
not musical ticks; imported offsets are not dynamically stretched on later tempo
changes. Native chains retain their fixed two-bar 4/4 grid and tempo-change policy.

Limits: 1 MiB, 64 tracks, 16,384 scanned events, 2,048 stored events and one hour.
Native files longer than the chain's two bars are rejected, including trailing
rests; notes reaching/crossing its loop boundary are rejected rather than wrapped
or truncated. Standalone LOOP phrases cannot exceed their current global loop.
ONCE/HOLD can use independent phrase length. Missing/orphan Note Offs are rejected.
There is no implicit trim, fit, append or merge. Replacement requires explicit
confirmation and a matching engine session/revision; failed validation is atomic.

This first version imports notes only. CC, pitch bend, program change, aftertouch,
SysEx, SMPTE divisions and Format 2 are explicitly rejected, preserving the phrase.
Export includes compatible channel events already stored in the phrase, with no
Transformer, Controller, velocity/time decay or routing baked in. Export is SMF
Format 0 at up to 24,000 PPQ (reduced for extremely long rests) with an explicit tempo (120 BPM if legacy auto-tempo is unset)
and 4/4 metadata. Original per-file tempo/meter metadata is not retained as a new
patch extension; source event timing is retained. End-of-track preserves phrase
length. A malformed/unpaired stored note stream cannot be exported silently.

## Architecture / persistence

SMF parsing and serialization run in the authenticated HTTP worker. Native opcode
35 reads/replaces a selected phrase through the existing bounded maintenance
handshake. The callback only validates runtime safety and acknowledges maintenance;
it does not parse files, allocate event vectors, copy full phrases or perform I/O.
The control worker accesses phrase memory only while the processor is paused.
Import modifies only the selected event/count/length cells (native imports select
its supported LOOP mode); existing schema-7
persistence stores these without a schema change. STOP remains necessary for
replacement, preventing held-note ownership from being invalidated.

API: GET `/api/v1/phrase/ID/midi` returns `audio/midi`; POST
`/api/v1/phrase/midi` accepts JSON `phraseId`, base64 `file`, and `mode`
(`preview` or `replace`). Replace also requires `expectedRevision` and
`expectedEngineSessionId`. Both use existing token/same-origin authorization.

## Validation and manual interchange

Run `tests/test_phrase_midi.py` (independent parser dependency: `mido==1.3.3`),
`tests/test_phrase_midi_integration.py` and `tests/test_phrase_midi_browser.py` via
the combined runner. The fixture is REAPER-style Format 1, not an actual file
exported from a running REAPER instance. Real desktop REAPER and physical
Zynthian/Firefox/Helix interchange still require validation.

1. Record Piano for two bars; STOP; export Phrase 1.
2. Preview/replace Phrase 2; trigger it and verify pitches, velocities and durations.
3. Keep Bass/Synth processors playing while importing on stopped Piano.
4. Export a two-bar notes-only MIDI item from REAPER as Format 0 or 1 with tempo
   metadata. Import it, audition through Piano, overdub, STOP and export back.
5. Open the export in REAPER; compare the source notes and absolute timing.
6. SAVE, restart/reload, replay, STOP/PANIC and check all instruments release.
7. Attempt a four-bar file and a malformed file; confirm clear rejection and an
   unchanged destination. Do not use the cloud high-buffer pass as Pi latency proof.

## Executed software regression

The combined suite passed with the rebuilt native interchange binary:

```sh
python3 -m pip install -r tests/requirements.txt
CHAIN_JACK_BLOCK=8192 HEADLESS_BINARY=/path/to/rebuilt/midi-headless-engine \
python3 scripts/combined-test.py --native --jack --browser chromium
```

Use the existing `YSFX_SOURCE`, `YSFX_BUILD`, `JACK_INCLUDE`, `JACKD` and
`JACK_DRIVER_DIR` overrides documented for this environment, or system-installed
build/JACK dependencies. Six SMF tests include an independent mido parser;
one native end-to-end interchange test records real JSFX MIDI and performs
playback/overdub/restart; the browser test uploads/downloads actual file bytes.
The full suite also runs normal/sanitized Controller checks, existing native EEL2,
Lua, API, six Chromium workflows and dummy-JACK ordering/overflow tests. The native
three-processor test mutes the original phrase before playing the imported copy,
rejects an overlong replacement without mutation, retains other chain data, and
restores the imported phrase through saved Zynthian extended configuration.

Final focused JACK checks additionally use a counted note ledger for repeated
pitches and retain server/engine logs on failure. The final run passed after routing
dummy-JACK stderr to a temporary log file rather than an undrained pipe. Two earlier
follow-up runs saw closed control connections while engines remained alive; that
root cause was not conclusively identified. Do not interpret successful reruns as
hardware reliability certification. Pi timing and repeated SAVE/LOAD/record stress
qualification remain required. No automatic retry of performance commands was added.
