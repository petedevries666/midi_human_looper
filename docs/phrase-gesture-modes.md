# Native phrase playback: GATE, RETRIGGER, TOGGLE

Existing LOOP, ONCE and latched HOLD retain their meanings.

| Mode | Press | Release | Natural end |
|---|---|---|---|
| GATE | Start once from the beginning | Stop the owned occurrence and release its notes/pedals | Stop; keeping the pedal down never loops |
| RETRIGGER | Stop previous occurrences of this source, then restart it | No action | Stop |
| TOGGLE | Start if stopped; otherwise stop this source without readmission | No action | Stop; next press starts from the beginning |

Different phrase sources remain independent, subject to existing mute groups.
Replacement uses the production ownership ledger and preserves MIDI ordering:
previous Note Off precedes the fresh Note On. Another phrase's notes and sustain
owners are retained. STOP and PANIC retain their existing cleanup paths.

Conductor blocks can inherit or override these modes. GATE owners are associated
with the stable switch identity and the admission's press generation, rather than
the current step index. Its release therefore still finds the original occurrence
after a cursor change. PRESS, HOLD and LONG HOLD may start GATE; RELEASE and
SUPERCHARGE RELEASE cannot start a maintained occurrence and are marked unsupported.
A GATE queued until a phrase boundary is not admitted after its pedal has already
been released.

The phrase's optional native source metadata stores `playMode` as GATE, RETRIGGER
or TOGGLE. The legacy source MODE carrier is ONCE for these new modes; existing
controller curves retain their original 0..2 normalization. An explicit gesture
mode takes precedence while selected. Returning to LOOP/ONCE/HOLD removes the
native option. COPY/PASTE and SWAP carry it with the phrase.

The native engine exposes a capability flag; older engines and the frozen REAPER
editor do not offer the new modes. No REAPER source changes are made. Source mode
configuration uses stopped-state commits, while ordinary legacy mode edits retain
their existing queued parameter path.

Tests execute the generated production EEL and real MIDI output, plus Web/API
metadata persistence, actual keyboard press/release and source-specific ownership.
GATE release tests enqueue the production release edge inside the audio cycle;
calling a MIDI-emitting helper outside processing is not a valid output trace.
