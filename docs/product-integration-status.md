# Product integration status

The current capability matrix, dependency map, limitations and physical release
gates are maintained in [capabilities.md](capabilities.md). Earlier contradictory
checkpoints are archived in [archive](archive/product-integration-status-before-consolidation.md).

Consolidation implements versioned sample-grid native timing, descriptor-generated
EEL/C++ parameter execution, explicit autonomous restart commitment and shared
atomic slot persistence. It does not merge drafts or claim full Controller/Snapshot
studio/live execution parity. Existing musical engine, source MIDI, IDs, legacy
patch readers, bridge, note ownership and compact UI are preserved.

Current integration candidate is PR #44, `integration/studio-live-rc`.
For the requested Pitch Bias feature, the next coding step is the versioned raw
and portable migration described in [its checkpoint](velocity-decay-pitch-bias-checkpoint.md).
The response helper is tested but inactive; no Pivot/Bias controls are delivered.
Shared Controller ownership/takeover execution in both hosts remains a separate
unimplemented vertical slice, not implied by the native controls or bridge.

Before merging the stack, review #30 lifecycle and native controls, rerun the
complete regression runner after changing each base, and perform the physical
acceptance procedure. Do not bypass the documented grid/version guard or discard
native-only extensions to make PUSH/PULL appear successful.
