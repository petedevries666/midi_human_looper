# PR #48: graphical control restoration

This pass updates the existing browser components, not the engine or schema.
Reference: JSFX @gfx phrase strip (six rows, numbered record circles, M/S,
velocity rails, logarithmic time decay), instrument volume rail, Transformer
rectangles and expression curves. Compared with the pre-#48 browser at
`a1ebed5` and first #48 pass at `d9eee44`.

| Control | JSFX | First #48 browser / regression | This implementation |
|---|---|---|---|
| Transport | Musical glyphs, status, panic | Text STOP/status | Local SVG STOP; truthful native status retained |
| Phrase | Numbered record circle, editable name, trigger glyph | Text-heavy form strip | Number badge, SVG record/trigger, editable name retained |
| Mode | Clickable LOOP/ONCE/HOLD label | Native select; HOLD unavailable | Same valid engine actions; no fake HOLD |
| Velocity | Filled drag rail | Number field | Filled pointer/touch/keyboard rail, multiplier readout |
| VEL DECAY | Rail + percent | Number field | Rail + percent, ONCE visibility retained |
| TIME DECAY | Logarithmic bipolar rail | Number field | Logarithmic .5–2 rail, unity reset, multiplier |
| Instrument | Enable, name, channel selectors, volume rail | Volume number field | Visible volume track + position, independent channel selectors |
| Transformers | Connected rectangles, selection | Rectangles with mostly text | Connected blocks, parameter meters, selected yellow border, editor/actions |
| Parameter editor | Wide filled rails, numerical values | Native range with weak affordance | Filled tracks, bright position markers, numeric draft editing retained |
| Curves | Multipoint graphical editor | Canvas curve + numeric points | Visible point handles, direct pointer/touch dragging, numeric/bend editing retained |
| Smart Switch | Compact blocks, options popup | Text actions | SVG options/testing, unchanged transactional popup |
| Controller | Learn, curves, ownership | Generic editor/curve | MIDI glyph, graphical point editing; ownership unchanged |
| Snapshot | Native feature beyond legacy JSFX | Recall/morph/update text | Local action icons, existing A/B slider and transactions retained |
| Patch | Save/load actions | Text buttons | Local SVG save/load with accessible action names |

Range inputs use browser pointer capture/touch and keyboard semantics. Local
movement updates the readout; `change` commits through the authenticated,
revision-checked API. Double-click resets. Background model rebuilds are deferred
while a slider owns focus so a live state update cannot detach a drag. Tab/blur
returns to normal rendering. Editor sliders remain drafts until DONE; CANCEL
never commits. Numeric parameter ranges and bindings are unchanged.

## Remaining differences

Native HOLD needs an engine lifecycle change; it stays explicitly unavailable.
The current state API has no per-phrase playing/recording identity. The UI shows
actual processor transport status, phrase number/content, mute/solo and selection
focus; it does not invent a per-phrase playback lamp. Four-track CONDUCTOR remains
unimplemented in this branch. Legacy expression assignment rails remain disabled
in the module editor; its multipoint editing is not exposed there. Controller
mapping curves support direct point dragging and numeric bend editing. No new
Controller/Snapshot parity is claimed. Ordering restrictions remain explicit.

## Validation

`tests/test_tactile_browser.py` exercises actual native parameter changes from
mouse drag, keyboard, mute icons, isolated phrase/instrument bindings, module
editing and refresh persistence. `test_controller_browser.py` additionally drags
a curve point before testing transactional cancellation and persistent mappings.
Use the existing combined runner and `scripts/screenshots.sh`; see AGENTS.md.
Screenshot backend is the real native engine with a mock clock; JACK regressions
use desktop dummy JACK. Neither qualifies physical V4, Helix or real REAPER GUI.
The existing update/rollback instructions in `web-jsfx-parity.md` still apply.

Rapid keyboard changes on a single rail are coalesced serially through the same
command path; a rejected update restores the last accepted position. No new
control ownership policy or engine writer is introduced. Native instrument
volume, phrase velocity/decay, module drafts and routing remain independently
addressed by their existing stable identities.

Representative actual browser captures at 1366×768:
[Phrase strips](screenshots/phrases-1366x768.png),
[Three Instruments](screenshots/instruments-1366x768.png),
[Transformer editor](screenshots/transformer-editor-1366x768.png),
[Smart Switches](screenshots/smart-switches-1366x768.png),
[Header / transport](screenshots/patch-1366x768.png).

## Executed results for this pass

- `python scripts/combined-test.py --native --browser chromium --timeout 240`:
  **PASS**, including native/JSFX host regressions, controller normal/sanitized
  checks, patch/project/bridge/SMF persistence, editor transactions, snapshots,
  naming, direct sliders, MIDI Learn and browser import/export.
- `python tests/test_screenshot_audit.py`: **7 PASS**. `scripts/screenshots.sh`:
  all artifact layout checks and PNG dimension/existence checks passed. Every
  view was visually inspected at 320×240, 800×480, 1366×768 and 1440×900.
- The full `--native --jack --browser chromium` command was executed. Its first
  run passed all actual dummy-JACK graph, overload, timestamp-ordering,
  three-chain and dedicated fanout tests, then failed the obsolete browser
  VOLUME-number-field locator. That test now uses actual keyboard slider
  interaction and passes, including a rapid 68-step adjustment.
- Subsequent full JACK reruns **failed intermittently**: one observer failure
  with `lateBlocks=1`, zero active notes and zero output overflow; an isolated
  rerun stopped chain recording after `chainFrameGap=8192`,
  `chainClockGap=16384`, 26 late blocks and maximum callback 249780 µs. The
  second failure occurred without concurrent screenshot jobs. These outcomes
  do not constitute a consistently green JACK release qualification. No guard,
  timeout, buffer assertion or engine code was relaxed for this UI pass.

The screenshot manifest records the actual engine build revision and that UI
source had uncommitted changes during capture. The native binary is unchanged
by this second pass. Real REAPER GUI, Zynthian V4, Helix touch/pedal performance
and hardware JACK load/interrupt qualification remain pending. Reproduce the
clock-gap condition and diagnose it independently before a live release.
