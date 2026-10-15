# PR #48: less text, more signal

This third pass changes browser presentation and its tests only. No native/EEL2
engine, timing, JACK, serialization/schema, host adapter, installer or security
implementation changed.

## Measured audit

`tests/test_performance_density.py` loads the second-pass JavaScript/CSS from
commit `77b62ab` and the current UI against the same real native demo/API. It
counts visible action labels, parameter captions and explanatory text. Shared
column headers count once. Names, module identity, numeric values, routing/mode
values, event counts and accessibility labels are excluded. The saved text lists
and exact counts are in `performance-text-audit.json`.

| View | Label characters before → after | Reduction | Label words before → after |
| --- | --- | --- | --- |
| Six phrases | 481 → 71 | 85% | 98 → 30 |
| Three Instruments | 279 → 24 | 91% | 51 → 9 |
| Transpose editor | 19 → 12 | 37% | 3 → 3 |

The test compares every Phrase/Instrument button's accessible action identity
before/after, not just its count. All actions survive. The sixth phrase ends at
731px on a 1366×768 viewport with page scroll at zero. There is no overflow at
320, 800 or 1366px. Disclosure panels remain keyboard-accessible.

## Changes

- One sequencer header: # / NAME / PLAY / REC / M / S / MODE / VEL / V.DEC /
  T.DEC / MIDI / END / EDIT. Sliders keep values and bindings; ONCE-only decay
  slots remain intentionally empty for LOOP. Mobile rows reorganize controls
  and restore short local rail captions when shared columns no longer fit.
- Icon-only obvious actions, M/S, END for finishing a take, editable names,
  occupied/empty cues, real mute/solo and focus states. No inferred playback lamp.
- Instrument IN/OUT/VOL strip and connected modules with short parameter
  feedback. Insertion is a visible + beside the type selector. Order restrictions
  are in the chain tooltip and Instrument editor HELP, never silently changed.
- Binary editor switches and enum selectors use the existing descriptor type
  and numeric codes; enum names match JSFX. Continuous rails, numeric entry,
  expression ownership, curves and DONE/CANCEL are preserved.
- Compact header retains both signature lines. Restart authority is in PROJECT;
  compatibility prose is in COMPATIBILITY; Smart Switch tests are in TEST;
  popup instructions are in HELP. Open switch test panels survive state updates.

## Evidence and execution

```sh
HEADLESS_BINARY=.build/midi-web-rt \
SCREENSHOT_PYTHON=/workspace/setup-tools/venv/bin/python \
scripts/screenshots.sh --performance --output docs/screenshots/performance
```

Use your own built binary/Python paths outside this prepared cloud. Standard setup
is in AGENTS.md. This user-requested focused run produces the three primary views
at desktop and tablet sizes instead of dozens of repetitive captures. Each PNG
was inspected visually and audited for overflow/clipping/keyboard reachability.
Other views are exercised by the browser regression suite. The existing flat
`screenshots/` images remain historical second-pass evidence; current third-pass
images and manifest are under `screenshots/performance/`.

The density test needs baseline commit `77b62ab` available in local Git history.
Its asset override serves actual historical UI code, not mocked API responses.

Nine relevant Chromium suites passed: general editor/transport, generic editor,
Controller curves, Snapshot editor, compact patch workflow, names/parity, tactile
controls, text/inventory/layout audit and MIDI import/export. Additional tactile
coverage exercises a real touch volume adjustment and commits enum/toggle values
through the unchanged engine API. Names, sliders, persistence and transactions
remain functional.

A broader native combined run failed the timing-sensitive interrupted-morph
assertion (`9` versus tolerance `3`); an isolated rerun passed all 14 Snapshot
tests. No tolerance or engine behavior was modified. This UI pass does not
requalify the previously reported intermittent dummy-JACK clock-gap failures.

Native HOLD and per-phrase playing/recording telemetry remain limitations. Full
REAPER GUI, real Firefox/touchscreen and Zynthian/Helix hardware validation remain
pending. Nothing was merged or deployed.

## Actual files changed

- `headless/web/app.js`, `index.html`, `style.css`: performance matrix, compact
  actions/help, parameter presentation, adaptive layout and truthful state cues.
- `scripts/screenshots.py`: focused `--performance` mode; default full workflow
  remains available. `scripts/combined-test.py`: includes the new UI audit.
- Browser tests: `test_headless_browser.py`, `test_product_browser.py`,
  `test_snapshot_browser.py`, `test_tactile_browser.py`, plus new
  `test_performance_density.py`. Tests cover expanded tools, unchanged bindings,
  touch, toggles/enums, armed Learn visibility, maximum-length names and stable
  action identities. The density test waits for externally edited state before
  issuing revision-checked UI commands.
- This report, `performance-text-audit.json`, screenshot index and the six
  focused PNGs/manifest under `docs/screenshots/performance/`.
