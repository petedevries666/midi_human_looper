# Product integration status

The current capability matrix, dependency map, limitations and physical release
gates are maintained in [capabilities.md](capabilities.md). Earlier contradictory
checkpoints are archived in [archive](archive/product-integration-status-before-consolidation.md).

Consolidation implements versioned sample-grid native timing, descriptor-generated
EEL/C++ parameter execution, explicit autonomous restart commitment and shared
atomic slot persistence. It does not merge drafts or claim full Controller/Snapshot
studio/live execution parity. Existing musical engine, source MIDI, IDs, legacy
patch readers, bridge, note ownership and compact UI are preserved.

Next precise coding step: implement and test one shared ownership/takeover vertical
slice on an existing stable target, using the current Controller token contract and
ReaScript/JSFX mailbox. Do not introduce another owner or scheduler. Demonstrate
physical takeover during one snapshot transition in both actual hosts before
expanding target coverage or accepting full studio/live parity.

Before merging the stack, review #30 lifecycle and native controls, rerun the
complete regression runner after changing each base, and perform the physical
acceptance procedure. Do not bypass the documented grid/version guard or discard
native-only extensions to make PUSH/PULL appear successful.
