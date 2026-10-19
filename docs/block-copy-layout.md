# Block copies and visual layout

The native Web editor offers EDIT, COPY, DELETE and, on vacant insertion controls,
PASTE by right click, touch long press, or Shift+F10. Copy/paste transactions require
STOP, released notes, and completed echoes. Clipboard contents live in the HTTP
worker, one bounded detached block per type, and expire when that worker restarts.
No saved patch file is overwritten; SAVE PATCH keeps a completed edit.

For SNAPSHOTS, SMART SWITCHES and MOVEMENTS, right click their + / capture control
to paste a new block. Occupied cards never offer PASTE. Copies receive new identities.
A switch copy includes its Conductor with fresh STEP/LAYER/block UUIDs, retaining
references to existing phrase and Movement sources. Its physical MIDI input is
unassigned to avoid a duplicate pedal gesture. Self-directed reset actions follow
the new switch. Phrase/controller carrier settings in a reused switch slot stay intact.

PHRASES retain fixed numbered slots. On an empty row PASTE copies the MIDI content,
name, playback parameters, output policy and mute group. On an occupied row a dialog
requires OVERWRITE or SWAP, or CANCEL. Trigger assignments, Controllers and references
remain attached to their original numbered slots. SWAP requires the original patch,
engine session and unchanged source content; it exchanges content and playback
settings with the copied source, including an empty destination. COPY is repeatable.

Use the small grip on SNAPSHOT, SMART SWITCH and MOVEMENT cards to drag their visual
positions. Touch uses the same grip. Arrow keys on a focused grip and context-menu
move actions are equivalent. PHRASES cannot be dragged. The layout is a browser
preference per patch slot; it survives page reloads in that browser, does not change
musical IDs, snapshot NEXT/PREVIOUS order, Conductor steps or MIDI routing, and is
not embedded in patch exports.

## MOVEMENT channel and TEACH

A CC MOVEMENT explicitly selects CH1–16, with matching MBMF instrument names shown
in the channel list. Its MIDI output uses that channel. TEACH uses the channel and
CC currently selected in the editor, without playing the curve. It finds a single
linked Zynthian chain on that channel and refuses ambiguous, missing or stale links.
The target control must be armed in Zynthian MIDI Learn. TEACH performs scoped Learn
and applies the curve's initial CC value through the existing consuming relay;
it does not change JACK routing or send notes. DONE saves the edited Movement.
CC0/32 (bank) and CC64 (sustain) cannot be taught with this action.

## Validation

Pure edit tests cover occupied-destination rejection, copied data, slot 128, SWAP,
stale source refusal, floating-point normalization, shared switch carriers, stable
source references and renewed Conductor identities. A separate real native engine
and real HTTP worker test performs MIDI import, phrase copying/swapping, snapshot
capture/copy, switch/Movement duplication and persistence round trips on private
Unix sockets without JACK or saved user patches. Host adapter/relay fixture tests
cover channel-2 TEACH and stale/wrong/reserved destination refusal; physical Learn
still requires validation on the musician's Zynthian control screen.
