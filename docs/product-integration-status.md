# Product integration status

Application: **MIDI BAD MOTHER FUCKER**. Modules are independent MIDI pedals;
controllers and snapshots are shared performance infrastructure within one patch.

## Dependency order

Main already includes PRs #19–#24 (headless host, descriptors, controller policy,
controller integration and chronological JACK output). PR #27 adds opt-in native
Zynthian chain transport without changing REAPER's free-time engine. PR #29 adds
Controller-owned external morphing; PR #30 builds the Snapshot manager on it.
PR #27 is merged after the complete native/JACK/Chromium regression passed,
including bounded recovery and interrupted-recording diagnostics. The integration
branch joins it with #29/#30; native looper commands now use opcode 40, leaving
Snapshot opcode 20 intact. PR #29 is also merged after combined Controller and
Snapshot regression validation. PR #30 remains a draft for the integrated prototype.

PR #25 is a HUMANIZER mathematical/descriptor foundation, **not playback**.
PR #28 is a bounded scheduler foundation, **not a playable ECHOCITY module**.
Neither is needed to record and loop phrases or to use existing Transformers.
Do not enable or advertise either effect merely by merging its infrastructure.

## Existing processing restrictions

The JSFX engine preserves legacy fixed processing stages for older single-instance
patches. Stateless duplicate Transpose/Range instances opt pitch processing into
visible serial order. Velocity multipliers run before Polyphony/ARP; ARP is a
terminal note generator and CC MOD is a separate controller-emission stage.
Consequently the editor must not promise arbitrary pedal ordering around ARP,
Polyphony or delayed effects. At most one ARP and one Polyphony module per
Instrument is currently supported. Future scheduler continuations must preserve
those ownership constraints or explicitly reject unsupported placements.

There are at most eight Instruments, six Transformers per Instrument, sixteen
phrases, sixteen logical Controller sources and thirty-two Controller mappings.
Native Zynthian processors have independent memory, sockets, patch directories
and JACK ports. Synchronization uses JACK transport; phrase storage is never shared.

## Hardware qualification

Automated desktop JACK routing, real EEL2 execution, HTTP/WebSocket and Chromium
checks are software tests. The Zynthian adapter test stubs only the physical UI/base
classes and creates three actual native MIDI processors on a dummy JACK graph.
No Raspberry Pi, stock Firefox, Helix, native Zynthian UI or audible-synth acceptance
is claimed. Native loops initially support two bars of fixed 4/4; tempo changes and
transport seeks stop safely instead of silently retiming recordings.

Use [native installation and rollback](zynthian-native-chains.md), then the three
Piano/Bass/Synth hardware protocol in that document. Review experimental and draft
capabilities before choosing an integration revision; do not use all open branches
as a presumed release.

## Integration branch implementation

- Native Snapshot capture/update/rename/duplicate/reorder/delete, inclusion editing,
  instant recall, timed/interrupted morphing and manual A/B remain implemented from
  #29/#30. Smart Switch TAP/DOUBLE/HOLD use the existing dispatcher with Snapshot
  overrides. Capture reads effective values; mapped physical takeover uses the
  existing Controller ownership tokens. Browser closure does not schedule MIDI.
- The compact browser shows six Phrase rows per page. REC/OVERDUB, TRIGGER,
  exclusive TRIGGER LEARN, SOLO, MUTE, mode and velocity controls are inline;
  VEL/TIME DECAY are visible only for ONCE. Native two-bar mode explicitly locks
  mode to its supported LOOP workflow rather than pretending variable playback.
- Instrument rows show ON/OFF, label, MIDI IN/OUT, VOLUME and confirmed DELETE ×.
  Three initially existing Instruments have empty chains. ADD/DELETE supports zero
  through eight Instruments, retains monotonic IDs, and uses the existing JSFX
  bounded deletion queue so Note Offs are emitted inside the processing block.
  Deletion removes Instrument Controller mappings and Snapshot targets, retaining
  same-numbered Phrase targets. Replacement IDs never inherit those mappings.
- Phrase Trigger Learn now uses the Controller Host's exclusive command capture
  lease, consumes its attack/release, checks native and legacy assignment conflicts,
  and writes the existing schema-7 phrase trigger fields. Learning never creates a
  persistent temporary Controller source or arms recording. A deliberate reassignment
  releases the conflicting Controller mapping lease; cancellation preserves assignments.
- Only Transpose/Range neighbours in an explicitly serial pitch chain can reorder.
  Unsupported stage moves are rejected by the engine and hidden by the editor.
  Bypassing the extra instance keeps serial order, rather than reverting other
  modules to legacy fixed stages. Older single-instance patches retain their order.
- Unknown patch fields/extensions are rejected on LOAD and overwrite, preserving
  their original files. Native adapter SAVE uses an fsynced unique temporary file
  and atomic replacement. No unsupported module configuration is silently stripped.

## Remaining limitations / precise next steps

This is a core integration prototype, not completion of every requested module.
Do not mark HUMANIZER or ECHOCITY playable: their open foundations are unmerged.
Independent Phrase Transformer chains remain unimplemented. The generic editor
currently configures Instrument Transformers; ADD creates an instance immediately,
whereas parameter EDIT has transactional DONE/CANCEL. Full transactional ADD and
complete native Smart Switch configuration/Learn remain follow-up work; the current
native switch popup edits Snapshot gesture overrides while retaining imported legacy
switch assignments. REAPER does not execute the native Controller/Snapshot extension;
its Lua guard refuses unsupported headless data instead of erasing it.

Next coding step: add typed, stable Phrase chain ownership to the shared schema and
bounded scheduler before exposing Phrase ADD TRANSFORMER. Implement real forward
HUMANIZER/ECHOCITY continuations on that same scheduler, with feature capability
flags and actual engine/JACK ownership tests, then extend the generic editor. Do not
reuse post-output filtering as a substitute for source-event ownership.

The native chain wrapper still needs a hardware audit of imported Smart Switch
record/play/stop semantics under fixed-grid transport. Zynthian's native PLAY/RECORD/
STOP/FINISH controls are the reproducible first-test path. Full stock Firefox,
Helix, Zynthian UI registration/autoconnect, audible synths, Pi CPU/RAM and latency
remain hardware validation pending. No release candidate hardware certification.

Cloud timing limitation: the three-process dummy JACK capture sometimes overruns
at 2,048 frames under shared-container CPU scheduling. Functional validation uses
`CHAIN_JACK_BLOCK=8192`; the engine reports and safely cancels missed recordings.
A passing high-buffer workflow must not be presented as a playable Pi latency result.
Physical JACK buffer/CPU qualification is a release blocker, not a hidden test waiver.

## Executed validation of this integration

The complete combined runner passed on the final implementation:

```sh
CHAIN_JACK_BLOCK=8192 PATH=/workspace/setup-tools/venv/bin:$PATH \
YSFX_SOURCE=/workspace/setup-tools/ysfx YSFX_BUILD=/workspace/setup-tools/ysfx/build \
JACK_INCLUDE=/workspace/scratch/midi-deps/root/usr/include \
JACKD=/workspace/scratch/midi-deps/root/usr/bin/jackd \
JACK_DRIVER_DIR=/workspace/scratch/midi-deps/root/usr/lib/x86_64-linux-gnu/jack \
HEADLESS_BINARY=/workspace/scratch/midi-headless-engine \
python3 scripts/combined-test.py --native --jack --browser chromium
```

This includes 162,709 synthetic-time Controller checks and 543 host adapter checks
in both normal and ASAN/UBSAN builds; 2,355 actual EEL2/GUI/MIDI checks with stable
concurrent GUI hashes; baseline HTTP, registry, installer, Controller and Snapshot
API suites; the complete product workflow; five Lua tests; five Chromium workflows;
and actual dummy JACK three-processor recording/overdub/persistence, timestamp
ordering and overflow recovery. The JACK probe checks chronological events and an
empty final note ledger, including channel-mode cleanup. No physical certification
or stock Firefox qualification is inferred from these results.

## Resumed repository audit / issue #33

At resumption, actual main is `ab37a75`: #27 and #29 merged; #30 remains draft at
`50b5db4`. Open implementation PRs #25 (`69ff1c2`) and #28 (`d7e6b7e`) remain
mathematical/scheduler prerequisites without playable effects. #11/#12 remain
research/design PRs. #19–#24 are merged. No changed upstream implementation was
found to reuse for issue #33; its focused branch builds on #30, without merging
unfinished work. Issue #32 requires non-monotonic Controller-owned automation,
not another note effect or a browser timer; it remains unimplemented.

Phrase SMF interchange is now implemented on `feat/phrase-midi-interchange`,
including transactional browser preview/replace and download, real native worker
integration and source-data schema-7 persistence. See
[format, timing, bounds and manual tests](phrase-midi-interchange.md). A real REAPER
export has not been tested here; the test fixture is REAPER-style Format 1 and
export is independently parsed with mido. Physical qualification remains pending.
This is progress toward a release candidate, not a declaration of final completion.

## Next precise implementation checkpoint

Resume `feat/phrase-midi-interchange` to review/qualify MIDI interchange; it is
stacked on #30 and must not bypass that dependency. Rebuild server and native binary
together. Do not merge either draft as a fully finished release candidate.

For the next effect implementation, reuse `feat/echocity-scheduled-events` (#28)
and its explicit POLY continuation contract. Integrate it with the tested #30/#33
base, then add stable per-instance echo settings, source-token Note On/Off capture,
real scheduler admission/emission and cancellation hooks before exposing any echo
controls. Run actual live-input and imported-phrase playback tests through JACK.
Reuse #25's seeded HUMANIZER algorithms with the same scheduling/ownership path;
do not introduce a parallel native-only post-output effect. Motion #32 must then
use #29's external ownership tokens for non-monotonic point curves and physical
CC takeover, with headless timing and explicit Smart Switch action routing.

Unimplemented: playable HUMANIZER and ECHOCITY, independent Phrase Transformer
chains, complete native Smart Switch configuration, full transactional ADD,
unrestricted module ordering, native Motion v1 and REAPER Snapshot/Motion execution.
Physical Zynthian/Helix/Firefox/REAPER and playable Pi latency remain blockers to
hardware release qualification. No OS, LUMAZ or hardware service changes were made.

Issue #33 delivery: PR #34 is a draft stacked on #30. The full combined native,
JACK, EEL2, sanitized Controller, Lua, HTTP and six-browser-workflow suite passed.
Final counted-ledger three-processor JACK validation also passed with file-based
server diagnostics. Two earlier follow-ups lost control replies with live engine
processes; their root cause remains unconfirmed, so reliability qualification is
still pending. No PR was merged during this implementation stage.

## Studio/live implementation stack

PR #37 implements design #35 on top of #34/#30: immutable portable schema-7
carrier, seconds/sample-grid conversion, explicit unsupported-capability refusal,
and shared-EEL2 MIDI parity tests. The `feat/reaper-live-sync-bridge` stack
implements design #36: asynchronous ReaScript SEND/GET, toolbar PUSH/PULL,
immutable staging, guarded STOP-only compare-and-apply, revision/session/hash
checks, atomic committed pointer and autonomous restoration. No draft is merged.

Native Controller/Snapshot data is preserved; REAPER execution of populated
native extensions is refused. Native activation across incompatible two-bar
transport grids, multi-JSFX whole-project routing and phrase/bar-boundary
activation remain unsupported. Individual phrase transfer is notes-only. See
[studio/live setup and physical procedure](studio-live-bridge.md). Software
regression is distinct from pending physical REAPER/Zynthian/Helix validation.
