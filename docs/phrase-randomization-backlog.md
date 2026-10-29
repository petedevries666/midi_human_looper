# Phrase randomization — design backlog

Requested by Pierre. These are design notes, not implemented capabilities.
Native Zynthian engine and Web editor only; source MIDI remains unchanged.

## START JITTER

Accepted: random playback start, with an amount expressed as a percentage of
phrase length and two choices: LIBRE and SUR NOTE.

- LIBRE chooses a position inside the permitted start window.
- SUR NOTE chooses a recorded attack inside that window.
- Amount 0 preserves normal playback.
- Proposed placement: phrase pencil editor, with a local Conductor block override.
- Proposed timing: draw at trigger; optionally draw again at each LOOP cycle.
- Measure the window from the beginning of the effective playback direction.
- Still to specify: reconstruction of notes/pedals spanning a LIBRE start,
  an attack-free window, and interaction with END, RATE and PING-PONG.

## RANDOM LAYER

Accepted for the backlog: a Conductor step can randomly select one of its layers.

Proposed UI and contract, awaiting implementation/design validation:

- STEP header selection near REPEAT: ALL (existing default), RANDOM 1,
  RANDOM WITHOUT IMMEDIATE REPEAT.
- One draw per step admission; PRESS/HOLD/LONG HOLD/RELEASE keep that selection.
- A new REPEAT admission draws again; a rejected admission consumes no draw.
- Highlight the selected layer during execution.
- Optional FIXED / CANDIDATE layer designation: keep fixed accompaniment while
  selecting one candidate.
- Check the current one-block-per-layer structure before promising a phrase
  and its associated MOVEMENT as one selectable unit.
- Define eligibility and empty/single-candidate cases before implementation.

## RANDOM PITCH with a note palette

Creative intent explicitly emphasized by Pierre: an expressive composition and
performance tool in the spirit of Radiohead's Kid A, beyond subtle humanization.
Explore unfamiliar harmonic variants and evolving melodic patterns while keeping
the performer's control through bounded ranges and a deliberately chosen palette.
Keep this feature alongside START JITTER and RANDOM LAYER as a creative priority
in the backlog. No implementation order or additional playback behavior is implied.

Requested: random pitch for a phrase in a Conductor step, lower/upper limits,
and individually checked pitch classes instead of requiring key/scale/mode names.

Proposed default: one random transposition per phrase admission, shared by all
its notes, preserving chord intervals and melodic contour. A separate per-note
randomization would be a different, optional behavior, not an implicit default.

Proposed block controls:

- RANDOM PITCH enabled/disabled (disabled preserves existing TUNE).
- LOW / HIGH transposition bounds in semitones, with units clearly labelled.
- Twelve pitch-class toggles C, C#, D, D#, E, F, F#, G, G#, A, A#, B.
- ALL / NONE shortcuts; enabling all pitch classes removes the palette filter.
- Draw only from legal candidates, after composing with effective TUNE and before
  downstream instrument transformers. Preserve the admitted output pitch for
  every Note Off, sustain release, STOP and PANIC.

Still to agree: limits as transposition offsets versus absolute MIDI pitches;
whether the palette constrains every resulting note or only a chosen reference
note; the no-valid-candidate policy; and redraw timing for LOOP versus a fresh
trigger. Never silently clamp individual chord notes or bypass the palette.

For whole-phrase transposition, checking every resulting pitch class preserves
intervals but may leave no valid candidate for some chords or chromatic phrases.
The editor should make this visible before playback.
