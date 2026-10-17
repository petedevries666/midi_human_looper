# PHRASE output channel

Open a PHRASE's pencil / PHRASE OPTIONS. **OUTPUT CHANNEL** offers ORIGINAL,
ALL and CH1–CH16. Changes commit immediately through the existing session/revision
checked API and are stored by PATCH SAVE.

- In the native phrase contract (version 2), ORIGINAL preserves each source
  event's channel for Instrument IN matching, then applies each matching
  Instrument OUT. This is the same routing as live MIDI input.
- In the historical REAPER path, ORIGINAL retains its previous behavior:
  source channels bypass Instrument OUT and the old global playback override.
- CH1–CH16 force playback channel-voice messages onto that channel.
- ALL emits each channel-voice message on all sixteen channels.

Note On/Off, CC, sustain, pitch bend, program change, polyphonic and channel
pressure use the same playback selection. System messages are not broadcast or
channel-remapped. Existing input matching and pitch/velocity Transformers remain
in the phrase processing path. Physical/live input, Instrument output controls,
MOVEMENT's explicit channel targets and PR #67's native routing are unchanged.
When multiple Instrument routes match a phrase, their existing independent
Transformer processing still applies; this control does not remove those routes.

Active safe instances latch the selection at admission, including LOOP/HOLD:
changes apply after STOP/retrigger, never remap already-sounding notes or pedals.
The existing bounded ownership record stores a 16-bit mask of **successfully
emitted** channels plus the transformed pitch, without enlarging storage or the
12-instance admission limit. STOP, PANIC and deletion release the actual owned
channels and preserve remaining physical/phrase owners. Existing selective
channel-mode cleanup stays selective rather than forwarding a destructive CC123
over unrelated live notes.

## Persistence / compatibility

The existing schema-7 payload has four unused words at +116..119 in each of the
first four Smart Switch carrier records. These sixteen **phrase-owned** words
now store 0=ORIGINAL, 1..16=fixed channel, 17=ALL. No new patch size, schema or
portable envelope is needed. Old documents contain zero/default ORIGINAL; older
prefix migrations initialize the fields through existing defaults. Native LOAD
rejects noninteger/out-of-range values before activation. Switch DONE/CANCEL,
undo and deletion already exclude these reserved phrase fields.

PATCH SAVE/LOAD, patch banks and REAPER serialization carry the existing payload
unchanged. Shared EEL executes the selection in REAPER too, but the selector is
Web-only in this focused change. Older executables preserve the words but cannot
execute the override; use matching rebuilt native/shared-JSFX sources for playback.
MIDI export contains original source channels and events, not routed output.

## Safety restrictions

The existing independent mono/ARP admission restrictions remain. ALL is also
explicitly refused on the unsafe legacy shared mono/ARP playback path (instance
error 3); it is not approximated. Legacy mono/ARP LOOP channel edits require STOP.
No new Instrument ALL or MOVEMENT routing capability is introduced.

## Executed validation

All final commands exited 0; logs and actual JACK events are in
`docs/evidence/phrase-output-channel/`.

```sh
# Reuse the documented Cloud/native prerequisites; build the matching binary.
scripts/headless-build.sh
scripts/phrase-output-test.sh
scripts/headless-test.sh
SCREENSHOT_PYTHON="$TEST_PYTHON" scripts/screenshots.sh
```

- Focused real-EEL renderer: **704 checks**, ORIGINAL and every fixed channel,
  ALL, all channel-voice message classes, sustain, overlapping ownership with
  a physically held note, policy changes, LOOP/HOLD, STOP, bank persistence,
  switch-draft isolation and explicit unsafe-ARP refusal.
- Existing real EEL/GUI/MIDI suite: **18,508 checks**. Fixtures which previously
  depended on Instrument remapping now explicitly choose the corresponding
  PHRASE channel/source route; their destination, lifecycle and isolation
  assertions were retained.
- Native suite: existing headless, catalog, installation, adapter and routing
  compatibility checks passed. No installer/router source changed.
- Real Chromium → API → engine: all 18 options, independent phrase state,
  SAVE/LOAD, browser refresh, Web worker reconnect, native restart without
  autoplay, invalid-value refusal and byte-identical source SMF export.
- Real private dummy-JACK: ORIGINAL/CH2/CH16/ALL emitted correct notes, CC,
  sustain, pitch bend, program change and polyphonic pressure. Active ALL
  survives a setting change; events stay chronological and source data identical.
  Compatible non-note source events were installed via the production patch
  transaction: the existing SMF importer is note-only and was not broadened.
- Required real screenshot workflow: **179 artifacts**, five viewport sizes,
  automated layout checks and visual inspection of every view (including
  scroll-bottom captures). New selector fits at 320×240 and desktop widths.
  Representative: `docs/screenshots/phrase-editor-800x480.png` and the real
  post-reload CH3 capture in the evidence directory.

Cloud tests are not Raspberry Pi/Zynthian/Helix hardware qualification. No merge,
installation, physical access or deployment occurred. Issue #54 WIP was retained.

For a short human test, use one active Instrument with a fixed OUT different from
the phrase source. Play a phrase recorded on two channels: ORIGINAL must retain
both, CH2 must force both to CH2, and ALL must reach all sixteen. Hold a physical
note while stopping the phrase. Change the selection mid-phrase, then STOP and
retrigger. SAVE, restart and LOAD; confirm the selection and source MIDI survive.
