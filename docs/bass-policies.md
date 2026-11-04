# BASS phrase policies (native engine)

In the POLYPHONY editor, NOTE MODE = BASS exposes COMPORTEMENT BASS:

- GLOBAL (default): existing lowest-note priority across all sources. Identical-pitch phrase repeats keep the current gate.
- DERNIÈRE PHRASE: the newest admitted phrase owns bass selection. Its lowest note reattacks on a repeat, including identical pitches. Older phrases remain tracked for cleanup but never regain priority when the selected phrase ends.
- HOLD UNIQUEMENT: the same newest-phrase priority, but only actual HOLD instances feed this instrument. ONCE and LOOP still play through other instruments. Conductor MODE overrides count: the admitted instance mode is authoritative.

Direct keyboard notes retain lowest-note priority alongside the selected phrase.
These options filter note attacks only; CC/TEACH/Learn paths stay intact. Existing
BASS transformations, output channels, source recordings and Conductor layouts
are not rewritten.

Policies are optional `bassPolicies` entries in the existing patch Conductor
metadata: `{instrumentId, moduleId, mode}` with modes 0, 1, 2. IDs are stable
instrument/module identities, never positions. Missing references are preserved
but ignored; deleting/recreating a module cannot inherit its predecessor's policy.
The NOTE MODE enum stays 0..3, preserving existing controller normalization.

The editor applies changes while stopped and restores them on CANCEL unless a
concurrent edit changed the same policy. Patch SAVE/LOAD includes the policy.
Runtime selection uses the instance serial as well as its slot, preventing a
reused voice slot or an older Note Off from taking over the selected bass.
Native regression fixtures route the same phrases to BASS and a second polyphonic
instrument, covering overlap, repeats, old releases, direct MIDI and PANIC.
