# MBMF native MIDI feedback: hardware incident and safety correction

## Evidence from Zynthian Kit V4 / Oram 2601.1 (2026-10-15)

After enabling PR #67 native channel routing, a dedicated MBMF source was
connected to `ZynMidiRouter:dev2_in`. With keyboard and phrases idle, the
MBMF control socket reported:

| Metric | 2 seconds, connected | 2 seconds, disconnected |
| --- | ---: | ---: |
| `midiCount` delta | 38,103 | 0 |
| `lateBlocks` delta | 50 | 0 |
| `outputOverflow` delta | 0 | 0 |

Previously `maxCallbackUs=27709` with JACK `blockSize=256` at
`sampleRate=48000` (5.33 ms budget). Last observed MIDI event was
`[12071168, 186, 120, 0]` (CC120, channel 11). Keyboard notes were
chopped and phrase recording entered ERROR. Disconnecting **only**
`mbh_1:midi_out -> ZynMidiRouter:dev2_in` stopped both event flooding
and late blocks. This establishes a feedback path through the native
source, **not** which exact downstream chain completed the cycle.

Do not reconnect the old native source on this snapshot until qualified.

## Corrective policy

- Source `mbh_N:midi_out` may enter Oram's native `devN_in`, but
  **only synth-containing terminal chains** may receive its events.
  No other MIDI-only chain, including MBMF itself, is admitted.
- Also exclude synth chains whose `midi_out` reaches an MBMF chain.
  Reject JACK graph paths from an allowed chain's `chN_out` back to
  the source's `mbh_N:midi_in`.
- Disable all excluded native routes **before** enabling synth receivers.
  Verify each native `zmop_set_route_from` with `zmop_get_route_from`.
  On any mismatch/exception, close all routes from that source and omit
  the `mbh_N:midi_out -> devN_in` JACK connection from Oram's desired
  graph. Log the refusal.
- Preserve channel filtering in Oram; no synth-specific JACK cables,
  no audio callback changes, no changes to native engine recording.
- Do not change other devices' routes, snapshots, or MIDI chain routing.

This is a **fail-closed safety correction**. A failure to prove safe
routing intentionally produces silence from MBMF, rather than an
unbounded MIDI feedback storm.

## Validation status

Six new unit tests passed in a local Python 3 runtime, covering
independent synth channels, exclusion of MIDI-only chains, indirect
chain returns, JACK graph returns, failed native readback, source
removal and unrelated JACK routes. The pre-existing PR #67 source
tests were updated to use a stateful zyncore API mock.

**No live ZynMidiRouter or Raspberry Pi verification has been performed.**
These tests do not prove the precise original feedback path or that the
new code eliminates it on the affected snapshot. Do not merge or
declare the incident resolved before a hardware acceptance run.

## Hardware acceptance gate

1. Stage and check the exact reviewed commit with the existing Oram
   installer; do not change the native engine binary or Webconf.
2. Keep MBMF phrases stopped, with a single synth chain first.
3. Confirm native JACK graph: MBMF output goes only to `devN_in`,
   never directly to a synth input. Confirm no feedback to MBMF input.
4. Measure the control socket's `midiCount` and `lateBlocks` deltas
   with the keyboard idle. **Both must remain zero** for the test
   window. If not, immediately disconnect MBMF output from
   `devN_in` and roll back native channel routing.
5. Only then play a note, record a short phrase, and test channels
   independently. Verify 1-to-1 MIDI note on/off, no double attacks,
   no ERROR and no late block growth.
6. Replace a synth, restore a snapshot and restart Zynthian UI;
   repeat the idle and playback checks.

Rollback with the same staged installer:

```sh
python3 "$stage/zynthian/install.py" --rollback-channel-routing
systemctl restart zynthian
```

No auto-merge or automatic deployment.
