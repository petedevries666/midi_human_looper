# ECHOCITY destination transforms

The ECHOCITY editor offers DIRECT (the compatible default) and VIA INSTRUMENT
(TRANSPOSE / RANGE / VELOCITY). Only wet echoes use the new option. Resolve the
receiving MBMF instrument by its explicit MIDI OUT channel, never by its IN
channel. Missing, disabled, ORIGINAL or ambiguous destinations produce no wet
attack. Returning to the source instrument preserves its already transformed
note rather than applying its transformers twice.

For a different destination, reuse the native EEL `tf_pitch` and `tf_velocity`
functions at the echo's scheduled attack. This includes enabled serial transpose,
range and velocity modules and their current parameter values. The host compiles
the bridge once during startup; no compilation, variable lookup, allocation or
MIDI reinjection occurs in the audio callback. Destination ARP and polyphony are
not invoked, and its ECHOCITY cannot recursively create further echoes. Existing
downstream HUMANIZER / VELOCITY CURVES routing remains unchanged.

The shared scheduler captures the choice per admitted echo, including buffered
reverse fragments. The output ledger captures the actual transformed pitch for
release, cancellation and panic, even when the destination changes before the
Note Off. Range-filtered attacks own no physical note and emit no spurious Off.

Carrier version 5 appends `destinationTransforms` (0 or 1) to each version-4 row:
36 values per unit. Versions 1–4 remain accepted and default to DIRECT. Wire,
native persistence, real-browser editor and bounded runtime ownership tests cover
the new option. A real Surge listening check still requires the connected rig.
