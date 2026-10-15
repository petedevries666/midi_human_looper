# Global Snapshots: ownership prerequisite

This document describes PR #29 only. The subsequent actual manager implementation
and exact remaining coding steps are in [global-snapshots-manager.md](global-snapshots-manager.md).
Its old next-branch suggestion below is historical; continue on
`feat/global-snapshots-manager`.

## Scope and integration audit

Base: main `17e0ac6` after stable host/descriptor/Controller/JACK PRs #19–#24.
Open PR #27's native Zynthian adapter is optional; draft #25 HUMANIZER and #28
ECHOCITY scheduler are unrelated and excluded. This is a global performance domain,
not an Instrument Transformer. No Zynthian OS, LUMAZ, services or JACK configuration
are changed.

The current Controller Engine registers only mapping targets, at most 256 policy
targets; the host configuration has 32 mappings. Stable addresses use Instrument,
module and parameter kind; phrase TIME/VEL DECAY use their reserved kinds. Legacy
expression-owned targets are rejected to avoid two writers. The browser's generic
editor sends four values per transaction. Patch schema 7 and the headless
`controllerEngine` configuration extension have separate compatibility boundaries:
new-policy REAPER parity is not implemented, and Lua refuses destructive round trips.

Consequently, a full patch snapshot cannot be implemented by saving the existing
32 mapping slots or by applying an HTTP/browser animation. It first requires an
all-eligible-target registry with stable identities and descriptor scaling, shared
ownership for unmapped and legacy expression targets, and a validated versioned
configuration/persistence extension across JSFX, native, Lua and browser.

## Implemented prerequisite

`controller::Engine::morph` starts an audio-owned transition in the **existing**
Controller policy domain. No second parameter writer or scheduler is introduced.
Runtime lives in the bounded target records; no allocation, IO, locks or browser
clock are used. `controller::Host::morph` exposes it to the current host adapter;
its normal `tick`/apply callback handles effective values. This is an internal API,
not yet a network command or a user-visible Snapshot feature.

```
morph(target_id, normalized_goal, duration_seconds, now_seconds,
      Ease::Linear_or_Smooth, Switch::Continuous_or_Start_or_Midpoint_or_End)
```

Duration is 0 (instant) or at most 3600 seconds. Invalid values, clocks, targets and
enums are rejected before advancing time or changing ownership. Tick derives from
the host's monotonic sample clock. Continuous normalized values stay in [0,1]; the
future descriptor adapter must scale and quantize them using existing ranges.
`morphBatch` validates all registered target identities, bounds and duplicate
keys before touching time or owners; accepted transitions share one timestamp.
Caller storage is not retained and batch count is bounded by 256 targets.
Discrete switching uses temporal start/midpoint/end, not fractional enum indices.
Smooth interpolation is `x*x*(3-2*x)`. A new morph advances to the command timestamp
and captures the current interpolated effective value, preserving continuity.

Arbitration is deterministic:

* An explicit recall replaces the current owner once and takes external priority 0.
* Physical mappings may then acquire ownership under normal DIRECT/PICKUP/GLIDE/SLEW
  rules and priorities. Uncrossed PICKUP leaves the morph running; successful
  takeover retires the morph permanently. Its tick never reacquires the target.
* BACK TO STATE belongs to the acquiring mapping; its existing policy captures the
  effective value at takeover. Returning does not resume the discarded morph.
* Manual recall cancels only that target's transition. Explicit cancellation uses
  the current token, so stale callers cannot cancel a newer recall or controller.
* Completion, PANIC, target deletion and configuration replacement retire runtime.
  PANIC freezes the effective value; it does not unexpectedly jump to a destination.
* Timed transitions are not configuration. Existing Controller JSON and schema-7
  payloads are unchanged. Committed bases remain separate from effective values.

No global snapshot IDs, names, ordering, capture collection, Smart Switch actions,
UI controls or patch snapshot data exist yet. Beat/bar duration and JSFX parity are
also pending. No public interface advertises those capabilities.

## Tests and reproduction

`scripts/controller-test.sh` and `SANITIZE=1 scripts/controller-test.sh` execute the
real policy engine and host adapter: interrupted/instant/smooth/discrete morphs,
all four takeover modes, BACK TO STATE, manual updates, deletion/recreated identity,
stale cancellation tokens, PANIC, invalid requests, independent targets and 1000
rapid recalls. Adapter tests exercise the existing application callback and verify
that transient morph state does not enter configuration JSON.

Build the native host with `scripts/headless-build.sh` and run:

```sh
HEADLESS_BINARY=/path/to/newly-built-engine \
YSFX_SOURCE=/path/to/pinned/ysfx \
python3 scripts/combined-test.py --native --jack --browser chromium
```

These are development checks, not an end-to-end Snapshot acceptance test. Do not
start a dummy JACK server on an active Zynthian. No physical Pi/Helix, Firefox or
real REAPER Snapshot validation is claimed.

## Resume implementation

Current branch: `feat/snapshot-morph-ownership`, based on main; do not merge
unrelated PRs. Next branch: `feat/global-snapshot-targets` based on this prerequisite.

1. Enumerate all eligible stable parameter identities from the shared descriptors
   and current native/JSFX Instrument, Transformer and phrase configuration. Capture
   actual audible values, not deferred committed destinations. Define capacity for
   the entire patch; the existing mapping-only registry is insufficient. Resolve
   legacy expression ownership explicitly instead of skipping it silently.
2. Connect the transition path to the existing audio-owned command and application
   queues, with safe deferred parameter updates during held notes. Integrate the validated batch API into global
   recalls with coherent multi-target start times. Handle target and
   Instrument deletion by identity, and test actual MIDI ownership/timestamp order.
3. Implement 16 bounded global snapshot records: stable IDs, names, captured target
   values, order and default duration/curve/discrete policy. Add capture/update,
   recall/interruption/cancel, rename/duplicate/delete/reorder and active/target state.
4. Append a versioned patch extension across native/JSFX/project serialization,
   Lua and headless load/save. Old patches default to empty; validate atomically;
   preserve unknown/unsupported data rather than erasing it. Do not persist morph
   runtime, held notes, transport positions or MIDI Learn state.
5. Add NEXT/PREVIOUS/ID/CYCLE/MORPH NEXT/PREVIOUS through existing Smart Switch
   action/gesture dispatch, including bounded duration/curve configuration.
6. Add the collapsible section directly below PATCH in the existing editor,
   draft-safe controls and engine-reported progress. Browser disconnect must not
   affect transitions. Document any remaining REAPER interface limitation.
7. Run real native/JACK/API/browser/persistence regressions and the user's physical
   Piano/Bass/Synthesizer, two-second Helix morph acceptance scenario. Do not claim
   the working global feature until these steps are complete. META LOOPER is out
   of scope.
