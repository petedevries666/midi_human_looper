# Phrase randomization — native contract

Native engine and Web editor only; frozen REAPER source and recorded MIDI remain unchanged.
The first creative-feature revision is installed on the Pi. The RANDOM PITCH correction below is under qualification before installation (2026-10-30).

## RANDOM PITCH — accepted user behavior

One offset is drawn for the entire phrase at each successful admission, within
LOW/HIGH (−24..+24 semitones). Apply it after effective TUNE, then quantize **each
resulting note** to the nearest checked pitch class, before instrument transformers.
Do not restrict offset choices by whole-chord compatibility. Melodic timing is
unchanged, but intervals can change after quantization.

- An already allowed note stays at its transposed pitch.
- Search above and below for the nearest permitted MIDI note.
- Equal distance follows the random offset direction: positive → upper,
  negative → lower; zero → lower.
- A small offset can therefore return to the original note. No extra jump is forced.
- Enforce MIDI 0..127 before quantization. At least one checked class always
  provides a bounded result; an empty palette explicitly refuses admission.
- Avoid the previous successfully admitted offset of the same phrase source,
  across direct play and Conductor, whenever another offset is available.
  Different offsets may quantize to the same audible melody; this is intentional.
- A sole offset remains playable. Refusals do not consume random state or history.
- Preserve original input keys and actual output reference ownership. Convergent
  pitches retain separate owners; Note Off, sustain, STOP and PANIC remain exact.
- Source pencil configuration and independent Conductor SOURCE / LOCAL override.
- PANIC/global STOP clears offset history. Runtime choices are not serialized.

ARM and x86 use the same Park-Miller sequence with Schrage reduction: no large
integer `%` that saturates on ARM. The independent loop-jitter stream uses this
same bounded primitive. The tests reproduce PHRASE 05's four-note material,
full offset range, repeated admissions, negative offsets, directional ties,
unchanged notes, MIDI edges and convergent Note Off ownership.

Creative purpose: expressive, evolving melodic/harmonic variants in the spirit
of Kid A, with a deliberately selected note palette rather than mandatory scales.

## START JITTER

0–100% of effective phrase length, LIBRE or SUR NOTE. Draw on trigger, optionally
on each LOOP cycle. Measure from the effective direction; SUR NOTE samples distinct
attacks and falls back to the original start if the window contains none.
Reconstruct crossing keys and sustain, including a released key still held by
its pedal. END stays fixed; RATE scales the shortened segment. The renderer
preserves its minimum loop duration and bounded work budget.
Trigger-only PING-PONG retains the closest valid onset for the opposite direction.
Configuration is available in the phrase pencil and as a Conductor local override.

## RANDOM LAYER

STEP header: ALL / RANDOM / RANDOM_NO_REPEAT, with FIXED / CANDIDATE per layer.
Fixed layers accompany one eligible candidate; empty/missing sources are excluded.
All-fixed steps play fixed layers. No available candidate is an explicit refusal.
One selection per successful step/REPEAT admission, retained across PRESS, HOLD,
LONG HOLD and RELEASE. Rejected admissions consume no random draw/history.
Selected layers are highlighted. STOP/reset clears selection history.
Up to 256 candidate layers fit the compiled pool; existing simultaneous voice
capacity and mute-group/routing rules remain unchanged.

All three settings copy with phrase content. Fresh recording into an empty source is allowed with RANDOM PITCH and/or START JITTER enabled: capture stores original incoming notes and keeps playback settings unchanged. Overdub of existing randomized content and mutation of an active randomized occurrence remain protected. Reverse recording restrictions are unchanged.
