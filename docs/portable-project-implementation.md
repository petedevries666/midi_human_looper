# Portable project implementation (PR #35)

This implementation is stacked on #34 and #30; neither draft is merged by this
change. It uses the existing schema-7 payload and stable instance IDs, preserving
Controller Engine and Snapshot extensions. Older patches must first be migrated
by the existing engine. Future fields/versions are rejected without overwriting
the source.

`headless/portable_project.py` provides immutable version-1 capture, validation
and materialization. Project IDs are UUIDs, revisions and content hashes are
SHA-256 over canonical JSON, and parents are explicit. Source phrase event
positions, recording offsets, phrase lengths and the loop length are stored in
seconds, then scaled to the destination adapter sample rate. Pitch, velocity,
channel, module order/parameters and native extension data are retained. Phrase
trigger flags, playheads and retrigger counters are cleared. This is a portable
configuration carrier, not an audio-render parity guarantee.

Native operations 4/5 with `arg=1` perform a callback-side STOP-only guard before
maintenance: playback, recording/arming, active phrase voices or morphing rejects
the operation. Existing patch SAVE/LOAD retains its original behavior (`arg=0`).
The guard does not add networking, file I/O or allocation to the MIDI callback.

REAPER can materialize the shared base engine configuration. Native Controller
Engine assignments and populated Global Snapshots are explicitly refused for
REAPER execution; the portable original remains intact. Full native control
parity is not claimed. Hardware/JACK path names are not added to the song.

Validation:

```sh
YSFX_SOURCE=/path/to/ysfx HEADLESS_BINARY=/path/to/engine \
  TEST_PYTHON=python3 scripts/portable-test.sh
```

The tests execute the same EEL2 source at 44.1/48 kHz, compare note bytes and
source timing within a 128-frame block tolerance, and exercise actual native
record/capture/load/rejection. They do not run REAPER itself or physical Zynthian.
Adapter transport policy is unchanged: native chain mode remains fixed two bars
in 4/4, so a incompatible loop length is rejected by its existing loader.
