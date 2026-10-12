# MIDI BAD MOTHER FUCKER development

Use the existing checkout; do not create worktrees unless requested. Preserve MIDI
note ownership, engine timing and existing project compatibility.

## Required web UI evidence

Every PR changing `headless/web/` must run `scripts/screenshots.sh`, visually inspect
**every generated view at all five viewport sizes**, and commit the updated real
PNG artifacts and `docs/screenshots/manifest.json`. Report layout failures and
unsupported views explicitly. Passing automated checks does not replace visual
inspection. Never substitute generated artwork, mocked APIs or fabricated views.

The single command starts a private native engine with deterministic `--demo` data
and the actual HTTP editor, captures 320×240, 800×480, 1366×768, 1440×900 and
1904×1032 viewport PNGs,
checks overflow/clipping/keyboard reachability, validates PNG dimensions, and stops
its own processes. It does not use JACK, hardware, saved user patches or a running
performance engine. Vertical scrolling is allowed; hidden controls are not.

The workflow also runs the real native `--chain` recovery browser test for
recording ARMED/RECORDING, named modulation menus, curve editing and reference
instrument chains. Chromium uses software rendering (`--disable-gpu`) and waits
for paint completion before capture: Cloud GPU rasterization can otherwise leave
partially painted PNGs even when DOM checks pass. Inspect the images themselves.
The metadata identifies demo and recovery fixture provenance separately.

## Codex Cloud setup

Required: Python 3 with venv, C++/CMake, the pinned ysfx library and JACK development
headers used by `scripts/headless-build.sh`, plus Chromium. Reuse existing caches.
The native setup is already documented in `scripts/headless-setup.sh`; it installs
OS packages and should run only in an appropriate development environment, never
as screenshot setup on a musician's Zynthian. Unprivileged extracted JACK headers
are supported through `JACK_INCLUDE`.

For an already prepared native environment:

```sh
scripts/screenshots-setup.sh
scripts/screenshots.sh
```

The setup pins Playwright in `.build/browser-venv`. It reuses system `chromium`
when available, otherwise downloads Playwright's pinned Chromium into
`.build/playwright-browsers` (requires `cdn.playwright.dev` network access).
Missing browser shared libraries should be installed during cloud environment
setup using `.build/browser-venv/bin/python -m playwright install-deps chromium`
with the appropriate OS package permissions. No package installation occurs in
the screenshot command. Browser launch failures are fatal, not skipped.

If no native binary exists, the screenshot command builds it with the existing
build script. Configure `YSFX_SOURCE`, `YSFX_BUILD`, and `JACK_INCLUDE` as needed.
`HEADLESS_BINARY` overrides the binary; it must match the checked-out JSFX/schema.
`SCREENSHOT_PYTHON` and `CHROMIUM_PATH` allow an existing Python/browser installation.
`PLAYWRIGHT_BROWSERS_PATH` overrides the retained browser cache.

A prepared Codex Cloud checkout can use:

```sh
export YSFX_SOURCE=/workspace/setup-tools/ysfx
export YSFX_BUILD="$YSFX_SOURCE/build"
export JACK_INCLUDE=/workspace/scratch/midi-deps/root/usr/include
scripts/screenshots.sh
```

To validate the layout detector independently:

```sh
.build/browser-venv/bin/python tests/test_screenshot_audit.py
```

Keep startup processes ephemeral: rerun the screenshot command in each task;
publication of a cloud environment does not retain live processes.
