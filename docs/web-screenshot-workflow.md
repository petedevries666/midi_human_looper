# Codex Cloud screenshot workflow

See [AGENTS.md](../AGENTS.md) for setup and the mandatory UI PR policy.
After setup, run **`scripts/screenshots.sh`** from the checkout. The command builds
an absent native binary using the existing build script, starts the real JSFX host
with `--demo` and a private HTTP worker, captures the editor, and cleans up. It uses
the existing integration-test lifecycle rather than a second demo application.

[Browse the real PNG artifacts](screenshots/README.md). The manifest records the
browser version, checkout revision, viewport dimensions and per-view layout checks.
All PNG dimensions are verified. Failed layout runs retain diagnostics under
`.build/screenshot-failures/` and do not publish their images into the documentation.
No visual baseline comparison is claimed: review the actual PNGs before committing.

The fixture has two recorded source phrases, three Instruments, the existing demo
Smart Switches, and controller source 101 assigned to CC21/channel 2. Snapshot and
Transformer examples are created through actual application commands. Playback is
stopped. Configuration and interaction order are reproducible; live diagnostic
clocks, callback timings and counters naturally vary between runs. The native host
uses its **mock MIDI backend** for this workflow, executing the actual JSFX and
Controller/Snapshot code without JACK or physical MIDI. HTTP responses and HTML are
not mocked. This validates the editor, not physical Zynthian timing or hardware.

Coverage includes PATCH, blank/populated Snapshots, inclusion/configuration editor,
A/B morph controls, Smart Switch popup, six-phrase page, phrase MIDI import/export
editor, Instruments, Transformer chain/editor, Controller mapping/advanced options,
and engine diagnostics. Scrolling dialogs have supplemental bottom screenshots.

**CONDUCTOR has no implemented engine/editor on the PR #44 integration base.** Its
absence is recorded explicitly in the manifest. No fake CONDUCTOR screenshot is
provided. When that interface is implemented, extend the view list in
`scripts/screenshots.py` in the same UI PR and remove the unsupported entry.

The automatic audit detects horizontal page/control overflow, hidden/clip ancestor
cropping, clipped button labels, removed keyboard tab stops, and controls that
cannot scroll into the viewport. Intentionally collapsed sections, disabled controls
and inert modal backgrounds are handled separately. This is a layout/reachability
check, not a complete accessibility certification; contrast and usability still
require visual inspection.

Two small existing layout defects were exposed and corrected: fixed-width numeric
inputs in narrow dialogs and Snapshot menus opening outside the 320px display.
The MIDI engine, schema, scheduling and musical behavior are unchanged.

## Verified in Codex Cloud

- `scripts/screenshots-setup.sh`: pinned Playwright installed; existing system
  Chromium reused. CDN browser downloads are blocked in this cloud environment.
- `scripts/headless-build.sh`: existing pinned ysfx/JACK-header caches reused;
  native build and bounded FIFO self-test passed.
- `scripts/screenshots.sh`: real artifacts generated at all requested sizes.
- `tests/test_screenshot_audit.py`: seven browser fixtures, including intentionally
  broken overflow, clipping, fixed unreachable controls and keyboard access.
- Existing product, Controller, generic editor and reconnect/PANIC Chromium suites.

No physical Raspberry Pi, Zynthian, Helix or REAPER validation is claimed.
