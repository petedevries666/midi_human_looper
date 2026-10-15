# Studio / live implementation and first test

Implemented in the #35/#36 implementation stack: #37 is based on #34, which is
based on #30; the bridge PR is based on #37. Design PRs #35/#36 are not merged.
The musical engine remains the existing JSFX executed by ysfx; the network and
file workers do not schedule music. Native Controller/Snapshot state from #30
is preserved by portable native activation. Individual MIDI interchange reuses
#34's validated, bounded parser and transactional phrase replacement.

## Install / start

Use the bridge implementation branch, including its prerequisite stack:

```sh
git fetch origin feat/reaper-live-sync-bridge:refs/remotes/origin/feat/reaper-live-sync-bridge
git switch feat/reaper-live-sync-bridge
python3 -m venv .venv
.venv/bin/pip install -r tests/requirements.txt
YSFX_SOURCE=/path/to/ysfx YSFX_BUILD=/path/to/ysfx/build \
  HEADLESS_BINARY="$PWD/headless/build/midi-headless-engine" scripts/headless-build.sh
```

Keep existing native Zynthian installation/routing from
[zynthian-native-chains.md](zynthian-native-chains.md). The adapter restores a committed portable
revision before starting its editor, unless an explicit Zynthian snapshot is
being restored; that snapshot has priority. No OS, LUMAZ, service or JACK graph
changes are required. Each paired endpoint addresses **one** independent
processor. Automatic multi-processor project distribution is not implemented.

For a standalone host (not in parallel with the native adapter):

```sh
headless/build/midi-headless-engine midi_human_looper.jsfx /tmp/mbmf.sock --jack
python3 headless/server.py --socket /tmp/mbmf.sock --bind 0.0.0.0 \
  --port 8765 --token-file /path/to/private-token \
  --patch-dir /path/to/processor-data --restore-active-project
```

Set a private LAN token file with permissions `0600`. Use a trusted LAN; plain
HTTP does not encrypt the token. No cloud account or discovery service is used.
The native adapter's port is `web_port_base + processor ID`; configure its
existing `web_bind`/`token_file` settings for LAN access. Firefox may disconnect
while the engine continues running. Do not start another host on the same socket.

On the REAPER computer, copy the updated `midi_human_looper.jsfx` into Effects,
and copy **all** `reaper/*.lua` files together into a ReaScripts folder. Reload the
effect, then import `MBMF_SEND.lua`, `MBMF_GET.lua`, `MBMF_PUSH.lua` and
`MBMF_PULL.lua` into REAPER's Actions list and optionally its toolbar. Start the
paired worker on that computer:

```sh
python3 headless/reaper_bridge.py --live http://ZYNTHIAN_IP:8766 \
  --token-file /path/to/private-token \
  --spool '/REAPER/RESOURCE/PATH/Data/MIDI_Human_Looper/bridge'
```

Find the resource path with REAPER's “Show REAPER resource path” action. Keep the
worker running during transfers. It uses only Python's standard library.
Desktop Windows/macOS and actual REAPER installations still require testing;
the Linux native pointer uses directory fsync, while Windows desktop spools use
file fsync plus atomic replacement.

## Phrase SEND / GET

SEND reads the selected MIDI take through `MIDI_GetAllEvts`, interpreting PPQ
positions through REAPER's tempo map. It previews capacity and requires explicit
replacement confirmation; a changed engine revision/session invalidates that
preview. GET creates a new MIDI item on the selected track at the edit cursor,
using `MIDI_SetAllEvts`. No manual `.mid` export/import is necessary. Channels,
pitches, attack/release velocities, overlapping notes and source timing are
preserved. Receiving does not change either host's global tempo.

First version is notes-only, at most 2,048 events and one hour. CC, SysEx, text,
muted notes and notes crossing an item boundary are rejected explicitly. The synthetic final REAPER All Notes Off (CC123) source marker is accepted as
metadata only after all notes; genuine matching Note Offs are still mandatory.
Other CC data remains unsupported. Glue
repeated source-loop items before SEND. Native chain destinations must fit the
existing two-bar grid; oversized material is rejected, never truncated. Finish
recording and STOP the destination before replacement. GET does not apply the
pedalboard to source data.

## PUSH / PULL

Toolbar actions perform the whole transfer, without manually exporting patch
files. First PUSH requires explicit replacement confirmation. Later PUSH checks
the last synchronized active revision and exact live fingerprint, then validates
and stages an immutable project. Activation additionally checks engine revision,
session and fingerprint, and is **STOP-only**. Desktop baselines also bind the
REAPER project GUID; a different project must deliberately PULL/adopt before PUSH. The native callback also compares
its raw patch against a preallocated capture baseline before any load, protecting
parameter changes between capture and activation. Playback, arming/recording, held
notes/sustain and timed morphs reject capture/load before cancellation. No automatic
STOP or PLAY is sent.

Clean PULL proceeds directly. Unsynchronized local state offers REPLACE,
DUPLICATE portable data only, or CANCEL. ReaScript re-captures before application;
the JSFX also compares its entire current patch and globals against a separately
latched baseline in the same block as apply. Changes after capture reject the
load. A successful PULL marks the REAPER project dirty; save the `.RPP` normally
to persist its new JSFX state too. Its mailbox uses reserved cells 17–22 and bounded baseline cells
199980–199988 / 200000–371648; these are not persisted. Their gmem banks
are allocated during initialization, before MIDI processing. The existing SAVE/LOAD
mailbox and Lua daemon remain usable.

Whole-project REAPER execution currently requires **exactly one track JSFX
instance across all open project tabs**, verified with FX identity APIs (including
input FX), and stopped REAPER transport. Take FX
and multiple instances are refused because the legacy shared-memory adapter
cannot identify their owner. Individual phrase transfers do not require a JSFX.
Run FX processing while stopped so the mailbox can acknowledge.

Projects carry the existing schema-7 parameters, routing channels, stable
Instrument/module IDs, source MIDI and native extensions. Seconds are converted
to the destination sample grid (nearest sample). Native chain activation still
requires the existing exact two-bar loop length; differing tempo/block grids
are rejected rather than silently changing timing. A completely empty studio
patch with no loop duration adopts the native grid, explicitly reported as
`emptyGridAdopted`; no source events or global transport tempo are changed. Phrase/bar boundary activation
and automatic transport-grid adaptation are deferred.

REAPER cannot yet execute native Controller Engine bindings, Snapshot actions or
A/B morphs. Such PULL/PUSH configurations are **refused**, with a portable-copy
option on PULL; a base-only PUSH cannot erase those native fields. Empty native
extensions are retained in the portable live carrier. The original live revision
and any duplicate portable copy remain intact. No full control/UI parity claim
is made.

Stage files and the active pointer use temporary files, fsync and atomic rename
outside JACK. Successful activation acknowledges only after pointer commit.
Persistence failure rolls back the engine and restores the prior pointer.
Incomplete stages have no effect. Restart restores only the committed revision,
never playing state. Keep the processor data directory on a writable local
filesystem with atomic rename support.

Ambiguous timeout/crash: inspect live state before retrying. A `.working.json`
job may already have committed remotely; do not replay it automatically. A
successful PULL acknowledgement commits only its own pending transaction.
Configuration changes made through other independent control clients still need
normal revision arbitration; do not run competing patch loaders during sync.

## Test / rollback

Automated commands:

```sh
HEADLESS_BINARY=/path/to/engine python3 tests/test_project_sync.py
python3 tests/test_reaper_bridge.py
YSFX_SOURCE=/path/to/ysfx HEADLESS_BINARY=/path/to/engine \
  TEST_PYTHON=python3 scripts/portable-test.sh
python3 scripts/combined-test.py --native --jack --browser chromium
```

`--jack` starts an isolated desktop dummy JACK server; do not run it on a live
Zynthian graph. Tests cover source MIDI round trips, version/hash rejection,
44.1/48 kHz shared-EEL2 note/timing parity, JSFX mailbox compare-and-apply,
staging/activation conflicts, disk-failure rollback, browser-independent process
restart and real JACK activation preserving #30/#34 data. REAPER APIs are mocked;
REAPER itself, stock Firefox and Raspberry Pi/Helix hardware remain unvalidated.
Cloud JACK tests use 8,192-frame buffers to avoid VM scheduling misses; this is
functional validation, not a playable-latency measurement.

Physical test:

1. Back up processor data and the REAPER project; use a disposable patch.
2. Start three native chains using the existing Piano/Bass/Synth procedure. Pair
   the worker with the Piano processor's authenticated editor endpoint.
3. SEND a one-bar chord/arpeggio take to an empty phrase, then play and overdub it
   in Zynthian. Verify the other chains are unchanged. GET it to a new REAPER item
   and compare notes, channels, release velocities, durations and rests.
4. STOP both sides. PUSH a compatible shared-base patch, change one live value,
   and verify another PUSH reports a conflict. PULL with CANCEL, then DUPLICATE,
   then explicit REPLACE; verify each outcome.
5. Try capture/PUSH during playback and PULL after a local edit. Both must refuse
   destructive activation. Test populated native snapshots/controller mappings:
   REAPER execution must report unsupported capability and retain the original.
6. Commit a compatible revision; close Firefox and the worker, restart the
   processor, and verify source MIDI/configuration restore without autoplay.
   Resume playback manually. STOP/PANIC must release all notes.

Rollback: STOP/PANIC, stop the paired worker, restore the backed-up processor data
and previous repository/effect version, then restart the existing native adapter.
Remove the imported ReaScript actions if desired. Do not delete unrelated services
or change system MIDI/JACK configuration. This implementation does not replace
installation/rollback of the native adapter itself.
