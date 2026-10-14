# Refuse stale installation configuration before UPDATE activation

Audit A22 reproduces an actual configuration overwrite in `activate()`, using
only disposable files and a service fixture: prepare on port 8765, change config
to 9000 while the update is being prepared, activate the stale candidate; final
port becomes 8765 and stop/start has already run.

The shared activation function now compares current config to the preflight
snapshot **before writing the pending journal or stopping services**. The common
Web/native worker supplies that snapshot in its journal. The legacy CLI passes
its original configuration explicitly. A mismatch refuses with instructions to
check/confirm again; current config, previous rollback journal and service state
remain untouched. Normal activation and compensating rollback are unchanged.
No schema, MIDI, adapter, permissions, restart policy or new feature change.

The new regression tests assert byte-for-byte config/journal preservation and
zero service calls for both entry paths, plus normal matching activation. Together
with existing actual native/Web preflight and transaction tests: 15 updater tests,
8 backend tests and 4 native-menu tests exit 0. Evidence:
`docs/evidence/mega-audit/update-cas/`. Reproduction after fix retains port 9000,
reports refusal, and records `serviceCalls: []`.

This is not a filesystem-wide transaction lock against noncooperating root
writers after the comparison. Cooperating updater operations still use the existing
runtime-update lock; do not run installers/manual config edits during activation.
The separate musical restart race A08, UI-wide restart and physical rollback
qualification remain open. Do not claim this fixes every concurrent deployment
or makes updates safe during performance. No physical service was operated.
