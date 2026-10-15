# MBMF exclusive native input (draft, not hardware-qualified)

## Why this is necessary

On the user's Zynthian Oram Kit V4, the JACK graph showed:

- Physical MIDI input: `system:midi_capture_1 -> ZynMidiRouter:dev0_in`
- Dedicated MBMF: `ZynMidiRouter:ch0_out -> mbh_1:midi_in`
- Synth: `ZynMidiRouter:ch1_out -> synthv1-01:in`
- MBMF virtual source: `mbh_1:midi_out -> ZynMidiRouter:dev2_in` when enabled.

The keyboard remained audible with MBMF's JACK output disconnected. This proves
a native physical-input bypass into the synth. The phrase recorded successfully
with that link disconnected, but recording failed and the synth became choppy
when MBMF output was reconnected. At idle, the PR #83 virtual-source firewall
alone had passed (zero MIDI and zero XRUN delta), but **REC failed**.

The JACK graph does not expose the internal native dev-to-chain matrix. In
particular, Zynthian's chain manager enables every input device for every
new MIDI chain by default. There is also an internal `zynsmf:midi_out ->
ZynMidiRouter:seq_in` path and every chain's output is sent to
`zynsmf:midi_in`. We have **not proven** that ZynSMF actually echoes during
REC; its return to MBMF is blocked defensively in this opt-in policy.

## Opt-in exclusive routing

The helper reads the existing installation configuration:

`/zynthian/zynthian-my-data/midi-human-looper/install.json`

Optional field:

```json
"exclusive_midi_input_ports": ["system:midi_capture_1"]
```

The list contains **exact JACK input source port names**, not Zynthian chain
IDs, MIDI channels, or synth engine names. Empty or missing means **off**:
**the MBMF virtual MIDI output is fail-closed (not attached to devN_in)**.
A malformed JSON document or unrecognized keyboard port also blocks the
virtual route. Native MIDI routes are not implicitly activated without opt-in.
The listed source must exist in a native physical input slot. Invalid
configuration or a missing named source **blocks the MBMF virtual output**,
rather than connecting an unverified routing matrix.

When enabled with one dedicated MBMF chain:

1. Set each selected physical input to native MULTI, and allow it to reach
   the MBMF chain. Disable that physical input's native route to all other
   MIDI chains, including the synth. This removes the bypass.
2. Permit MBMF's virtual input to reach only terminal synth chains, using
   the existing per-channel ZynMidiRouter filter. It cannot reach MBMF.
3. Disable native `seq_in`, `step_in`, and internal CV/Gate input to
   the MBMF chain, so transport/SMF/step events cannot form a return loop.
   Their routes to other chains are unchanged.
4. Preserve unrelated hardware MIDI sources, including `ttymidi:MIDI_in`
   and the VideoTrigger connections.
5. Verify every native setter via getter readback; on failure restore the
   original physical routing and keep the virtual MBMF output disconnected.
   Reapply after autoconnect and restore saved routes/modes when the feature
   is disabled or the MBMF chain is removed.

This is a **single dedicated MBMF chain** prototype. Multiple dedicated
MBMF chains are intentionally rejected by the strict policy. It does not
change the engine binary, web editor, patches, snapshots, or Zynthian JACK
connection manager beyond the previously installed owned helper.

## Deployment: do not reconnect the old output manually

Save a Zynthian snapshot, stop transport and back up `install.json`.
Keep `mbh_1:midi_out` disconnected until the updated helper and opt-in
configuration are installed, and Zynthian UI has restarted.

Use the reviewed immutable commit from PR #83. Stage the `zynthian/`
directory, use the existing `--binary` and `--native-channel-routing
--check` preflight, then install the helper without `--upgrade-adapter`.
The existing managed installer preserves the config and all unrelated files.
Restart only the Zynthian UI. **Never manually connect MBMF to a named synth**.

Activation is an explicit separate config edit, not an installer side effect.
Only use the exact input port verified on the user's machine. On rollback,
restore the original config backup, reinstall the previous reviewed helper or
run `--rollback-channel-routing` using the staged installer, and restart
Zynthian UI. A failed installation check must cause no writes.

## Physical acceptance: stop on the first failure

1. Verify `mbh_1:midi_out -> ZynMidiRouter:dev2_in` appears after restart,
   and that there is no direct synth shortcut.
2. At idle, measure MIDI and XRUN deltas for 2 seconds: both must be zero.
3. Play a few notes; verify one attack, no doubled monitoring or chopping.
4. REC one empty phrase, FINISH, PLAY. No ERROR or callback overload.
5. Check MIDI channel isolation, ZynSMF transport, VideoTrigger, other
   input devices, and snapshot/chain recreation. Validate live route matrix
   via a diagnostic inside Zynthian's initialized runtime, **not** a
   standalone Python import of `lib_zyncore`.
6. On MIDI storm or choppy audio, disconnect `mbh_1:midi_out` from its
   native `devN_in` and stop testing.

**Current validation:** GitHub Actions run 38789501210 passed **67/67 tests**
(14 exclusive-route, 7 feedback-guard, 4 channel-source, 30 installer, 7 adapter,
5 legacy routing) and successfully compiled the safety smoke monitor.
**No Pi/ZynMidiRouter REC acceptance yet.** This remains DRAFT / DO NOT MERGE.

For supervised smoke testing after review, run:
```sh
python3 scripts/zynthian-m3-safe-smoke.py           # 2 seconds at idle
python3 scripts/zynthian-m3-safe-smoke.py --seconds 15 # while playing/recording
```
The monitor NEVER reconnects a port; on MIDI storm, XRUN burst, chain ERROR,
or status failure it executes an emergency `jack_disconnect` for the native
virtual destination. It does not operate Zynthian's instrument/transport UI.
