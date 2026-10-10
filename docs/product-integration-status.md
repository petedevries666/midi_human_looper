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
Snapshot opcode 20 intact. The combination remains reviewable before merging.

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
