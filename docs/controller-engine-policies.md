# Global Controller Engine: policy core, issue #18 PR C1

**Status:** executable, bounded C++ policy implementation with deterministic tests.
Not yet enabled in the headless host or REAPER, and not the completed PR C feature.
This keeps tomorrow's independently usable P0 intact while policy semantics are
reviewed before MIDI Learn/legacy migration/persistence integration. No existing
expression assignment or sound is changed by adding this library.

## Domain and timeline

`headless/controller_engine.hpp` owns normalized effective targets and ownership.
It is global controller policy, never an Instrument note Transformer. The future
host adapter must implement the complete timeline:

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

## Required integration before exposing controls

1. Add typed physical-source records and one global Learn target/lease, preserving
   exact channel/type/number, explicit duplicate reassignment and release quarantine.
   Reuse the existing switch/phrase Learn isolation; do not create another listener
   independently inspecting the same event.
2. Resolve target keys `(scope, stable Instrument/phrase/module ID, parameter ID)`
   against descriptors, retaining base values separately from effective values.
   Apply through existing held-note deferral/reset hooks, not raw note-routing edits.
3. Migrate legacy expression assignments and multipoint curves atomically, with
   DIRECT defaults matching existing `exp_curve_value`/`param_scale` behavior. Prevent
   legacy and generic writers from owning the same target. Cross-check real EEL
   fixtures and preserve REAPER-export semantics rather than clearing assignments.
4. Version configuration persistence, validate entire imports before commit, reset
   runtime on LOAD/PANIC, and reject stale commands after target deletion/patch recall.
   Do not silently add a lossy sidecar that REAPER's Lua SAVE would discard.
5. Add descriptor-rendered mapping editor, source Learn and live takeover/return
   indications, then real-engine/HTTP/browser integration tests. These controls are
   intentionally not advertised as available by this policy-only PR.

HUMANIZER and VELOCITY CURVES remain subsequent separate implementation stages;
#11/#12 designs were inspected. Their scheduler/curve/ownership work is not replaced
by the controller library or metadata.

## Run the tests

```sh
scripts/controller-test.sh
SANITIZE=1 scripts/controller-test.sh
```

Tests cover synthetic time, rapid retarget, pickup after recall, independent eligible
targets, priority contention, stale return/token rejection, target deletion/PANIC,
curve bends and capacity/invalid configuration. They prove the policy core only,
not MIDI Learn, native parameter adapter, persistence migration or Pi performance.
