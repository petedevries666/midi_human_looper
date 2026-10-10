# Global Snapshots Manager: implementation and resume checkpoint

This is working headless code on `feat/global-snapshots-manager`, dependent on
PR #29 (`feat/snapshot-morph-ownership`). It is an incomplete draft, not the full
acceptance target. No unrelated PRs are included and nothing is merged.

## Implemented

* Fixed capacity of 16 snapshots, monotonic stable IDs, names, duplicate, reorder,
  deletion, effective-state CAPTURE and UPDATE, per-record MODIFIED indication.
* Native shared parameter-identity lookup used by capture, Controller resolution,
  and editor telemetry; compile-time tests compare it with `modules/catalog.json`.
* Capture of each existing Instrument's VOLUME, all parameters exposed by existing
  Instrument Transformer descriptors, and all 16 phrases' TIME/VEL DECAY.
  Values come from actual engine memory, including currently applied controller
  values; held notes, transport, Learn and morph runtime are excluded.
* Instant recall and interruptible sample-clock timed morphs through PR #29's
  existing Controller Engine. Physical mapped controller takeover cancels that
  parameter's morph permanently. Token cancellation prevents stale owners from
  cancelling a newer owner. Existing typed parameter application preserves
  deferred held-note changes and MIDI lifecycle behavior.
* Compact Capture/Recall/Morph/Update rows below PATCH. More menu: Edit,
  Duplicate, reorder, Delete with confirmation. Inline rename; engine-reported
  selected/modified/progress feedback. Polling leaves open menus undisturbed.
* Transactional EDIT/DONE/CANCEL in the existing modal: name, duration 0–30 seconds,
  Linear/Smooth, discrete switching at start/midpoint/end. Dismissal discards
  drafts. Captured configuration revision and engine session reject stale commits.
* Version-1 `globalSnapshots` extension alongside unchanged schema-7 memory.
  Existing pause barrier and atomic file replacement are reused. IDs, order,
  stored values and settings survive engine restart and patch reload. Legacy
  patches load with no snapshots. Malformed configurations are rejected before
  replacing running state; unsupported extensions cannot be overwritten silently.
* REAPER Lua refuses unsupported snapshot-bearing patch round trips. REAPER
  export refuses nonempty snapshots instead of dropping them. Empty extensions
  can be exported as the existing base patch.

Storage and application queues are preallocated at startup. Snapshot commands,
lookup, capture and dirty detection use bounded arrays on the processing thread;
JSON, socket, file IO and codec streams remain on the worker. Increased command
record size and callback cost still need profiling on a Raspberry Pi.

## Current limitations — do not claim complete

The native registry covers the current Controller-addressable parameter kinds,
not every desired patch control: Instrument enable/routing, Transformer bypass,
phrase base velocity/solo/mute/mode and future module parameters are not captured.
Stable phrase identities use the existing kinds 14/15 and phrase IDs; the project
has no native phrase Transformer chain implementation yet.

Legacy expression-owned targets are captured but cannot safely recall through
this ownership adapter. If any included target is missing or legacy-owned, the
entire recall is rejected before changing parameter values. Partial recall,
per-target exclusion and ownership/partial-state feedback remain unimplemented.
There is no manual A/B macro, macro MIDI Learn, Snapshot Smart Switch action,
beat/bar duration, grouped parameter editor or actual REAPER Snapshot engine/UI.
The mandatory compact main Phrase/Instrument controls, phrase-owned chains,
Smart Switch popup configuration, safe browser Instrument add/delete and blank
patch ONCE defaults still require implementation. Existing application layouts
were not replaced with an alternate editing system, but do not yet satisfy that
complete row contract. Reordering the domain sections alone does not fix this.

The requested Helix “MORPH TO NEXT” acceptance scenario **cannot yet be performed**.
No real Pi, Helix, Firefox or REAPER execution validation is claimed.

## Resume: exact next coding step

Continue on **this branch**, not a new audit or replacement branch. First extract
op 26's recall preparation/application into one audio-owned `recallSnapshot(id,
mode, duration, ease)` function. Connect the existing JSFX `sw_fire` dispatcher
(and the shared Smart Switch TEST path) to a bounded performance-action bridge;
add stable switch-ID/gesture snapshot-action configuration and persist it in a
versioned extension. Handle NEXT/PREVIOUS/ID/CYCLE/MORPH navigation there, reusing
existing TAP/DOUBLE/HOLD detection. Test two switches with hardware-style input
and TEST, interrupted morphs, save/restart/reload and deleted snapshot references.
Do not create a second gesture engine or invoke HTTP from the processing thread.

Then implement:

1. Complete descriptor target coverage and safely shared legacy-expression
   ownership; missing-target partial apply and explicit exclusion feedback.
2. Full transactional parameter/inclusion editor, independent current/stored
   values and active/partial/overridden indicators.
3. Manual A/B morph macro via Controller ownership, MIDI Learn, persistence and
   physical takeover tests; avoid reacquiring overridden targets on every tick.
4. Mandatory compact Phrase/Instrument rows, native add/remove safe cleanup,
   phrase-owned empty Transformer chains and default three empty Instruments.
5. REAPER engine/editor integration with preserved unsupported extension data;
   migration, lifecycle, all platform regressions and physical acceptance test.

## Reproduction

Use the pinned ysfx setup and development dependencies described in
`docs/zynthian-first-test.md` / `scripts/headless-build.sh`. For a freshly built executable:

```sh
YSFX_SOURCE=/path/to/ysfx YSFX_BUILD=/path/to/ysfx-build \
  HEADLESS_BINARY="$PWD/.build/midi-headless-engine" scripts/headless-build.sh
HEADLESS_BINARY="$PWD/.build/midi-headless-engine" YSFX_SOURCE=/path/to/ysfx \
  python3 scripts/combined-test.py --native --jack --browser chromium
```

`--jack` starts an isolated desktop dummy JACK test server: never run that suite
on an active Zynthian. Browser tests require Playwright and Chromium at
`/usr/bin/chromium`. Lua tests require lupa. Sanitizer checks run in the combined
suite. `tests/test_snapshots.py` exercises actual native JSFX + command queue + HTTP,
not an isolated mathematical simulation.

For a local development demo without hardware:

```sh
MOCK_MIDI=1 HEADLESS_BINARY="$PWD/.build/midi-headless-engine" \
  PATCH_DIR="$PWD/.test-snapshot-patches" scripts/headless-run.sh
```

Open `http://127.0.0.1:8765`. Adjust Instrument VOLUME using its existing EDIT modal,
Capture A; change VOLUME, Capture B. Recall A, Morph B; inspect progress. More →
Edit → set duration/curve → DONE. Change VOLUME → UPDATE; save PATCH 1, stop/restart
host, load PATCH 1. Confirm names/order/settings and recalled values. Cancel an
Edit and confirm no settings change. Disconnect the browser during a morph and
reconnect: engine timing continues. This is the current implemented subset.

For a Pi on its existing JACK server, omit `MOCK_MIDI=1`; use existing supported
host/chain instructions. Do not change OS/JACK services. LAN Firefox requires the
existing token-protected bind setup. Native Zynthian adapter PR #27 remains a
separate optional dependency, not delivered by this draft. Physical verification
must cover playing three independent chains during controller takeover, repeated
recalls, held-note deferred changes, STOP/PANIC, restart and snapshot restoration.

## Executed validation (2026-10-10, desktop x86-64)

The complete combined suite above passed with the final production code:
14 baseline HTTP tests, 4 descriptor/registry tests (including C++11 catalog
identity assertions), 9 Controller API tests, 9 Snapshot API tests, 162,442 policy
checks + 528 adapter checks both normally and under ASan/UBSan, 2,328 actual
EEL2/GUI/MIDI checks, 3 stable concurrent-render cases, 5 Lua persistence tests,
3 actual dummy-JACK routing/overflow/timestamp scenarios, and Chromium host,
generic editor, Controller and Snapshot workflows. The new browser scenario
also executes settings DONE and CANCEL and verifies that polling preserves menus.
Snapshot tests include stale commits, duration bounds, atomic malformed load
rejection, unsupported-version overwrite refusal, REAPER export refusal,
physical mapped takeover and a fresh native engine restart followed by patch load.

JACK reported inability to lock the host's memory in this container; the
functional routing/order checks passed. These checks do not establish hard real-time
performance or Firefox/REAPER/Pi/Helix hardware compatibility.
