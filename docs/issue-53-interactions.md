# Hardware UX recovery — issue #53 / PR #50

No physical device is accessed by this change. It extends the existing recovery
branch and does not change JSFX musical policy, patch schema, Zynthian registration,
updater behavior, token, JACK routing or installed configuration.

## Controls

- Instrument Transformer selectors include **+ ADD EMPTY TRANSFORMER**. Select it
  and press **+** to open a blank draft. Choose a supported type and DONE to insert
  a default instance and open its live parameter editor. CANCEL leaves the chain
  unchanged. Untyped blanks are editor drafts, not executable/persisted modules;
  existing typed insertion and presets retain their behavior.
- **Enter / Space** finalizes the actual active recording/overdub using the same
  FINISH action as the phrase row. It does not send PANIC or stop other phrases.
  Armed-only takes are untouched. Editing fields, focused buttons/selects,
  contenteditable, dialogs, modifier chords and key repeat keep their own semantics.
- **TAP / DOUBLE / HOLD TEST** previews the configured gesture via the existing
  shared Smart Switch dispatcher without a MIDI binding or enabling hardware
  input. Feedback reports the dispatched action/step, no action, empty source or
  missing target. Preview does not commit the switch editor's uncommitted draft.
- Controller **REMOVE** removes only that source and its mappings. The formerly
  ambiguous mapping DELETE icon now reads **REMOVE MAPPING**, with confirmation;
  it removes only the parameter binding. The separate X was the physical MIDI FORGET action; it now visibly reads
  **CLEAR MIDI**, retaining the source and mappings, and is absent when unassigned.
- Each Controller has a compact **TEST** slider. CC and unassigned sources use
  0–127; NOTE sources use binary 0/127. Mouse/touch input and keyboard movement
  enter the existing Controller policy core by stable source ID, including curves,
  takeover, GLIDE/SLEW and return policies. Test input never synthesizes MIDI input,
  captures/cancels Learn, creates mappings or changes committed base values.
  The slider position is a transient browser gesture, not saved patch data.

## Validation and first hardware check

`tests/test_issue53_browser.py` starts the actual native `--chain` engine and HTTP
server. It exercises blank creation/CANCEL, live mapped transpose and emitted MIDI,
Learn isolation, save/load/removal, targeted recording shortcuts with an independent
running LOOP, and unbound TAP playback. `tests/controller_host.cpp` additionally
checks GLIDE progression, NOTE scaling, missing/out-of-range rejection and immutable
configuration through the actual policy adapter. The combined runner includes the
new browser workflow.

Run in the prepared Cloud environment:

```sh
HEADLESS_BINARY="$PWD/.build/midi-recovery" \
  /workspace/setup-tools/venv/bin/python tests/test_issue53_browser.py
scripts/controller-test.sh
SCREENSHOT_PYTHON=/workspace/setup-tools/venv/bin/python \
  HEADLESS_BINARY="$PWD/.build/midi-recovery" scripts/screenshots.sh
```

The browser test also accepts `MIDI_BROWSER=firefox` with Playwright Firefox
installed. In this Cloud session the Firefox download was denied (HTTP 403,
`Domain forbidden` for cdn.playwright.dev and Microsoft's fallback); Firefox is
not qualified by a Chromium pass.

After human review and an explicitly selected deployment SHA, verify on V4:
start a LOOP, REC another phrase, play/release notes, focus the performance surface
and press Enter or Space. Only the take should finish; export should start at tick
zero. Test TAP on a populated sequence with MIDI TYPE UNASSIGNED; compare its
output with a Helix gesture. Assign a named Controller to transpose/volume, move
its TEST slider, then the physical controller, and verify configured takeover and
BACK TO STATE. Save/reload and confirm assignments remain. STOP/PANIC must release
notes. ARM64, real Firefox/Helix, synth audio and hardware timing remain physical
acceptance tests; Cloud dummy JACK is not hardware qualification.

## Executed evidence (2026-10-12, x86_64 Cloud)

The complete combined suite passed with `--native --jack --browser chromium
--timeout 240`, using the pinned ysfx checkout, extracted JACK headers/daemon and
`CHAIN_JACK_BLOCK=8192`. This includes 11,685 actual EEL/GUI/MIDI checks, 18 grid
and 36 free-time exported-SMF fixtures, 162,709 Controller policy checks and 558
host checks (normal and sanitizer), native HTTP/persistence/bridge/updater tests,
actual dummy-JACK routing/ARP/ordering/PANIC tests and the Chromium suites.
A subsequent focused run additionally passed keyboard overdub finalization while
an independent LOOP continues, retaining both original and overdubbed pitches.

Observed mapped MIDI: manual Controller maximum sends source note 60 through
TRANSPOSE +48 as note **108**, with a paired release. Unassigned/disabled Smart
Switch TAP starts the configured source note **60**, updates PLAYING and dispatch
counter/step; an empty sequence produces an explicit explanation. The keyboard
capture's exported first Note On remains at time/tick zero.

Cloud could not lock all JACK test memory (`Cannot allocate memory`), and the
intentional input-flood test recorded an XRUN notification and bounded overflow.
Safety guards remained enabled; the complete runner passed its cleanup/order
assertions. This does not qualify Raspberry Pi latency or hardware reliability.

Screenshot evidence: the final one-command run generated **133 valid PNGs** and
an updated manifest, with no overflow/clipping/reachability findings. Every
produced view was inspected at its generated viewport, using contact sheets and
full-resolution checks of the changed controls. This caught the ambiguous FORGET
X and narrow desktop TAP feedback; both were corrected and recaptured.
Representative views: [Controller test / CLEAR MIDI](screenshots/controller-live-test-1366x768.png),
[Smart Switch result](screenshots/smart-switch-test-1366x768.png),
[blank Transformer draft](screenshots/empty-transformer-800x480.png).
The manifest records UI source `9aecd5f` and native build `c828546.dirty`;
there were no later native engine changes. The dirty marker includes retained,
uncommitted screenshot output from preceding validation runs.

The remote branch advanced during this work with updater commit `1500de4`.
It was preserved through merge `40355c7`, without force-pushing or rewriting it.
All 11 updater tests, including actual native preflight/checkpoint tests, passed
against the combined branch. The full combined suite preceded the final CLEAR
MIDI label/feedback CSS refinements; the issue #53 and existing Controller browser
regressions were rerun after those changes, followed by the complete screenshot
workflow. No feature was disabled or timing assertion relaxed.
