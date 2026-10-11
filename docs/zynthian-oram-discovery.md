# Oram discovery fix and dedicated MIDI chain qualification

Base: `integration/studio-live-rc` / PR #44, commit `b3031934`. No musical engine,
JSFX, web UI, JACK configuration or hardware service is changed by this fix.

## Discovery and installation

Audited official zynthian-ui Oram revision
`11d4e858367db465a431c701d9035432742a5a7d`:
`zyngine/zynthian_lv2.py`, `zynthian_chain_manager.py`, `zynthian_chain.py`,
`zynautoconnect/zynthian_autoconnect.py`, and the native MIDI configuration GUI.
`Other` is explicitly a MIDI Tool category; SysEx and MIDI Control already use it.

The selector reads `engines_by_type`, not just the manager's engine_info. MB is now
registered before that index is rebuilt and in the standalone catalog definitions
used for regeneration. The manager retains only class registration and instance
creation hooks. Existing catalog metadata and unrelated entries are preserved.
No engine catalog JSON, routing state or Zynthian snapshot is rewritten by the installer.

A managed issue-26 installation upgrades in place. Its adapter, binary/repository
configuration, bind/port, token and patch files remain unchanged. Original source
backups are retained, and `pre-oram-upgrade/` stores the previous registration,
catalog, adapter and manifest. Modified owned files or conflicting backups are
rejected before activation. Each file is replaced atomically; caught installation
failures restore prior files. This is not a power-loss-proof multi-file transaction.
After a hard interruption, preserve the backups and inspect the manifest/source
hashes before retrying; do not remove ownership checks.

## Minimal PuTTY commands after review

First save your Zynthian snapshot, stop recording/playback and PANIC. Use a separate
checkout so this catalog-only fix cannot change the running project's JSFX/server
while retaining its installed binary. These commands assume the standard Oram paths
and existing issue-26 installation:

```sh
git clone --single-branch --branch fix/oram-midi-fx-discovery https://github.com/petedevries666/midi_human_looper.git /zynthian/zynthian-plugins/mbmf-oram-discovery-fix
cd /zynthian/zynthian-plugins/mbmf-oram-discovery-fix
binary=$(python3 -c 'import json; print(json.load(open("/zynthian/zynthian-my-data/midi-human-looper/install.json"))["binary"])')
python3 zynthian/install.py --check --binary "$binary"
python3 zynthian/install.py --binary "$binary"
systemctl restart zynthian
journalctl -u zynthian -n 40 --no-pager
git rev-parse HEAD
```

Run the restart only if your installed UI service is named `zynthian`; this restarts
UI, not JACK. No package install, rebuild, reboot or `--lan` change is needed.
For subsequent reviewed updates, use `git pull --ff-only` in this fix checkout and
repeat check/install. The printed Git revision identifies the discovery fix;
`install.json` still identifies the original runtime binary and repository.

Validate **Add MIDI-FX → Other → MIDI Bad Mother Fucker** in an existing MIDI chain,
and **Add MIDI Chain → Other → MIDI Bad Mother Fucker** for a dedicated chain.
Check again after a normal native engine catalog refresh and UI restart. Existing
engines must remain available. Registration survives regeneration and restart.

Rollback using this updated installer, after stopping/removing only MB processors:

```sh
cd /zynthian/zynthian-plugins/mbmf-oram-discovery-fix
python3 zynthian/install.py --rollback
systemctl restart zynthian
```

Rollback restores the original manager/catalog source and removes only owned
adapter/helper files. Saved patches, configuration, token and backups remain.
Do not use the old version-1 installer to roll back version-2 metadata. If Oram has
cached an MB entry during catalog regeneration, it becomes disabled when its engine
class is removed; a normal native catalog regeneration removes that cached entry.
Other engines and snapshots are retained. If preflight fails, leave the working
installation in place and inspect the reported file conflict before any restart.

## One shared processor: supported routing, important limitation

Oram natively supports a dedicated MIDI chain and **Chain Options → MIDI Output →
Chain inputs**. Select the Bass, Piano and Synth chains there. This uses native
`toggle_midi_out(chain_id)`, graph rebuilding and autoconnect, not a new JACK router.
Native destination IDs live only in Zynthian snapshots; portable MB projects retain
MIDI channel intentions and never acquire Zynthian-specific chain IDs.

However, direct chain output connects to the destination's first MIDI processor or
synth input, bypassing its ZynMidiRouter channel filter and channel translation.
**Setting Bass channel 1, Piano channel 2 and Synth channel 3 is not sufficient.**
All three inputs receive the complete stream. Each destination must have a verified
channel-aware synth or an existing native channel filter/mapper before the synth.
FluidSynth's router part translation also needs qualification. Do not assume an
omni synth is isolated, and do not introduce global routes to compensate.

Configure one MB chain receiving the intended channels, then three independently
configured instrument chains. Disable their direct physical keyboard/Helix inputs
through the native per-chain input UI so dry and processed notes cannot arrive twice.
Choose only outward MB → instrument routes; never route a destination back to MB.
Oram marks potential loops with infinity but does not prohibit every unsafe choice.
If your synth/filter cannot enforce channels, use the existing inline MIDI-FX mode
until a qualified channel-aware destination is available. Generic automatic
three-synth channel isolation is not claimed by this PR.

The existing shared engine timeline remains available; four-track CONDUCTOR,
HUMANIZER playback and MOVEMENT completion are outside this discovery fix.
PANIC before changing/removing a destination route: unlinking a sounding receiver
cannot deliver its later Note Off. Automatic held-note cleanup across arbitrary
external route edits is not claimed.

## Evidence and physical acceptance

Automated installer fixtures exercise fresh install, v1 upgrade, repeat installation,
catalog reload/regeneration, selector visibility, invalid taxonomy, ownership
conflicts, injected activation failure and exact rollback. Fixtures retain actual
Oram selector/index/routing excerpts; LV2 scanning and hardware objects are stubbed.
The native routing tests verify destination resolution, set-based connection
deduplication, removal and loop detection.

The real desktop JACK test runs one actual MB adapter/JSFX host, records and plays
three MIDI channels, fans out to three virtual channel-aware receivers, verifies
identical chronological streams, no duplicated delivery, channel isolation,
STOP/transport restart and instance-removal cleanup. This is not physical Zynthian
or synth validation and does not prove generic receiver filtering.

On your V4 after review:

1. Save a baseline snapshot; verify unrelated engines/routes before and after install.
2. Add one dedicated MB chain and three qualified receivers. Check CH1 reaches only
   Bass, CH2 only Piano, CH3 only Synth, including simultaneous/repeated notes.
3. Record/play a phrase, sustain notes, STOP and PANIC; verify silence and no stuck
   notes. Test transport stop/start and browser disconnect while playback continues.
4. PANIC, remove one destination route/chain, and verify the other two remain intact.
5. Save/restore a Zynthian snapshot; verify destinations and presets. Test catalog
   refresh/UI restart. Check engine logs, CPU and XRUNs at your actual buffer size.
6. Exercise rollback and confirm original engines, instrument configuration and
   snapshots remain usable. No physical Raspberry Pi or Helix results are claimed.
