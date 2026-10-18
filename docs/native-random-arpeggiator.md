# Native random ARP modes and Conductor reset

Legacy identities 0 RANDOM, 1 UP, 2 DOWN are unchanged. Native schema 8 adds:

| ID | Mode | Rule |
| --- | --- | --- |
| 3 | RANDOM NO REPEAT | Uniform choice excluding the last pitch when possible. |
| 4 | RANDOM BAG | Shuffle every held pitch; avoid repeats across bag boundaries. |
| 5 | RANDOM LOOP | Repeat a generated eight-step motif until the pitch set changes. |
| 6 | RANDOM WALK | Random neighbouring held pitch, reversing at the ends. |
| 7 | RANDOM MUTATE | Eight-step motif; 25% mutation probability per position/cycle. |
| 8 | RANDOM WEIGHTED | Lower held pitches have higher descending-rank weights. |
| 9 | RANDOM CLIMB UP | Start at the lowest held pitch, explore upwards with occasional backtracking, then descend. |
| 10 | RANDOM CLIMB DOWN | Start at the highest held pitch, explore downwards with occasional backtracking, then ascend. |
| 11 | RANDOM CLIMB UP / DOWN | Same exploratory traversal as CLIMB UP in this revision. |
| 12 | RANDOM CLIMB DOWN / UP | Same exploratory traversal as CLIMB DOWN in this revision. |

CLIMB now uses a biased random walk: each step chooses the preferred direction
with 70% probability and a short reverse with 30% probability. A step moves
1 or 2 held-note positions (STEP MAX default = 2); near boundaries the distance
is clamped. At the highest/lowest note, the preferred direction reverses.
There is no wrap jump, no cached sequence and every journey is newly sampled.
The preferred direction persists across temporary backtracking.

STEP MAX is currently fixed at 2 in the native selector; the requested
editable 1–4 parameter, patch persistence and editor binding still need
implementation. Do not advertise a working STEP MAX control yet.
The UP / UP-DOWN and DOWN / DOWN-UP pairs intentionally share traversal
semantics for now; they must be differentiated or consolidated in a follow-up. Selection uses actual held MIDI
pitches, including their authored octaves; no octave generator is added. One
held pitch repeats to remain playable; two pitches necessarily alternate in
NO REPEAT. Pool/mode changes reset the pattern.

Selectors are bounded with no allocation, file access or retry loops in audio.
Preinitialized per-instrument 1024-cell scratch pages are runtime-only and excluded
from patch serialization. Existing output ownership, timestamps and note-off gates
remain in the ARP path. Generated native EEL and C++ descriptors support 13 modes;
the frozen REAPER source retains three, without JSFX edits.

The real generated source, executed in ysfx/EEL, passes 25,574 checks of emitted
MIDI: gates, ownership, held-pitch selection, no-repeat rules, bag coverage, loop
period, walk adjacency, CLIMB endpoints/direction and single-note fallback. Native
HTTP integration round-trips mode 12 through saved patch slot 127.

RESET now clears the native Conductor cursor and pending advance/release state
alongside legacy traversal. STOP PHRASES is stop-only. STOP + RESET resets its
selected switch or ALL SWITCHES. The editor exposes reset targets for TAP,
DOUBLE and HOLD in addition to LONG HOLD.

On the physical patch, STOP IT targeted itself. Its target was corrected to
REFRAIN in resident state and only the corresponding target cell of saved patch
1; the original is privately backed up. A live-engine test verified STOP IT
returns REFRAIN to cursor zero and silence, and the next trigger starts STEP 1.
Patch 2 road is unchanged.
