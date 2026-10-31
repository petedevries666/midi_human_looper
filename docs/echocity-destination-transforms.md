# ECHOCITY destination transforms

## Full instrument chain

Carrier value 2 adds VIA INSTRUMENT (complete native chain, MONO/BASS/LEGATO and
ARP included). Value 1 remains the pitch/velocity-only path described below;
DIRECT remains value 0 and the compatible default. Full re-entry also applies
the source chain again if the echo returns to that same instrument.

The full path uses a fixed 512-event/256-lease handoff into the next DSP block:
one block of additional wet latency, no change to DRY. Every attack reserves room
for its release. No extra VM or JACK ports are created. The native EEL merger
orders the internal ingress with physical MIDI by sample offset, bypassing Learn,
recording and Smart Switch dispatch. The original ARP advances only once per
block. ARP outputs in later blocks and mono fallback notes retain Echo provenance,
which bypasses destination ECHOCITY and its DRY attenuation. This prevents recursive
echo chains while retaining the normal final HUMANIZER / VELOCITY CURVES stage.

Input leases pin instrument identity and transformed pitch. A release does not
recompute TRANSPOSE or address a replacement instrument. Panic drops queued
attacks and clears destination leases alongside existing native ownership.
All host/EEL buffers are prepared at startup, without callback allocation or JIT
compilation. Real EEL tests exercise pitch capture, mono/legato, all thirteen ARP
selectors, recursion exclusion and panic. Hardware listening is qualified separately.

## Pitch / velocity path

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
36 values per unit; the full path extends this field to value 2. Versions 1–4 remain accepted and default to DIRECT. Wire,
native persistence, real-browser editor and bounded runtime ownership tests cover
the new option. A real Surge listening check still requires the connected rig.
