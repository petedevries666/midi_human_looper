# M1: source PHRASE MUTE GROUP

Draft stacked on M0 #79 (`2037269`), itself on #78 / #76. No merge/deployment.

PHRASE OPTIONS now has a compact MUTE GROUP integer and SET GROUP. Zero means
independent; positive IDs use the existing action-target ID domain 1–16777215,
not a new limit on the number of musical groups. Configuration is stopped-only,
validated and atomically installed through the existing native revision/session
transaction. A concurrent change rejects the save; it never overwrites a newer
patch. Main phrase rows are unchanged.

After reserving a new ONCE/HOLD admission, the engine stops *other sources* in
that group using existing destination-owned release functions. Same-source
independent occurrences keep their admission policy; different groups, live
keyboard notes, physical sustain and MOVEMENTS remain independent. LOOP uses
its existing source dispatcher. Explicit STOP/PANIC and twelve-voice capacity
are unchanged. No new scheduler, callback allocation, lock, parsing or I/O.

Within a STEP, the smallest existing PHRASE ID (the stable 1–16 source binding,
not layer order or array traversal order) wins among conflicting different
sources. The compiler resolves this on the worker. Reversed layer order is
covered by actual native tests. Conflicting blocks remain stored and editable;
API and editor show a warning, recalculated from current source properties.
There is no block MUTE GROUP override.

## Persistence and rollback

The schema-7 MIDI payload and portable project format are unchanged. The existing
CONDUCTOR extension's **internal document version 3** adds required `muteGroup`
to each source. Its external carrier remains version 1. Versions 1/2 remain
accepted unchanged; adopting groups explicitly copies/upgrades the document,
adds group zero to all sources and retains UUIDs, switches, curves, order and
MOVEMENTS. Saving a MOVEMENT preserves version 3 rather than downgrading it.
Native and Python validators agree and reject malformed/unknown data.

The sixteen existing PHRASE bindings are prepared into sixteen runtime cells in
the existing reserved area below CONDUCTOR storage. Cells are outside the frozen
JSFX patch payload. Native config installation resets them when the extension is
absent. Loading never triggers playback. Groups survive two patch banks, portable
capture/materialization at 48/96k and loading into a fresh native process.

**Older runtimes reject version-3 configuration.** Keep pre-M1 patch/snapshot and
runtime backups before any explicitly reviewed device test. Roll back runtime
and the matching pre-M1 project together; never strip group data or silently
convert it to an older document. No automatic installation is provided here.

## Actual executed evidence

- `scripts/m0-playback-test.sh --m1-groups`: 64 real DSP MIDI checks, exit 0;
  targeted group release, physical shared pitch/sustain, unrelated group, LOOP ↔
  ONCE, smallest-ID winner, unsafe route refusal, capacity refusal.
- M0 focused 114/17/51 checks and extended 100 shared-entry checks and ownership 6698 pass; full shared regression
  **18,508 EEL checks**, exit 0. Frozen/default legacy behavior is exercised.
- Actual private JACK / source / native / sink: `On60, Off60, On62`, then independent
  HOLD/retrigger and LOOP, PANIC, output overflow zero, observed chronology checked
  without sorting. 48k/8192 Cloud dummy backend, **not Pi timing qualification**.
- Four native API tests under ASAN/UBSAN: source editing, invalid-load rollback,
  source isolation, MOVEMENT execution, bank/portable round-trip and fresh engine;
  exit 0, zero diagnostic files with leak detection and abort-on-error enabled.
- Existing persistence: 23 CONDUCTOR, 5 MOVEMENT, 20 extension-preservation tests;
  native CONDUCTOR 3 tests, all pass.
- Exact committed engine `f743b9146c3820caba9e2da1716b0a9a106b5d0f` rebuilt successfully; four native group/bank/portable/fresh-engine tests rerun with exit 0. Supplemental tests then verified learned-MIDI and legacy-switch ONCE overlap and HOLD cut/retrigger, bringing shared-entry coverage to 100 checks. No production changes after that engine commit.
- Actual Chromium: phrase options -> native playback -> save/load; warning refresh;
  stopped-load state. A deterministic delayed-script test also covers the startup
  bug found visually: telemetry previously called `paintConductorRuntime` before
  the deferred editor loaded. Initial API/WS startup now waits for DOMContentLoaded.
- Full screenshots workflow exit 0, 185 manifest views at five sizes inspected in
  viewport contact sheets; three additional real group-warning screenshots at
  320×240, 800×480 and 1440×900. No synthetic UI data or hardware claim.

Logs and source hashes: `docs/evidence/m1/`. Existing combined runner retains all
prior gates and now includes M0/M1 native/browser/JACK tests. It was **not rerun in
full here**; prior #76/#77 Cloud timing/receiver failures remain open and are not
masked. Initial test-helper errors (missing fixture switch and incompatible bank
helper signature) were corrected in tests, not by changing musical assertions.

## Deliberate limits

- Grouped mono/ARP admissions remain explicitly refused before an attack. Their
  independent ownership is not qualified; do not pretend grouped routing is safe.
- Capacity preflight is conservative: twelve occupied ONCE slots can refuse a new
  grouped source even if stopping a victim would later free a slot. Refusal leaves
  every old owner intact. No hidden voice stealing or larger capacity.
- END_OF_PHRASE/QUEUED is still unsupported, so MUTE GROUP cancellation of QUEUED
  is not yet executable (later transition milestone). No fake queued behavior.
- Action-block STOP GROUP belongs to the later action milestone; this M1 slice
  implements musical source admission and targeted cleanup, not unsupported actions.
- Real V4/Helix, CC7 REVEAL and concert timing remain unqualified. No changes to
  Zynthian services, updater, LUMAZ or original issue-54 working files.

## Five-minute musician recipe after review

Back up and record installed SHA; preserve a matching pre-M1 patch for rollback.
With the processor stopped, set two bass PHRASES to group 7 and a piano/pad to 0.
Save. Play bass A, then piano, then bass B: only bass A stops. Hold a keyboard note
and sustain while repeating: neither is cut. Change A to LOOP, repeat. Put both
bass sources in one STEP in reverse order: warning appears and smaller PHRASE ID
wins. Set B to group 0, reopen CONDUCTOR: warning disappears and both play. Save,
reload stopped, repeat, then PANIC. Hardware installation requires separate approval.
