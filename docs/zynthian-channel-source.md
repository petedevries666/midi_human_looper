# Dedicated MBMF source through Oram's MIDI channel filter

This focused correction replaces #64's direct synth destinations for a dedicated
MBMF chain. It is stacked on #66 (#64 / #62 ancestors), but installing these Python
files does not require upgrading the native binary, Webconf or musical project.
No engine, Web UI, project schema or operating-system service configuration changes.

## What changes

Oram discovers `mbh_<processor>:midi_out` as an input device and connects it to its
allocated `ZynMidiRouter:devN_in`. Existing `chN_out` connections feed receiving
chains through their native channel filter. The input uses MULTI, independently
of UI focus. Only dedicated chains whose last MIDI processor is MB qualify.
Insertion inside a synth chain keeps its existing internal route.

The additive worker-side hooks run inside Oram's autoconnect transaction, never
in JACK's audio callback. Every native graph refresh/snapshot restoration reapplies
routing. MB-containing chains and chains with a return route into MB are excluded.
Old #64 direct destinations are suppressed in the desired graph, without deleting
snapshot configuration. Other MIDI sources, synth routing and audio graph remain
unchanged. Removing MB restores the input slot's previous mode/routes before reuse.
The adapter hides #64's direct destination knobs when this helper is installed.

An available native input-device slot is required. If Oram has exhausted its input
slots, this feature cannot route another source. Arbitrary downstream MIDI-FX after
MB and multiple MB-to-MB chains are not supported by this correction.

## Channel controls: explicit scope

Existing Instrument INPUT ALL / 1–16 and fixed OUTPUT 1–16 continue working;
notes, incoming channel-voice messages and generated ARP use existing engine paths.
MOVEMENT CC targets already specify an explicit channel; these now traverse the
same receiving-chain filter.

**This PR does not complete the requested channel-control extension.** Instrument
output 0 remains legacy ORIGINAL, not broadcast ALL. Per-PHRASE ORIGINAL / ALL /
1–16 override and instrument-inherited MOVEMENT targets are still absent. The
16-channel broadcast needs an emission/ownership change and compatibility tests;
relabeling ORIGINAL as ALL would be incorrect. Existing projects stay identical.
This is ready for reviewing the routing correction, not full channel acceptance.
Do not delay the separate fixed-channel hardware routing test for these gaps.

## In-place installation after review (PuTTY, existing checkout)

STOP MBMF, release keys and save the Zynthian snapshot first. These commands stage
only the installer/adapter Python files temporarily; there is no second clone,
installation or native rebuild. Substitute the reviewed immutable SHA below.

```sh
cd /root/midi_human_looper
git fetch origin fix/oram-filtered-channel-source
sha=REVIEWED_SHA
stage=$(mktemp -d)
git archive "$sha" zynthian | tar -x -C "$stage"
binary=$(python3 -c 'import json; print(json.load(open("/zynthian/zynthian-my-data/midi-human-looper/install.json"))["binary"])')
python3 "$stage/zynthian/install.py" --binary "$binary" --native-channel-routing --upgrade-adapter --check &&
python3 "$stage/zynthian/install.py" --binary "$binary" --native-channel-routing --upgrade-adapter &&
systemctl restart zynthian
```

The last command restarts the **Zynthian UI and its hosted chains**, interrupting
playback. It does not restart JACK, networking or LUMAZ. If validation refuses a
changed owned file/unsupported Oram source, stop: no forced overwrite.
Configuration, tokens, ports, projects and snapshots are retained. Original source
bytes/modes are backed up atomically by the existing installer.

Routing-only rollback (same temporary installer; no runtime/registration removal):

```sh
python3 "$stage/zynthian/install.py" --rollback-channel-routing && systemctl restart zynthian
```

`--rollback-adapter` independently restores the previous adapter if desired.
Keep the staging directory until qualification/rollback completes.

## Short physical test

1. One dedicated MB MIDI Tool chain, native chain MIDI channel ALL. Create synth
   chains CH2, CH3 and CH4; keep their independent presets/mixers.
2. In the native MIDI-input selection, use the MB source for receivers and disable
   the physical keyboard on receivers to prevent a separate hardware-through path.
   Route keyboard/Helix to MB through native device settings (MULTI plus MB-only
   admission if focus-independent physical input is needed).
3. Set MB Instruments IN1, OUT2 / OUT3 / OUT4. Play CH1. Inspect `jack_lsp -c`:
   MB output must connect only to its `ZynMidiRouter:devN_in`, with no synth port
   shortcut. Check receiver isolation by disabling two MB Instruments at a time.
4. Set a MOVEMENT's explicit channel to 2, 3 or 4; check only that chain responds.
5. Change focus, recreate a synth chain, save/restore snapshot and restart UI;
   repeat. Test overlapping notes, sustain, STOP/PANIC and removal after releasing
   keys. Confirm no duplicate attacks/hanging notes or return path into MB.

Existing global PANIC may emit safety channel-mode messages on all channels; this
PR does not narrow its scope. It is not a guarantee of per-Instrument PANIC isolation.

No physical V4/Oram-2601.1 qualification has been performed in Cloud.

## Executed checks

See `docs/evidence/oram-channel-source/` for logs. All commands exited 0:

```sh
python3 tests/test_zynthian_channel_source.py # 4 native API-call/lifecycle tests
python3 tests/test_zynthian_install.py        # 30 fresh/upgrade/repeat/rollback tests
python3 tests/test_zynthian_destinations.py   # 7 legacy adapter compatibility tests
python3 tests/test_zynthian_routing.py        # 5 pinned legacy route tests
source /tmp/mbmf-b-env.sh                     # Cloud-specific cached prerequisites
scripts/headless-build.sh
c++ -std=c++11 -O2 tests/zynthian_chain_jack.cpp -I"$JACK_INCLUDE" -l:libjack.so.0 -lpthread -o /tmp/mbmf-channel-probe
CHAIN_NATIVE_ROUTES=1 CHAIN_JACK_PROBE=/tmp/mbmf-channel-probe "$TEST_PYTHON" tests/test_zynthian_dedicated_chain.py
```

The actual native engine/dummy-JACK fixture checks three-channel emission,
recording, LOOP/ONCE/HOLD, ARP and cleanup. It exercises **the old fanout probe**,
not a live ZynMidiRouter, so it is engine compatibility evidence only. Native
router configuration is tested by capturing actual production helper calls to
Oram's `zmip_set_flag_active_chain` / `zmop_set_route_from`; Cloud has no zyncore
hardware runtime. The full pinned Oram source at commit
`11d4e858367db465a431c701d9035432742a5a7d` accepted the MIDI-only hooks, repeated
patching was identical and removal restored exact bytes. Audio's similar loop
was left unchanged. Issue #54's 25 protected working files were hash-verified.
No UI files changed; no screenshot or unrelated full regression campaign needed.
