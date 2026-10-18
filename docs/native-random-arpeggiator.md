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
| 9 | RANDOM CLIMB UP | Upward leaps; wrap exactly to the lowest pitch. |
| 10 | RANDOM CLIMB DOWN | Downward leaps; wrap exactly to the highest pitch. |
| 11 | RANDOM CLIMB UP / DOWN | Start low; reverse at the top without duplication. |
| 12 | RANDOM CLIMB DOWN / UP | Start high; reverse at the bottom without duplication. |

CLIMB favours small leaps spanning one to three held-note positions. The leap
range, eight-step motif and mutation probability are fixed in this version; no
extra JUMP/length/mutation controls are added. Selection uses actual held MIDI
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
