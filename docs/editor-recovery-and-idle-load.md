# Editor interactions, recovery and idle load

The illustrated cards expose EDIT / DELETE through a context menu (right click,
keyboard menu key / Shift+F10, or a 600 ms stationary touch). Live play controls
retain their press/release ownership. Transformer cards open their editor on
activation and show selection by instrument plus module identity. BYPASS remains
direct. The editor docks in its own reorderable section below Instruments.
Movement preview curves have transparent backgrounds. Modulation previews fit
the actual range rail; geometry reads are batched and identical updates do not
write styles again. Hidden browser pages pause their stream and fallback polling.

Deleting a Smart Switch preserves phrase/movement sources and legacy embedded
phrase metadata; it removes its Conductor and stale reset/snapshot actions.
Linked presets cannot resurrect a deleted switch. Empty patch slots open a blank
patch; COPY / PASTE use a private server clipboard and SAVE remains explicit.
Patch names are host metadata in patch-names.json, with bounded printable names,
atomic writes and an expected-name check. Renaming neither loads nor saves music.

RELIER PAR CANAL OUT explicitly recovers absent host links with one matching fixed
MIDI channel. Existing living links remain intact. Missing destinations are
reported, and ambiguous channels require a choice. ORIGINAL / ALL do not guess.
Link changes require the engine to be at rest and retain inventory, revision and
session guards. They do not change JACK connections or MIDI IN settings.

Native capacity expansion previously turned the due-boundary scheduler into
64 x 64 scans on every block, even with no pending boundary. The native generated
source now exits after the first scan finding no due boundary. Executed boundaries
still trigger bounded rescanning in sample order; the maximum remains 64 scans.
The shared frozen REAPER JSFX is unchanged. An unlinked host bridge also avoids
querying mixer telemetry at 25 Hz when it has no instrument bindings.

## Validation on 2026-10-18

- Actual private native schema-8 test: switches 1 and 64 both queue step 2, then
  execute at their master phrase boundaries. No JACK or user patch used.
- Instrument-link fixture suite: 25 tests, 22 passed and 3 environment-dependent
  skips on Windows. New coverage includes idle no-query, channel relinking,
  ambiguity, ORIGINAL and refusal while notes are active.
- Patch-name persistence/conflict/bad-input regression passed. JavaScript syntax
  checks and Python compilation passed. Actual live Web rename was verified with
  Enter and reload; the user's subsequent name change was preserved.
- Earlier private native checks covered stopped switch deletion/source retention,
  refusal during playback, and COPY / empty LOAD / PASTE / saved LOAD.
- Actual live editor: selection uses instrument/module IDs; editor remains open
  when moved up and down, and Cancel closes it without editing the parameter.
- User explicitly replaced the five-size script requirement with validation on
  their live interface. scripts/screenshots.sh was not run for this follow-up.
  The committed live PNG is an actual desktop capture; no touch-device or full
  five-size qualification is claimed.

On the same idle resident patch, two short 10-second windows measured native
process CPU at 26.5% then 11.9% of one core, with zero XRUN increments in those
windows. These are observations, not a sustained audio guarantee: a later
post-restart observation included one additional XRUN. The user subsequently
confirmed that Firefox was fluid and the sound clean. Long-duration audio
qualification remains separate.

The live recovery retained the previous processor's saved patch, its later
resident capture and the displaced current resident in separate local slots.
No user musical patches, access keys or tokens are included in this source PR.
