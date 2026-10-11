# Reviewed runtime update: Zynthian V4 / Oram ARM64

This updater changes **only MBMF's runtime paths in its existing `install.json`**.
It does not install OS packages, register engines, change JACK connections, alter
Zynthian snapshots or touch LUMAZ. It requires an existing issue-26/PR47 installation
and the build dependencies already used for that installation. Missing dependencies
abort before activation. Never run this during a performance.

## Before updating

1. STOP every MBMF processor, finish recording and snapshot morphs, and release keys.
2. Save your current Zynthian snapshot. Oram owns the chains and restores its snapshot;
   an unsaved chain layout cannot be recovered by a runtime updater.
3. Keep a second PuTTY terminal available. The updater validates the candidate in a
   private engine without JACK, checkpoints stopped MBMF projects, and backs up
   MBMF project/patch data, configuration and the authentication token.
4. Use the full **reviewed commit SHA**, not an unreviewed branch name.

After review, run from your existing repository checkout (replace both placeholders):

```sh
sudo python3 /path/to/midi_human_looper/scripts/zynthian-update.py --revision REVIEWED_40_CHARACTER_SHA
```

For an installation predating this script, the first update can also be one
command from PuTTY (replace the path and SHA in both places):

```sh
bash -o pipefail -c 'git -C /path/to/midi_human_looper fetch origin REVIEWED_40_CHARACTER_SHA && git -C /path/to/midi_human_looper show REVIEWED_40_CHARACTER_SHA:scripts/zynthian-update.py | sudo python3 - --revision REVIEWED_40_CHARACTER_SHA'
```

This fetches metadata without changing your working tree. It executes only the
reviewed script and does not activate the runtime until validation succeeds.
No manual removal or re-registration is needed. Releases are isolated under
`/zynthian/zynthian-my-data/midi-human-looper/releases/<sha>/`.

The pinned ysfx/WDL library and application are built with `-fsigned-char` on
ARM64. No third-party source editing or package installation occurs. Configuration
replacement uses fsync and atomic rename. The token, network ports, timing version
and unknown configuration keys are retained.

## What restarts

**The existing `zynthian` UI service is stopped and started.** It owns the MBMF
children, so there is no independent MBMF service to restart safely. This interrupts
UI-managed MIDI processing and can interrupt instrument playback/audio. JACK itself
is not restarted. The saved Zynthian chain graph is restored by Oram. Do not use this
command as a seamless live update.

Activation checks UI health, each previously running MBMF processor's exact build
revision and restored source-project fingerprint, and its authenticated browser API.
If any check fails, the old runtime configuration is restored and the UI started
again. A rollback failure leaves the durable pending journal for recovery; it is
reported as failure, never as successful activation.

## Rollback and recovery

One command rolls back the last completed runtime update:

```sh
sudo python3 /zynthian/zynthian-my-data/midi-human-looper/releases/REVIEWED_40_CHARACTER_SHA/scripts/zynthian-update.py --rollback
```

Current musical data is kept, validated against the older executable, and
checkpointed; rollback does not silently overwrite newer edits with old backups.
If a build/preflight fails, nothing is activated. If power is lost during activation,
rerunning either command first restores the journaled old configuration, validates
it and exits with a recovery message; inspect your restored state before retrying.

Backups are under `midi-human-looper/backups/<timestamp>/`. Do not delete releases
referenced by `install.json` or `runtime-update.json`. If the UI cannot restart,
inspect `systemctl status zynthian` and `processor-*/engine.log`; no installer or
JACK changes are required for recovery. A missing or incompatible binary aborts
rather than attempting a destructive reinstall.

## Verify on the actual device

- Open each configured editor at its existing port and with its existing token.
- Expand diagnostics and check `buildRevision` equals the reviewed SHA.
- Verify the Bass/Piano/Synth chain layout and MIDI channel destinations survived.
- Record from ONCE and LOOP at arbitrary transport phases, export MIDI into REAPER,
  and check the first positive Note On is tick zero and note lengths are unchanged.
- Test held mouse/touch/Helix triggers, short taps, release, STOP and PANIC.
- Check saved phrases, controller assignments, snapshots and transformer parameters.
- Perform one rollback while stopped, then confirm these same checks.

Automated tests use a real native preflight engine and mocked service transitions.
No real Oram restart, ARM64 build or physical device update has been executed in
Codex Cloud. Those are mandatory physical acceptance tests before release.
