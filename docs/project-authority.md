# Project and restart authority

There is one explicit automatic restart checkpoint per native processor:
`projects/active.json` referencing an immutable validated portable revision.
A successful PUSH activation or **COMMIT RESTART STATE** advances it. The latter
captures a STOP-safe point-in-time configuration without reloading the engine,
changing playback or requiring a paired studio computer. Both actions conflict
on changed revisions; commit requires engine session/revision and the previously
inspected active revision. No automatic overwrite, retiming or background sync.

**RESTART STATE** inspects the project identity, committed revision and whether the
stopped live configuration matches it. During playback/held notes/morphs inspection
is explicitly deferred, not falsely marked saved. Inspection is user-driven,
not another continuous browser polling path. Transient controller values remain
runtime state; committed parameter bases, mappings, source MIDI and snapshots are
project configuration. Use Snapshot capture for effective performance values.

Authority order:

1. An explicit Zynthian snapshot restoration takes precedence, because the user
   deliberately recalled that complete Zynthian state. It does not silently rewrite
   the portable committed checkpoint.
2. Without such a snapshot, the adapter restores the committed portable revision.
   Standalone server startup uses the existing `--restore-active-project` option.
3. With neither, start with the normal default patch, stopped. PATCH 1/2 slot files
   remain available for deliberate LOAD, but are not implicit restart authority.

REAPER RPP remains its host authority; save it after PULL marks the project dirty.
Desktop bridge baseline/spool files track synchronization, not live-engine runtime.
A local restart commit changes live revision ancestry: the next studio PUSH must
PULL/adopt that revision instead of overwriting it. SEND changes source MIDI live;
COMMIT RESTART STATE explicitly makes that change restartable without PUSH.

Legacy SAVE/LOAD behavior remains intact. Browser/native slot saves now reuse the
same atomic temporary-file/fsync/rename/directory-fsync utility as portable files.
Unknown data is validated before overwrite; malformed/newer portable revisions
are refused and retained. Disk failure retains/restores the old active pointer;
staged but uncommitted files are never automatic startup candidates. Engine state
is not changed by checkpoint failure. Ambiguous failures must be inspected before
retrying. This is not certification against every power-loss/filesystem scenario.

Acceptance: send a source phrase, STOP/PANIC, inspect and COMMIT, disconnect browser
and REAPER, restart only the test processor, verify the phrase/configuration restore
stopped, then play manually. Save a slot and verify it does not change restart
revision. Change live values and verify dirty status; stale commit/PUSH must conflict.
Load a Zynthian snapshot and verify explicit snapshot priority. Repeat with failed
activation/commit and interruptions using disposable backed-up data. Never restart
unrelated services or change global JACK configuration for this test.
