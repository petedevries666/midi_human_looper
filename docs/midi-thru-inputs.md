# MIDI THRU by physical input

The native editor adds **MIDI THRU / ENTRÉES** under **CONFIG / MIDI OUTPUT**.
DIN and USB inputs are listed separately, each with policies for channels 1–16:

* **OFF** blocks live musical routing and recording from that input/channel.
* **NON ASSIGNÉ** lets unassigned events reach the existing instrument routing.
  Assigned phrase, Smart Switch and controller commands remain consumed.
* **TOUT** also lets assigned commands play through the musical path.
  Exclusive Learn capture and quarantined releases always remain silent.

Commands and all Learn paths receive input before the musical gate. Zynthian
TEACH and the scoped learned-CC output relay are separate from this ingress
filter. Internally generated phrases and Movements do not pass through it.
Instrument IN/OUT channels and transformers still determine the musical targets.

## Global defaults and patches

**GLOBAL** stores per-device defaults in `midi-inputs.json`, alongside
`install.json`. **PATCH ACTUEL** overrides individual channels; **HÉRITÉ** uses
the global setting. Save the patch normally to retain its overrides.

The first activation requires stopped playback and released notes. Existing
explicit input selections are proposed without writing configuration during a
read. A newly detected USB input requires **GÉRER CETTE ENTRÉE**. Reading an
inventory never enables a device or changes JACK routing.

The registry keeps stable source identities independently of JACK input slots.
Reconnecting a2j devices tolerates changing numeric ALSA client indices. Two
simultaneous devices with the same normalized name are ambiguous and remain
blocked rather than being silently exchanged. Up to 15 physical inputs can be
managed; inactive historical device identities are retained.

## Routing and note lifetime

Each enabled physical source uses a dedicated native JACK input. Oram closes
its direct instrument bypass and former merged MB input first. The engine
admits live music only after the expected dedicated connection is verified;
there is no fallback that pretends a merged input preserves source identity.

Closing a source/channel releases its tracked live notes and sustain without
releasing another source's held notes. JACK disconnection schedules source
cleanup on the DSP thread. Policy memory, note ownership and voice cursors are
not serialized in patches. An empty patch resets overrides but retains the
global physical input registry.

Older native sources continue using their previous routing when this feature
is unavailable. The frozen REAPER JSFX is unchanged. This feature is developed
in PR #110; hardware installation and DIN/USB qualification must be recorded
separately from isolated native and router fixture tests.
