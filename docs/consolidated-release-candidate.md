# Consolidated software candidate: first studio/live test

This is a review candidate, not a hardware-qualified release. Full control/snapshot
REAPER parity is incomplete. The current status authority is [capabilities.md](capabilities.md).
Nothing was merged automatically during consolidation.

## Checkout and build

Use the top of the reviewed stack; all prerequisites are ancestors:

```sh
git fetch origin integration/studio-live-rc:refs/remotes/origin/integration/studio-live-rc
git switch integration/studio-live-rc
python3 scripts/generate-parameters.py --check
YSFX_SOURCE=/path/to/pinned/ysfx YSFX_BUILD=/path/to/pinned/ysfx/build \
  HEADLESS_BINARY="$PWD/.build/midi-headless-engine" scripts/headless-build.sh
```

ysfx must be pinned at `8077347ccf4115567aed81400281dca57acbb0cc`; JACK development
headers and the existing system JACK library are build prerequisites. Reuse the
existing setup. `scripts/headless-setup.sh` is optional dependency preparation and
runs apt via sudo: review it on the target rather than modifying the OS as part of
a software update. This session did not change OS configuration or services.

Back up your existing Zynthian snapshot, repository version and
`midi-human-looper` data directory. STOP/PANIC before updating a processor.
For a previously installed adapter, follow the existing hash-checked registration
rollback, then reinstall the updated adapter; saved data/configuration are retained:

```sh
python3 zynthian/install.py --rollback
python3 zynthian/install.py --binary "$PWD/.build/midi-headless-engine" --lan
```

For a first install omit rollback. Existing install.json is preserved, including
its timing selection. New configuration selects v2; an old missing field means v1.
Opt into `chain_timing_version: 2` deliberately only after backing up patches and
checking grid compatibility. Do not change JACK settings or restart unrelated
services. The existing native installation guide describes the UI registration
activation; no service action was executed during this implementation.

For a standalone test on an already running JACK server, use the existing host and
HTTP commands in [studio-live-bridge.md](studio-live-bridge.md), adding `--chain
--chain-timing 2` only if the two-bar native execution contract is desired. Use
`--restore-active-project` for standalone autonomous committed restoration. Do not
launch a second host on a native adapter's socket or ports.

## Musical acceptance procedure

1. Configure independent Piano/Bass/Synth Zynthian chains with the existing native
   MIDI Tool. Use the same timing version, fixed 4/4 and tempo on all three. Verify
   isolation and normal Zynthian autoconnect; no handwritten JACK connections.
2. Copy the updated JSFX and all companion Lua files together to REAPER as described
   in the bridge guide. Start its existing Python companion with the intended
   processor endpoint and private LAN token. Never reuse a wrong processor pairing.
3. In REAPER create a two-bar note-only take with a chord, staggered attacks,
   overlapping repeated pitches, rests and release velocities. SEND to the chosen
   stopped phrase; review replacement, then play it through Piano. Bass and Synth
   must remain independent. Oversized/incompatible material must refuse, not truncate.
4. Record/overdub a different phrase in Bass while Piano continues. STOP Bass and
   GET it into a new REAPER item. Compare source channels/pitches/velocities/durations
   and offsets; neither host tempo should change.
5. STOP and COMMIT RESTART STATE on the edited native processor. Inspect the saved
   revision. Close Firefox/companion and disconnect the network. Restart only the
   test processor without an overriding Zynthian snapshot; source/configuration
   must restore stopped. Start playback manually; verify pairing and no stuck notes.
6. Test a compatible shared-base full project with PUSH/PULL. Exactly one recognized
   track JSFX may be open across REAPER projects. Change live state, verify stale
   PUSH/commit conflicts, PULL/adopt intentionally, then commit again. Native-only
   Controller/Snapshot execution in REAPER must refuse and preserve original data.
7. Verify slot SAVE does not silently change restart authority, and explicit
   Zynthian snapshot recall overrides portable restore. Verify snapshot and physical
   Controller behavior in native execution, without claiming shared REAPER policy.
8. PANIC, STOP, bypass/delete an existing supported module and instrument while
   playing. Verify counted note cleanup and other-processor isolation. Test Helix
   unplug/replug and JACK port loss on disposable data, recording actual outcomes.

## Regression commands

In the configured cloud workspace (dummy JACK only):

```sh
CHAIN_JACK_BLOCK=8192 PATH=/workspace/setup-tools/venv/bin:$PATH \
YSFX_SOURCE=/workspace/setup-tools/ysfx YSFX_BUILD=/workspace/setup-tools/ysfx/build \
JACK_INCLUDE=/workspace/scratch/midi-deps/root/usr/include \
JACKD=/workspace/scratch/midi-deps/root/usr/bin/jackd \
JACK_DRIVER_DIR=/workspace/scratch/midi-deps/root/usr/lib/x86_64-linux-gnu/jack \
HEADLESS_BINARY=/workspace/scratch/midi-headless-engine-rc \
python3 scripts/combined-test.py --native --jack --browser chromium
```

Do not run dummy-server tests against a live Zynthian graph. For the separate legacy
transport regression set `CHAIN_TIMING_VERSION=1`; v2 is the test default. Browser
observation now shares one cached native state query per 250 ms window across
subscribers, invalidated by commands. Command/API reads remain uncached; MIDI
execution and control timing do not depend on this UI observation interval.
Tests cover shared observations, command invalidation, real websocket reconnect,
controller choices/DONE/CANCEL and existing MIDI lifecycle. This limits duplicate
observer work; it is not a measured Pi CPU optimization claim.

Controller TAKEOVER, BACK TO STATE and EASING now use named choices from descriptors
instead of requiring numeric enum knowledge; less-used numeric settings are collapsed
under ADVANCED OPTIONS. Policy values and persistence remain
unchanged; no extra editor/framework is introduced.

## Qualification and rollback

The pre-observation combined suites passed. A subsequent fresh RC run aborted a
three-chain recording after a detected missed JACK callback (equal transport and
clock gaps of 8192 frames, with XRUNs reported). The engine correctly rejected the
interrupted take; the underlying cause is not established. This failure is retained
as evidence and does not qualify reliability merely because another run passes.
There was no safety-check relaxation or automatic retry in the test. A separate
full rerun subsequently passed, including native/JACK/JSFX/Controller/Snapshot,
interchange, authority/rollback and all Chromium workflows. The separate legacy v1 three-processor JACK workflow also passed. The earlier
missed callback still prevents a hardware reliability claim.


Required physical validation: actual REAPER APIs/RPP save and restart, full Firefox
editor, Pi 128/256/512-frame settings as supported, XRUNs/deadlines/CPU/RSS under
three chains and multiple editors, Helix learning/takeover/reconnect, destination
port loss, Zynthian snapshots and interrupted/power-failed transfer. Automated
cloud checks are functional evidence only; no hardware or latency pass is claimed.

Rollback after STOP/PANIC: restore the backed-up compatible repository/effect,
binary/configuration/data and prior registration using its documented hash checks.
Keep old timing v1 if restoring its old projects. Never delete unrelated services,
reset the global JACK graph or remove LUMAZ. Staged uncommitted revisions are not
automatic restart candidates; inspect ambiguous transfer/commit failures before
retrying. Core Controller/Snapshot cross-host policy sharing and scheduled module
continuation remain the next coding tasks, not features completed by this candidate.
