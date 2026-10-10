# V4 studio/live candidate: installation and physical acceptance

Candidate branch: `integration/studio-live-rc`. This contains the implementation
chain #30 → #34 → #37 → #38 → #40 → #41 → #42 → #43. All remain drafts;
main has not been changed. The adapter API was tested against a known Zynthian UI
revision, not your V4 image. V4 names the hardware, not its installed UI API or
32/64-bit OS. Installation must refuse unknown registration anchors.

## Preserve the working instrument first

Save your current Zynthian snapshot and copy it to another computer. Stop all
MBMF playback/recording and use PANIC before closing its processors. In a terminal,
record `uname -m`, `getconf LONG_BIT`, the Zynthian UI git revision and its dirty
status. Do not update Zynthian, install OS packages, restart JACK or change LUMAZ.
The following backup is additive; retain its directory until acceptance passes:

```sh
backup_dir="/zynthian/zynthian-my-data/mbmf-backup-$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$backup_dir"
cp -a /zynthian/zynthian-ui/zyngine/zynthian_chain_manager.py "$backup_dir/"
if test -e /zynthian/zynthian-ui/zyngine/zynthian_engine_mbh.py; then
  cp -a /zynthian/zynthian-ui/zyngine/zynthian_engine_mbh.py "$backup_dir/"
fi
if test -d /zynthian/zynthian-my-data/midi-human-looper; then
  cp -a /zynthian/zynthian-my-data/midi-human-looper "$backup_dir/"
fi
git -C /zynthian/zynthian-ui rev-parse HEAD > "$backup_dir/ui-revision.txt"
```

Also retain your previous MBMF checkout/binary if installed: its `install.json`
contains their paths. Back up that binary and record its SHA256 and git revision.
Use a separate candidate checkout so the old binary and JSFX remain recoverable.

```sh
git clone --branch integration/studio-live-rc --single-branch \
  https://github.com/petedevries666/midi_human_looper.git \
  /zynthian/zynthian-plugins/midi-human-looper-rc
cd /zynthian/zynthian-plugins/midi-human-looper-rc
git rev-parse HEAD
python3 scripts/generate-parameters.py --check
```

Build using the existing pinned ysfx checkout and JACK development files as in
[the candidate build guide](consolidated-release-candidate.md). Do not run the
apt-based setup script as part of this test. A binary from this x86 cloud workspace
cannot run on the Pi; build on the target or a matching ARM environment. If build
dependencies are missing, stop before registration and retain the existing setup.

For an update, run the **previous checkout's** `zynthian/install.py --rollback`
first. Its hash checks prevent overwriting unrelated UI edits. For a first install,
skip that step. From the candidate checkout:

```sh
python3 zynthian/install.py --binary "$PWD/.build/midi-headless-engine" --lan
```

Before rollback or installation, run the same installer with `--check` and the
binary path. It validates known UI anchors and binary existence without writing
files; `upgradeRequiresRollback` identifies an older/different installed adapter.
This does not execute the binary or certify its architecture/hardware behavior.

An existing `install.json` is preserved intentionally. For a separate-checkout
update, inspect it and explicitly change only `repository` and `binary` to the new
absolute paths while processors are stopped. Preserve token, bind, port and timing
selection. Do not assume reinstall changes those paths. New installations select
timing v2; older configurations retain v1. Keep the old timing contract for old
projects until grid compatibility is checked.

Save the UI setup, identify the actual UI unit with
`systemctl list-units 'zynthian*'`, and restart only that UI unit when ready.
Do not restart JACK, unrelated services or the whole Pi to activate registration.

## Three processors and MIDI verification

1. Set 120 BPM, 4/4. Create Piano, Bass and Synthesizer synth chains on channels
   1, 2 and 3. In each chain add the MIDI Tool **MIDI Bad Mother Fucker** before
   its synth. Use normal Zynthian input/channel selection and autoconnect.
2. Play the keyboard into each chain. Verify only its intended synth sounds.
   Use `jack_lsp -c` for read-only route inspection if available. Do not use
   `jack_connect` or start a second JACK server. Save a new test snapshot.
3. Find each processor's ID in that snapshot or its
   `midi-human-looper/processor-N/engine.log`. Open Firefox at
   `http://ZYNTHIAN_IP:PORT`, where PORT is `web_port_base + N` (normally 8765+N).
   Enter the existing editor token locally; do not include it in test reports.
4. Record Piano for two bars, then Bass while Piano continues, then Synthesizer.
   Overdub Piano. STOP Bass alone. Verify other phrases and parameters do not
   change. Record a result for each step, not just that the editor loads.

Confirm the running binary revision through the state API's `buildRevision`.
It is embedded at compile time; `.dirty` means tracked changes existed at build.
It is distinct from the mutable parameter `revision` and `engineSessionId`.
An older/manual build may report `unknown` and must not be treated as identified.
Record the checkout revision and JSFX SHA256 separately: the host loads JSFX from
disk at startup, so the binary revision alone does not identify that source.

Collect per-processor evidence while playing (no token or phrase contents saved):

```sh
python3 scripts/monitor-live-engine.py \
  --socket /zynthian/zynthian-my-data/midi-human-looper/processor-1/control.sock \
  --seconds 60 > /tmp/mbmf-processor-1-evidence.json
```

Substitute the real IDs. This issues one read-only query per second, outside the
MIDI callback. Nonzero exit means diagnostics need review. It does not fix, reset
or restart anything. Retain `engine.log`, the evidence report, UI/JACK log interval,
and `ps -eo pid,comm,pcpu,rss` observations. Use the existing Zynthian XRUN display
or JACK logs: `lateBlocks` counts XRUN notifications delivered to this native JACK client;
it is not a complete graph-wide XRUN history.

## Physical checklist and pass criteria

Record revision/source hashes, image/UI version, synths, tempo, sample rate and
buffer size with every run. Start with your working audio settings. For each
supported 128/256/512-frame and 44.1/48 kHz combination, change settings only via
Zynthian's normal user interface and restore them afterwards. Never run the
cloud dummy-JACK regression suite on the live graph.

| Exercise | Required observation |
|---|---|
| Three loops for 10 minutes; record/overdub while others play | Stable shared wraps; independent phrase memory |
| Chords, overlapping repeated notes, sustain down/up | Correct releases; no unintended channel leakage |
| STOP one chain, global transport STOP, PANIC | No owned notes remain; other-chain STOP isolation |
| Helix unplug/replug; Firefox close/reconnect | No replayed stale command; autonomous playback continues |
| Destination port interruption and restoration using normal chain UI | Safe note cleanup; recovery documented; no runaway feedback |
| CPU/RSS and XRUN monitoring with three tabs and synths | No growing memory/queues or new overflow/gap counters |
| SAVE, COMMIT RESTART STATE, UI restart, explicit snapshot restore | Correct selected restoration authority; restored stopped |
| Revision conflict and interrupted transfer | Existing live project survives; deliberate retry/adoption |
| Rollback to saved checkout/configuration | Previous instrument and data remain usable |

A failure rejects qualification for that configuration. A successful repeat does
not erase an earlier failure. Cloud evidence previously showed a missed 8192-frame
callback and recording rejection, despite a 28.2 ms maximum callback below the
170.7 ms block period. Scheduling delay/transport discontinuity remains unresolved;
the recording safety rejection must stay enabled. These measurements cannot
certify low-buffer Pi reliability or identify a specific hardware fault.

## Recovery and rollback

If registration refuses, do not hand-edit around the guard: preserve its error and
continue with the old setup. If startup fails, inspect the affected processor's
`engine.log`, configuration paths, executable architecture and available ports.
An occupied/stale socket is intentionally refused: first verify no process owns
it; do not delete sockets belonging to running processors. Close/remove only the
failed test processor using the normal UI.

For rollback STOP/PANIC all test processors, run the candidate's hash-checked
installer rollback, restore the backed-up MBMF data/configuration and previous
checkout/binary, then reinstall the previous adapter from its checkout. Restart
only the UI and load the backed-up Zynthian snapshot. If rollback's hashes refuse,
retain all files and inspect intervening UI edits; never overwrite a newer chain
manager wholesale. Saved phrase/project files are retained by installer rollback.

See [REAPER acceptance](reaper-studio-live-acceptance.md) for the studio half.
