# Free-time recording recovery

Stacked on PR #49 at `2068877`; no merge or physical deployment.

Default native `--chain` now uses shared JSFX first-note recording. REC arms an
empty phrase indefinitely. A positive Note On starts the take, including its
same-block chord. A single origin preserves all following event intervals;
FINISH uses elapsed samples, not a two-bar window. Leading non-note events remain
live but are not stored before the first attack, matching `STATE_READY`. They
are not moved independently to invent a pre-roll. Existing playback mode is not
changed. New native takes close unmatched attacks at the last sample before
FINISH, using the existing bounded pairing check. STOP/PANIC use existing owned
note cleanup. Saved schema-7 takes are not rewritten.

The former synchronized two-bar adapter remains available with
`--chain-grid-capture`. For an installation deliberately using that contract,
`chain_grid_capture: true` in its existing install configuration enables it.
Missing configuration defaults to free-time recording; `chain_timing_version`
still selects grid V1/V2 **only when that grid is explicitly enabled**. Runtime
state reports `chainCaptureMode`. Import and portable activation apply fixed-grid
restrictions only to the explicit grid, retaining fallback for older runtimes
that do not publish this field. No installer or updater is changed.

This does not create a new scheduler or rewrite the shared phrase engine.
Original LOOP/ONCE/HOLD source semantics and native held-release restrictions
remain. Full free-time overdub, event-capacity exhaustion, varied-length LOOP
layers and real transport-loss qualification are still required; see the audit.
The browser still contains old grid-specific diagnostic text pending its separate
UI repair. Do not treat this draft as a hardware-qualified release candidate.

## Reproduce and validate

```sh
YSFX_SOURCE=/path/to/pinned/ysfx TEST_PYTHON=python3 tests/run_host_tests.sh
HEADLESS_BINARY=/path/to/candidate python3 tests/test_native_free_capture.py
python3 scripts/combined-test.py --native --jack --browser chromium --timeout 240
```

The EEL regression failed before the common-origin correction: a chord beginning
at offset 17 stored its second attack at 17 instead of zero. The tests now execute
both shared and default native paths, not a mathematical recording simulation.
36 actual source fixtures go through the production SMF writer; delta ticks,
channels, velocities and Note Off timing are checked. The native API test waits
4.3 seconds while armed, then records/exports/saves/reloads in each playback mode.
Grid tests opt into the old grid explicitly rather than weakening its assertions.

After review, use the existing documented reversible updater with the reviewed
full SHA, not a new installer. Back up musical projects and save a Zynthian
snapshot first. Stop/disarm before updating; the updater restarts the existing
Zynthian UI and its MBMF child processes, interrupting performance, without
restarting JACK. See `zynthian-runtime-update.md` for backup and rollback.

Physical test: choose an empty phrase in each mode; arm at arbitrary transport
positions; wait >4 seconds; play a chord, staggered releases, rests and further
notes; FINISH; export and inspect the first actual attack at tick zero in REAPER.
Repeat with no external clock and a tempo change, then save/restart/restore.
STOP/PANIC must release all notes. Test ARP only after the separate enable-control
repair is reviewed. Pi ARM64, live JACK, sustain, Helix and real REAPER remain
hardware acceptance requirements, not results of the cloud tests.
