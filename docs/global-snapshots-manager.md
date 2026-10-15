# Global Snapshot manager

Current status is in [the capability matrix](capabilities.md). Historical checkpoints
are [archived](archive/global-snapshots-manager-before-consolidation.md); their resume
instructions are superseded.

Native implementation supports 16 stable snapshots: effective capture, update,
rename, duplicate, reorder/delete, inclusion/partial recall, instant/timed morph,
interruption, manual A/B and shared Controller Learn. The existing Smart Switch
gesture dispatcher carries native snapshot actions. Controller tokens arbitrate
physical takeover and return. Safe changes remain deferred where held notes or
phrase playback require it. Source note data and running phase are not snapshots.

The compact browser interface uses transactional DONE/CANCEL, direct phrase and
instrument controls and confirmed deletion. It does not yet provide phrase-owned
Transformer chains or complete native legacy Smart Switch configuration. Beat/bar
morph duration and actual REAPER Snapshot execution remain absent. Unsupported
native snapshot data is preserved and refused during REAPER execution.

Persistence stays inside the owning patch/project, not browser storage. Legacy slot
SAVE and autonomous restart commitment have distinct roles; see
[project authority](project-authority.md). Tests include `tests/test_snapshots.py`,
`tests/test_snapshot_browser.py`, Controller suites and the combined runner. Real
Pi/Helix/REAPER/Firefox acceptance remains pending.
