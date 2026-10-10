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
* Version-2 `globalSnapshots` extension alongside unchanged schema-7 memory. Version-1 snapshots migrate with no switch overrides.
  Existing pause barrier and atomic file replacement are reused. IDs, order,
  stored values and settings survive engine restart and patch reload. Legacy
  patches load with no snapshots. Malformed configurations are rejected before
  replacing running state; unsupported extensions cannot be overwritten silently.
* Smart Switch NEXT/PREVIOUS/RECALL/MORPH/CYCLE/MORPH NEXT/MORPH PREVIOUS
  actions use stable switch and snapshot IDs. TAP/DOUBLE/HOLD use the existing
  JSFX detector and `sw_action` dispatcher, including TEST. A bounded 64-action
  bridge is drained after the MIDI block; recall is applied on the next block
  (at most one block of control latency). Navigation wraps in snapshot order;
  morph uses the destination snapshot's duration/curve. Clearing an override
  restores the existing legacy switch action. STOP/PANIC discard pending actions
  and cancel owned morphs. Direct references are removed when their snapshot
  is deleted. No second MIDI matcher or gesture detector is introduced.
* Compact Smart Switch rows expose OPTIONS. The existing modal edits one
  snapshot gesture assignment transactionally with DONE/CANCEL/×/ESC/outside.
  This popup does not yet expose complete legacy Smart Switch configuration.
* Snapshot EDIT has a collapsed INCLUDED PARAMETERS list showing stored values
  and stable target addresses. Checkbox changes commit with name/settings as one
  revision-guarded transaction. UPDATE retains exclusions by stable identity.
  Missing or legacy-expression-owned targets are skipped safely with a visible
  PARTIAL count; eligible targets still recall. A recall with no eligible targets
  is refused. Legacy expression takeover itself is not implemented.
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
this ownership adapter. They are explicitly skipped, preserving their existing
owner. There is no manual A/B macro, macro MIDI Learn, beat/bar duration,
grouped current-versus-stored parameter editor or actual REAPER Snapshot engine/UI.
Snapshot inclusion editing and partial counts exist, but detailed takeover/override
feedback and editing individual stored numeric values remain unimplemented.
The mandatory compact main Phrase/Instrument controls, phrase-owned chains,
Smart Switch popup configuration, safe browser Instrument add/delete and blank
patch ONCE defaults still require implementation. Existing application layouts
were not replaced with an alternate editing system, but do not yet satisfy that
complete row contract. Reordering the domain sections alone does not fix this.

Headless “MORPH TO NEXT” can now be configured through OPTIONS and triggered
through the existing MIDI gesture dispatcher. The complete acceptance scenario
still requires broader parameter coverage, compact rows and hardware validation.
No real Pi, Helix, Firefox or REAPER execution validation is claimed.

## Resume: exact next coding step

Continue on **this branch**, not a new audit or replacement branch. Next implement
manual A/B macro ownership: add one explicitly global, uncaptured macro target to
the existing Controller binding resolver and application callback, backed by two
stable snapshot IDs and a bounded set of common eligible parameter identities.
Route manual position and a learned existing Controller source through that same
policy target. Apply only token-owned parameters, so an individual physical
controller takeover is not overwritten on every subsequent processing tick.
Test endpoints, curves, exclusions/missing targets, mapping takeover, BACK TO STATE,
MIDI Learn conflict/cancel, browser disconnect and restart persistence before UI.

Then complete:

1. Complete descriptor target coverage and safely shared legacy-expression
   ownership, using existing controllers and typed parameter application.
2. Grouped parameter editor, current/stored values, editing stored values, and
   active/partial/overridden indicators beyond the current partial count.
3. Mandatory compact Phrase/Instrument rows, full Smart Switch popup configuration,
   native add/remove cleanup, phrase-owned chains, and default three empty Instruments.
4. REAPER engine/editor integration with unsupported extension preservation;
   migration/lifecycle regressions and physical acceptance test.

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
identity assertions), 9 Controller API tests, 11 Snapshot API tests, 162,442 policy
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

## Smart Switch manual check

Capture A and B with different Instrument VOLUME values. In each snapshot's
More → Edit, choose a two-second duration and DONE. On the Helix-assigned existing
Smart Switch, open OPTIONS, choose TAP (or DOUBLE/HOLD), MORPH TO NEXT, DONE.
Press the physical switch repeatedly: order wraps and the destination settings
control the transition. Save/restart/load and repeat. Browser disconnection must
not stop a transition. Delete a snapshot referenced by RECALL/MORPH: its override
is removed without assigning another snapshot. Choose EXISTING SWITCH ACTION to
restore the original gesture action. This does not replace the MIDI assignment,
phrase sequence, gesture thresholds or RESET ON RE-ENTRY configuration.

Latest automated checks additionally cover two switches, hardware-style TAP,
DOUBLE and HOLD events, TEST routing, inclusion commit/rejection, exclusions
surviving UPDATE, partial missing-target recall and switch-action persistence.
The earlier TEST-draft regression was fixed and the existing REAPER GUI tests
remain mandatory. No actual Helix testing is claimed.
