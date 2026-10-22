# M5 architecture audit and delivery ledger

Status: implementation in progress; no deployment or live-state mutation.

Baseline: post-v2 source 040b15c. PR #99 (071ff75) is an unmerged,
independent native retrigger/200% decay change. Preserve its generated EEL,
terminal-output ownership and descriptor changes; do not replace them with
the older local files. ONCE is 1, HOLD is 2, LOOP is 0.

## Recall and storage

`headless/server.py:Handler._patch_command_locked` implements ordinary LOAD,
including empty-slot initialization. It directly imports the patch into the
engine. `headless/patch_recall.py:RecallService` separately implements manual
RECALL PATCH and MIDI Program Change via a worker, with snapshot preflight,
recovery snapshot, engine recreation, patch import, bindings and reservation.
`headless/web/app.js:patch` assumes synchronous engine telemetry; routing LOAD
to the worker must also change its queued/completed UI semantics.
`headless/web/patch-recall.js` already polls asynchronous recall phases.

Pair-save currently uses the hidden/nonstandard MBMF bank. New writes should
use 001-MBMF; retain old references and accept both journal prefixes during
crash recovery. Never bulk move snapshots. Renaming a patch must not invalidate
its existing association. A later save can create a newly named snapshot while
retaining the old file. Collisions not owned by the association must fail.

## Conductor, MASTER and gestures

`headless/conductor.py` validates persistent UUID documents; the C++ document
validator and `conductor_execution.hpp` compile them outside the audio callback.
Each switch header has eight cells; each step has an 80-cell record plus bounded
admission vectors. Source IDs resolve to fixed phrase slots. Mute group zero
does not enter the winner/exclusion map. Nonzero simultaneous groups choose the
lowest source slot. Each step admits at most twelve phrase voices.

Layer 01 is restricted to PHRASE or EMPTY. The compiler marks its admitted voice
in record 70, rather than assigning this role to the first surviving ordinary
layer. This distinction must survive mixed actions and missing sources. Further
runtime tracing is required before changing MASTER completion behavior.

The native compiler handles PRESS, HOLD, LONG_HOLD, RELEASE and
SUPERCHARGE_RELEASE, with separate phrase masks and MOVEMENT admission lists.
REVEAL/GATE combinations are validated separately from latched playback.
INSTANT dispatch deliberately permits later long gestures after an immediate
action; CLASSIFIED has different arbitration. Do not remove intentional
composition while fixing unintended double advancement. No threshold changes.

`editSwitchSequence` still edits a legacy phrase sequence alongside the dedicated
Conductor document. MIDI LEARN is under a collapsed detail after those controls.
Moving LEARN is independent; removing sequence editing requires accounting for
the legacy import path and preserving all existing configuration.

## Safe implementation boundaries

Typed actions require an explicit barrier policy before runtime changes:
snapshot/patch recall must be deferred outside realtime processing; recursive
switch dispatch must be bounded or forbidden; destructive PANIC/RESET cannot
race freshly admitted phrase voices. Do not silently accept unsupported action
documents or replace the MASTER with an arbitrary control action.

SOLO restoration requires upstream serialization/restoration evidence. No
UNSOLO ALL workaround and no assertion of a hardware fix from source reading.

## Remaining delivery

- A1 shared manual/MIDI asynchronous recall, duplicate/re-entry regressions.
- A2 native snapshot bank with legacy recovery and collision tests (in progress).
- A3 upstream SOLO diagnosis and independently validated remedy if feasible.
- C1 immediate LEARN; C2 legacy controls only after migration path established.
- B1/B3 unified one-step/multi-step model and typed action ordering.
- B4/B5 gesture arbitration and five-step HOLD/group-zero wrap regression,
  incorporating PR #99 without conflating HOLD with ONCE.
- Separate draft PRs, reproducible test evidence and hardware limitations.

## Runtime trace and migration gate

The frozen source's `conductor_press` waits on MASTER using both voice slot and
instance serial; END_OF_PHRASE uses the next cycle boundary for looping voices,
or source end for finite playback. `conductor_release_owned` preserves native
latched HOLD except explicit all/cancellation and unrevealed/gated ownership.
The original independent attack suppression can explain silent group-zero
re-entry; PR #99 removes it. A five-step HOLD wrap MIDI trace is still needed
before attributing this report solely to that fix. Do not delete HOLD retention.

The document schema already accepts configuration-only ACTION blocks, but the
native compiler marks them unsupported. Also, legacy RANDOM/REVERSE/PING-PONG
and CLASSIFIED are not supported by this Conductor compiler, which accepts only
SEQUENTIAL/INSTANT. Automatically converting every old switch now would break
existing configurations. Keep the legacy executor until those paths have real
native regression coverage; visual consolidation is not execution unification.

Proposed action execution contract for the subsequent native implementation:

1. Resolve all typed targets and reserve the entire phase before any output.
   Unresolved or unsupported actions reject the phase without partial notes.
2. Preserve MASTER voice+serial and boundary semantics. Empty MASTER stays empty;
   an ordinary action or phrase never implicitly becomes the clock master.
3. STOP/RESET act on previously existing owners, followed by admissions in layer
   order, with output timestamps preserved. Self-reset or recall mixed with new
   admissions is an explicit conflict, not an order-dependent surprise.
4. PANIC and RECALL PATCH are exclusive barrier phases; reject coexistence with
   phrase/MOVEMENT/MIDI admissions. Recall crosses a bounded host queue outside
   the realtime callback and completes through the shared RecallService.
5. No synchronous switch-to-switch invocation. Reject recursive references and
   internal recall loops; raw PC on the reserved recall channel cannot implicitly
   become a second local recall action.
6. Gesture phases retain INSTANT versus CLASSIFIED intent. LONG_HOLD is additive
   only where configured; never synthesize a second PRESS/step advancement. Gate
   release targets captured ownership, not whichever step is current afterward.

These are proposed implementation rules, not features already supported. The
current Windows host has no native compiler or usable WSL installation, and the
live Pi was not used for compilation or private engine runs. Real generated EEL
and terminal-MIDI evidence is required before replacing the dual executors.

Delivered incremental drafts: #100 recall/bank with 17 host and four dispatch
fixtures plus UI-handler tests; #101 isolated upstream SOLO candidate (original
three failures, candidate three passes); #102 panel cleanup (syntax only,
visual validation outstanding). M5-B remains unimplemented, not silently closed.
