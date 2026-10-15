# PR E final validation and delivery

Draft #61, branch `feat/conductor-step-layer-editor`, stacked on #60
`48417cfdfe39ebd92dcd9d544d693903efa32bad`, then #58/#57/#56/#50.
Contract: #55 `73cdee5604992ca3bd68e4c6c3b97c545333b127`.
Tested implementation: **`c9b38e1b03568e013134ac77fad31975fabf563e`**.
Later delivery commits contain documentation, evidence and PNGs only. The resumed
session recovered these completed results and finished visual review; it did not
rerun expensive suites or change production code.

## Actual results

| Executed gate | Result |
| --- | --- |
| Complete selected combined native/JACK/Chromium suite | exit 0 |
| Production shared EEL/GUI/MIDI | 18,508 checks PASS |
| Controller normal and ASAN | 162,709 core + 558 adapter checks each PASS |
| Strict native child sanitizer gate | functional exit 0; diagnostic files 0 |
| C persistence and D execution under native ASAN | 23 + 3 tests PASS |
| E browser authoring and real JACK port output | PASS |
| Pending-PANIC mode selection | PASS: requested LOOP 0, native mode 0, one actual parameter POST |
| Pointer-down EDIT / telemetry race | PASS: old button stayed connected during press, VELOCITY editor opened, native transpose 12 |
| Real Chromium screenshots / layout audits | exit 0; 163 PNGs; zero reported layout violations |
| Legacy cross-source ONCE | unchanged shared/native XFAIL, intentionally distinct from independent admission |

The positive race fixtures preserve the delayed real PANIC reply, native
parameter telemetry, native-value checks and idle controls. Neither was converted
to a synthetic PASS. Original failing signatures remain in D's evidence.
No tests or MIDI/overflow guards were removed or weakened.

`combined-final.log` and `exit-codes.log` are the completed frozen run. Compiler
attribute warnings and Cloud JACK memory-lock warnings are retained. ASAN covers
instrumented host adapters/intercepted allocations; ysfx's static library and
all generated EEL machine code are not fully instrumented. This is Cloud x86_64
functional validation, not physical V4 ARM64/Helix/Firefox qualification.

## Browser to real MIDI

The E JACK fixture authors four STEPS through the real browser, selects four
existing PHRASE identities, commits with DONE, requires **PATCH SAVED**, reloads,
and invokes existing TEST TAP. A receiver captures the actual engine JACK port:
**`60,62,64,65,60`**. Those events are not an API action echo.

The same browser then edits a two-layer STEP. Its attacks **60 and 62 share
frame 1,318,912 and offset 16** in the final trace. Targeted STOP emits Off60;
legacy STOP emits Off62. Missing-reference silence, same-pitch ownership,
PANIC receiver cleanup, chronological timestamps and silent LOAD remain D's
unchanged assertions. `jack-output.json` includes the complete receiver trace.
The fixture's legacy log heading says “hardware-like PRESS”; in its E variant,
the first five PRESS actions come from browser TEST, not a physical footswitch.
The later two-layer admission uses the separate JACK input client.

The browser fixture additionally covers EMPTY SAVE, automatic next STEP,
layer/step move/delete, STEP drag, block duplication/new ID, UNDO, local
INHERIT/OVERRIDE, source isolation, touch taps, keyboard range adjustment,
missing UUID preservation, reconnect, stale concurrent drafts and locked controls
during a delayed native commit reply. DONE observes the new native revision
before closing, so an immediate SAVE cannot use the old revision.

## Screenshots and visual review

All 163 manifest artifacts were dimension-verified and visually reviewed through
16 contact sheets spanning 320×240, 800×480, 1366×768, 1440×900 and 1904×1032.
The new editor was also inspected at original screenshot size for empty,
four-step/two-layer and override views. Black/gray/yellow styling, real sliders,
source labels, icons and accessible controls remain visible; no additional
blocking layout defect was found. Narrow displays intentionally require vertical
scrolling and wrap STEP columns; properties appear beneath the board. This is
not a claim of a finished hardware screen or complete JSFX visual parity.

See [screenshot index](../../screenshots/README.md) and
[manifest](../../screenshots/manifest.json). Source menus and editor captures are
actual drafts over native `--demo` data; demo PHRASES 3/4 are explicitly EMPTY.
The separate MIDI acceptance fixture supplies real notes in all four sources.

The screenshot source SHA is `c9b38e1`; runtime identifies `c9b38e1.dirty` because
previously generated PNGs were still uncommitted at build time. Production,
script and test sources matched the tested commit; no code changed during the
final run. `summary.json` records source and normal-binary SHA256 hashes. No clean
build or physical qualification is fabricated from the dirty suffix.

## Exact executed commands

Prepared Cloud exports: pinned ysfx `8077347ccf4115567aed81400281dca57acbb0cc`,
`YSFX_SOURCE=/workspace/setup-tools/ysfx`, `YSFX_BUILD=$YSFX_SOURCE/build`,
`JACK_INCLUDE=/workspace/scratch/midi-deps/root/usr/include`, extracted `JACKD`
and `JACK_DRIVER_DIR`, `TEST_PYTHON=/workspace/setup-tools/venv/bin/python`,
`CHROMIUM_PATH=/usr/bin/chromium`, `CHAIN_JACK_BLOCK=8192` and
`HEADLESS_BINARY=$PWD/.build/midi-headless-engine`.

```sh
scripts/headless-build.sh
CONDUCTOR_TRACE=/tmp/mbmf-e-jack-final-proof.json "$TEST_PYTHON" scripts/combined-test.py --native --jack --browser chromium --timeout 240
SCREENSHOT_PYTHON="$TEST_PYTHON" scripts/screenshots.sh
```

The combined runner includes E browser/JACK tests and both race fixtures with
`COMPARE_ROOT` set to the checkout. Functional JACK uses a private 48 kHz /
8192-frame dummy server; no musician's JACK routing is modified.

Sparse shared-EEL 128-frame measurements in the final log, 100 blocks after ten
warmups: 1/2/12-layer medians **28.284 / 30.058 / 47.557 µs**, p95
108.198 / 164.506 / 134.029 µs, maxima 442.366 / 562.818 / 269.828 µs.
These noisy Cloud measurements neither establish Pi latency nor resolve Q3.
E introduces no callback or ownership changes and retains the 12-voice budget.

## Earlier failures retained

- `screenshots-initial-layout-failure.log`: initial desktop CONDUCTOR button
  overlapped OPTIONS; CSS row placement was corrected and final screenshots pass.
- `combined-initial-import-failure.log`: runner omitted the race fixtures' import
  path; fixed by supplying their existing `COMPARE_ROOT`, without changing asserts.
- `combined-interrupted.log`: an intermediate run stopped deliberately while
  final UI correctness fixes were prepared; it is not qualification evidence.
- `combined-save-race.log` and `jack-save-race-diagnostic.log`: real E regression,
  premature DONE close allowed SAVE with stale revision, resulting in “patch not
  saved”. Fixed before the final frozen run; tests now require successful SAVE
  and assert the restored four-step document before layer edits.

## Verdict and boundaries

**GO for the next scoped phase F development**, retaining these regression gates
and measuring open Q3 decisions. Phase F/MOVEMENTS has **not** started.
No merge/deployment authorization follows from this result.

Limits: STOP-only configuration activation; unsupported MOVEMENT/JOIN/REVEAL/FECK
and advanced execution options remain unavailable/preserved; independent mono/ARP
remains restricted; REAPER adapter still explicitly refuses native Conductor
loading. TEST TAP is PRESS-only; HOLD release requires physical RELEASE or the
existing STOP/PANIC controls. Undo is local to the Conductor draft. A complete
cross-application undo/docked-editor design and physical hardware qualification
remain separate work.

No MIDI engine, JSFX gfx, REAPER adapter, installer, portable schema or issue #54
modifications. All 25 preserved issue #54 working files were hash-checked intact.
GitHub reported MERGEABLE / CLEAN against #60 at delivery inspection; the full
stack remains unmerged and #61 remains DRAFT.
