# Native Oram destinations: routing qualification

## Finding and fix

Oram does not infer connections to synth chains from MBMF's MIDI channel output.
An empty MBMF chain `midi_out` produces no synth route. Registering engine MB is
not enough. A manual `jack_connect` creates an unmanaged connection; Oram may
remove it on the next graph refresh.

Use native chain destinations. The adapter now exposes **MIDI OUT** controller
pages listing current instrument-chain titles and MIDI channels. Select each
intended destination once; `chain.toggle_midi_out(chain_id)` rebuilds Oram's graph
and requests its autoconnect. There is no synth-name lookup, private JACK router,
service change or extra MBMF process. Inline insertion into a synth chain does
not expose fanout controls or change its existing internal route.

A second defect is corrected: MBMF's client prefix used `^mbh_N:`. Oram treats
sources as regexes but escapes destination names. Escaping that caret prevents
routes *into* MBMF from matching its actual input. The literal prefix `mbh_N:`
works in both paths and still distinguishes processor 1 from processor 10.

Destinations are explicitly selected, never all instruments connected by default.
New chains appear when MBMF controls are refreshed/reopened. Existing routes
remain native chain state; Oram snapshots restore them and native autoconnect
recreates them after port/chain refresh. Host chain IDs do not enter portable
project files. Removal/recreation of a chain invalidates stale editor controls,
including a reused chain ID. Feedback candidates are omitted and rechecked at
activation. Rejected changes restore the knob to authoritative route state.

Route changes are refused while MBMF reports notes, instances, recording,
playback or active MOVEMENTs. No implicit PANIC is sent: existing PANIC includes
channel-mode messages and could silence unrelated synth notes. Set up routing
at rest. The native Chain Options route editor remains available; it does not
have this adapter guard. Stop/release notes before using it or removing a chain.
This is not a guarantee of atomic topology editing during incoming MIDI bursts.

## Essential channel limitation

Oram's direct chain route reaches the first MIDI processor or synth input. It
**bypasses the destination ZynMidiRouter channel filter/remapper**. CH2 in a chain
header alone cannot guarantee that an omni synth ignores CH1/CH3. Each receiving
synth must actually filter its assigned MIDI channel, or have a verified native
channel filter before it. Disable duplicate direct hardware input using native
chain input controls. Do not add a return route into MBMF.

For the reported Surge test, select the Surge chain in MBMF's MIDI OUT controls
(or native **Chain Options → MIDI Output → Chain inputs**). Verify Surge itself
accepts CH2 only. If it is omni, a channel filter is required; this PR does not
pretend that channel fanout alone isolates three instruments.

## Installation after review (no remote deployment performed)

Keep the current running installation and backups. Use the existing reversible
updater with the **reviewed SHA**, not a moving branch. See
[updater procedure](zynthian-runtime-update.md) for the current command and
rollback syntax. Do not install packages or change JACK services for this fix.
Updating the native binary alone does **not** replace Oram's installed Python
adapter: run the registration installer with `--upgrade-adapter` to
upgrade its owned adapter explicitly. `--rollback-adapter` restores only its
previous bytes and leaves registration/runtime/projects intact. Its preflight refuses unowned modifications and
retains backups. The established installer procedure and rollback are in
[Oram discovery](zynthian-oram-discovery.md).

Before any runtime/UI restart: save your Zynthian snapshot and MBMF project,
stop playback and release keys/pedal. A UI/runtime restart interrupts MIDI
performance. Confirm the adapter no longer contains `'^'+name` and that the
runtime build revision matches the reviewed SHA. No token, port, project,
LUMAZ, synth preset or native connection policy should be replaced.

### Minimal PuTTY commands for an existing compatible runtime

Use the existing Git checkout solely to fetch and stage reviewed installer files;
these commands do not switch its working tree or overwrite the running sources.
Replace `/path/to/existing/checkout` and the SHA. First save snapshots and stop
performance. This adapter slice is tested against the #62 dependency stack;
compatibility with the physically installed runtime must be reviewed before use.
It does not upgrade or qualify an older engine automatically.

```sh
MBMF_SHA=REVIEWED_40_CHARACTER_SHA
git -C /path/to/existing/checkout fetch origin "$MBMF_SHA"
MBMF_STAGE=$(mktemp -d)
git -C /path/to/existing/checkout archive "$MBMF_SHA" zynthian | tar -x -C "$MBMF_STAGE"
MBMF_BINARY=$(python3 -c 'import json; print(json.load(open("/zynthian/zynthian-my-data/midi-human-looper/install.json"))["binary"])')
sudo python3 "$MBMF_STAGE/zynthian/install.py" --check --upgrade-adapter --binary "$MBMF_BINARY"
sudo python3 "$MBMF_STAGE/zynthian/install.py" --upgrade-adapter --binary "$MBMF_BINARY"
sudo systemctl restart zynthian
```

Stop if preflight fails. Do not bypass ownership checks. Inspect with
`journalctl -u zynthian -n 40 --no-pager` and native Chain Options. The restart
interrupts UI-managed MIDI and potentially synth audio; JACK is not restarted.
Keep the staging directory until qualification. Adapter-only rollback:

```sh
sudo python3 "$MBMF_STAGE/zynthian/install.py" --rollback-adapter
sudo systemctl restart zynthian
```

The previous adapter remains in hash-addressed `adapter-upgrades/` backups.
The installer validates bytes/ownership, fsyncs and replaces files atomically,
and compensates caught failures. It is not a power-loss-proof multi-file
transaction; preserve backups and inspect metadata after an interrupted update.

## Physical acceptance on Oram-2601.1 / V4

1. With playback stopped, create one MBMF MIDI Tool chain and three instrument
   chains. Confirm receiving synth/filter channels 1, 2 and 3 individually.
2. In MBMF controls, reopen/refresh and enable their MIDI OUT destinations.
   Alternatively use the existing native chain output selector. No terminal
   `jack_connect` should be required.
3. Record/play notes and CCs on each channel. Only the intended synth sounds;
   no double keyboard delivery. Change the focused chain: routing stays active.
4. Trigger CONDUCTOR PHRASE/MOVEMENT STEPs and sustain overlapping notes. STOP
   and existing PANIC leave no held notes. Disconnect the browser: continue.
5. Try changing an MBMF route while notes/MOVEMENTs run: it must be refused;
   stop/release everything, then change it successfully.
6. Save a Zynthian snapshot, restart the UI and restore. Verify destinations,
   project data and stopped restoration. Stop before deleting a destination;
   reopen controls, recreate it, and explicitly select its new destination.
7. Verify rollback restores the prior adapter/runtime/configuration. Do not
   reopen new free-time projects on an older grid-only runtime expecting silent
   truncation; preserve their data and heed compatibility errors.

## Automated evidence and limits

`tests/test_zynthian_destinations.py` executes the production adapter control
path with pinned native Oram chain/graph excerpts. Tests cover three selections,
idempotence, native state restoration, insertion mode, stale/reused IDs,
feedback, refused active edits and failed observation. UI controller construction
is stubbed; this is not the complete Oram UI process.

`CHAIN_NATIVE_ROUTES=1 tests/test_zynthian_dedicated_chain.py` starts the actual
MBMF adapter/native engine and private dummy JACK. The probe does **not** connect
MBMF output. The pinned Oram resolver computes desired destinations; the test
applies those to real JACK ports. It checks three identical chronologically
ordered streams, notes/CCs, source recording/export, LOOP/ONCE/HOLD, real ARP,
STOP, transport restart and processor removal. Receivers explicitly model
channel filtering; no physical synth or full Oram daemon is claimed.

The retained initial failure (`initial-startup-panic*`) showed sequential implicit
PANIC during route setup delivering different setup safety messages to receivers.
The implementation was changed to explicit idle-only route configuration, not
weaker stream assertions. The exact equality assertion remains intact.

Cloud JACK runs cannot qualify Pi latency, XRUNs, Surge's receiver filtering,
Helix, actual Oram snapshot restoration or physical disconnect recovery. #63
still documents unqualified live timing and a failed combined Chromium run.
