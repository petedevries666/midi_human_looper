# M5 recall delivery

Saved manual LOAD on a Zynthian-hosted editor delegates to RecallService, the
same worker used by MIDI PC and RECALL PATCH. It checks session/revision before
enqueueing and reports queued state rather than rendering it as engine telemetry.
Snapshot enablement, missing-link errors, preflight and rollback therefore use
the same policy. There is no silent patch-only fallback after a host error.
Standalone editors retain direct patch-only load. Empty slots still initialize
a new patch without trying to load a nonexistent snapshot.

The worker waits for the short editor file lock to be released after dispatch;
ordinary editor writes retain their nonblocking conflict response. MIDI duplicates
after a successful recall in the same control/selected-slot context are consumed
without reloading. Explicit manual recall can still reload the current slot.
Failed operations and recreated controls permit retry. Startup does not infer a
successful recall from disk metadata alone. External changes bypassing this
service may require a status refresh; this is not a full musical-content hash.

New pairs use 001-MBMF. Old snapshot references remain valid and old files are
not moved or deleted. Both old/new journal formats recover failed pair writes.

Executed: 17 host recall fixtures and four production HTTP handler dispatch
tests; JavaScript syntax check; and a Linux subprocess regression proving that a
nonblocking editor operation is refused while RecallService owns the lock and
that the recall worker waits until the editor releases it. GitHub Actions run
39738793051 passed this cross-process test. The fixtures still use synthetic
patches and host adapters, not a live Zynthian instrument engine. Engine
recreation under asynchronous recall, real GUI reconnect/polling, five viewport
captures and physical snapshot/bindings restoration remain unqualified. No
deployment or hardware success claim.

Before integration: verify saved manual LOAD and MIDI PC restore the same rig;
empty-slot LOAD remains blank; repeated PC after success is silent; explicit
manual reload works; missing rig files fail before STOP; failed recreation
restores the previous rig/patch; rapid PC requests settle on the newest target.
