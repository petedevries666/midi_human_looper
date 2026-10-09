# Global Controller Engine: policy core, issue #18 PR C1

**Status:** the policy core was delivered separately in #21. This dependent branch
connects it to the real headless MIDI host and browser. REAPER policy processing and
automatic legacy-assignment migration remain incomplete. See
[controller-engine-integration.md](controller-engine-integration.md) for current
controls, persistence boundaries and tested limitations.

## Domain and timeline

`headless/controller_engine.hpp` owns normalized effective targets and ownership.
It is global controller policy, never an Instrument note Transformer. The headless
host adapter implements this timeline:

physical channel/type/number → exclusive Learn/switch/phrase routing → logical
source → per-mapping multipoint response → takeover → priority/ownership → normalized
effective target → descriptor scaling/quantization → existing `param_apply` or
per-instance pending storage → DSP.

Curve shaping precedes takeover; parameter-unit scaling follows arbitration.
Multipoint curve bends use the exact existing EEL exponent (`1 + 5*abs(bend)`),
with independent mapping curves. A nonlinear target scale does not change the
normalized interpolation contract. Enum/toggle targets quantize only at the adapter.

The core accepts explicit synthetic time, performs no allocation, locks, file/network
I/O, sleeping or MIDI output. Targets are bounded at 256, mappings at 64, curves at
16 points. Stable IDs address records independently of position. Configuration is
validated before replacement; runtime is excluded from the configuration-v1 contract.

## GLIDE TAKEOVER

- **DIRECT** is the compatibility mode: immediately demand the curve output.
- **PICKUP** waits until curve output is within the configured normalized threshold
  or crosses current effective value. Patch recall/config replacement resets the
  previous demand so an old position cannot fake a crossing. Pending status is exposed.
- **GLIDE** starts at the current effective value, ramps over `glideSeconds`, and
  continuously retargets from the interpolated current value on new movement.
- **SLEW** bounds movement by `slewPerSecond` normalized units/second, including rapid
  direction reversal. GLIDE/return support linear or smoothstep easing.

Higher priority wins. With equal priority, the newest source event takes ownership;
multiple mappings competing within that event use the lower stable mapping ID.
Ownership persists until return completion, explicit cancellation/deletion, PANIC,
patch recall or an external higher-priority owner. Continuous motion cancels return
and retargets from the current value; it does not repeatedly snapshot intermediate
positions as the desired return state.

## BACK TO STATE

Capture effective target when a mapping first acquires ownership. `capture(targetId)`
provides an explicit later snapshot boundary. Only eligible mappings return:

- **IDLE:** wait `idleSeconds` from the latest source event, then ramp. Repeated events
  reset inactivity even when the numerical source value is unchanged.
- **RELEASE:** an explicit source release starts the ramp without jumping to zero.
- **COMMAND:** an explicit target return command starts the ramp.
- **OFF:** retain effective value without automatic return.

A return reaches the captured value over `returnSeconds`, then relinquishes ownership.
A time update skipping both wait and ramp produces the same endpoint. Each target has
an ownership generation token. Higher-priority controller or external automation
invalidates old ramps/returns; stale external releases are rejected. A new acquisition
captures the new effective value. External automation must explicitly release its
valid token before lower-priority controllers can reacquire.

One pedal may map to I1 cutoff, I1 ARP speed and I2 volume: configure return eligibility
only for the first two. The synthetic test exercises precisely the independent-target
return behavior. Target deletion removes its mappings; PANIC cancels all runtime
ownership/ramps without changing current parameter configuration. Recall supplies
new committed values and resets pickup/return state.

## Remaining compatibility work

The native adapter now implements sources, exclusive Learn, target resolution,
held-note deferral, committed bases, versioned in-file configuration, generic editing
and live takeover/return indications. Existing expression-owned targets are rejected
to prevent competing writers. Automatic legacy migration still requires real EEL
curve/scale fixtures and atomic conversion with DIRECT compatibility defaults.

New-policy configuration is headless-only until a shared JSFX/project schema and
REAPER policy adapter are implemented. The separate REAPER base export and Lua guard
prevent silent destructive round-trips; they are not a claim of full bidirectional
policy compatibility. Physical Pi/Firefox acceptance remains outstanding.

HUMANIZER and VELOCITY CURVES are subsequent implementation stages. Their scheduler,
response-curve, AMOUNT and ownership work is not replaced by controller metadata.

## Run the tests

```sh
scripts/controller-test.sh
SANITIZE=1 scripts/controller-test.sh
```

Tests cover synthetic time, rapid retarget, pickup after recall, independent eligible
targets, priority contention, stale return/token rejection, target deletion/PANIC,
curve bends and capacity/invalid configuration. These synthetic cases prove policy semantics. Native MIDI/HTTP/browser tests are
listed in the integration guide; Pi performance is not inferred from either suite.
