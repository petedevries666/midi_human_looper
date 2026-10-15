# PR #50 recovery implementation

**Current issue #51 sprint status:** see [Zynthian V4 feedback sprint](zynthian-v4-feedback-sprint.md). The preservation checkpoint below is historical: STOP finalization and phantom voice observation have since been fixed and tested. User-reported installed hardware is now `d82f932` / PR #50; this sprint performs no hardware access.

Branch `fix/free-time-capture-origin`; dependencies #44 → #47 → #48 → #49 → #50.
No merge, deployment or physical-device access. Installed hardware remains PR #49.

## Behavioral references

Authoritative shared source is `/midi_human_looper.jsfx`, declared v1.27.1.
Baseline HEAD before this recovery was `adfff4df60d2b3cb634df8c1e84ab6d7e27495f4`;
that file's last baseline change was `59a82e22d01fc5d3bb6d64999fa1533f54f5200f`.
Historical v1.23.0 is at `72b92db091d5aef05d37b45057b62ffca390c867`, same path.
Its editor confirms the unchanged numeric mode mappings POLY/BASS/LAST/LEGATO,
RANDOM/UP/DOWN and FULL/DOWN/UP/BOTH. This is not a claim that every historical
behavior has been qualified on REAPER hardware.

## Implemented and exercised

| Area | Implementation | Evidence |
| --- | --- | --- |
| First attack | One sample origin, same-block chords, later rests preserved | 18 grid + 36 free source fixtures; actual SMF delta ticks |
| Recording lifecycle | Explicit FINISH/cancel; duration beyond former two bars; previous mode retained | Actual native API recording/export/save/load in LOOP/ONCE/HOLD |
| Independent free LOOP | Per-source lengths and anchors on existing sample clock | Actual shared MIDI periods 512 and 768 samples; new >two-bar take while LOOP plays |
| Overdub | Capture/rollback transaction, source duration retained, unrelated LOOP continues | Native API cancellation/export byte equality; simultaneous playback/overdub/FINISH/save/load; wrap-inside-block capture and single monitoring emission |
| Capacity/sustain | Failed take rolls back; FINISH closes unmatched notes and pedal | Shared/native 2049-event rejection fixture; sustain/held-note completion |
| ARP | Existing ENABLE parameter exposed last; chronological gate/step edges; paired sounding channel | Generated shared-engine output at 44.1/48/96 kHz and 64/128/512/1024 buffers; browser control and real dummy JACK chord |
| Musical labels | Shared descriptors retain enum numbers and publish named choices | Actual browser DOWN → native value 2 → generated MIDI; existing polyphony fixtures |
| Modulation | Named native sources, right-click/keyboard/touch context, immediate curve editor, NONE | Actual CC64 → volume64; bent multipoint CC32 → volume2 and actual CH1 CC7=2; save/load preserves source name/curve |
| Curves | Multipoint add/remove/drag, segment/bend operations, five shared factory curves, four custom slots, preview, DONE/CANCEL | Browser point/bend/custom-slot persistence; existing controller ownership tests |
| Phrase states | Engine observations per phrase; state painting without rebuilding rows solely for runtime state; focused idle rails follow physical CC while active drags remain protected | Actual ARMED → RECORDING → FINISHED and reload |
| Interface | Six compact strips, stacked velocity/time rails, horizontal wired blocks, contextual editor | Real Chromium artifacts under `docs/screenshots/`; all required sizes plus 1904×1032 |
| Rollback | Checkpoint before preflight; actual candidate capability probe; old grid durations validated against live clock | 11 updater tests including 48 clock/grid cases and immutable rejection |

LOOP-boundary and focused-controller feedback commit `df1ce01`.
Core commit `5e5238e`; browser `47a16ce`; rollback `262b8c9`; desktop density `b109382`; explicit CC7 evidence `a1f5232`.
The first combined runs exposed phrase-name and six-row-density browser regressions. A new LOOP-overdub boundary fixture also failed against the previous source (`layer_count(6)=2`, expected 4); admission now runs before MIDI draining, captures offsets 15/95 relative to the wrap and monitors the new attack exactly once. Name text is now
separate from observed status; the focused naming and Snapshot browser tests pass.
The complete updated suite passed: shared EEL/GUI/MIDI, native API/SMF, dummy JACK, normal and ASAN Controller checks, portability/persistence/updater and all Chromium workflows. The browser-only set was rerun after the final label/paint refinements. This does not certify physical hardware.

## Explicit remaining restrictions

- Native HOLD rejects ARP and mono instrument routes. Existing global ARP/mono
  ownership cannot safely distinguish a released phrase from other held sources;
  removing that guard would risk stuck or prematurely released notes.
- CLEAR and MIDI interchange remain STOP-only. They reject active operations
  instead of stopping unrelated phrases. Active targeted CLEAR needs a genuinely
  phrase-scoped router cleanup operation and is not claimed implemented.
- Existing legacy controller MIDI inputs remain exclusive. An explicit target
  replacement transfers that target's curve/ownership, but does not automatically
  migrate every other target sharing the legacy controller.
- Source SMF export retains compatible stored channel messages, but import still
  explicitly rejects non-note CC/program/bend/aftertouch files. It never silently
  strips them. Capture before the first positive Note On remains live-only.
- Native source names/custom presets are an optional version-2 Controller
  extension. Old runtimes explicitly reject it; no downgrade dropping metadata.
- Native Controller/Snapshot execution is not falsely claimed equivalent inside
  legacy REAPER JSFX. The portable original is preserved; unsupported execution
  is rejected. Factory curve geometry and parameter identities remain shared.
- Very short LOOP periods are bounded/rejected; event storage remains 2048 per
  phrase. Long sessions are bounded by event count rather than two bars.
- Firefox, physical ARM64, Helix and audible synthesizer/CC7/sustain behavior
  still require physical acceptance. Dummy JACK at 8192 frames is not low-latency
  certification, and Cloud callback safety guards remain enabled.

## Reproduce

Use the prepared environment documented in `AGENTS.md`:

```sh
HEADLESS_BINARY=$PWD/.build/midi-recovery python3 scripts/combined-test.py --native --jack --browser chromium --timeout 240
SCREENSHOT_PYTHON=/path/to/playwright/python HEADLESS_BINARY=$PWD/.build/midi-recovery scripts/screenshots.sh
```

Screenshot workflow starts private real native processes. It additionally runs
the production recovery browser test to capture actual recording states, named
assignment menus and curve response. No mockups or fake state flags.

Do not update hardware from this draft automatically. Review the final SHA,
back up projects/snapshot, STOP/disarm all processors, then use the existing
runtime updater. Its restart interrupts the Zynthian UI and MBMF child processes;
it does not change JACK routing/services, registration, tokens or LUMAZ. Old-grid
rollback of incompatible free-time projects is rejected; restore a separate
compatible pre-update project explicitly rather than truncating current data.

## Final executed validation

- `scripts/combined-test.py --native --jack --browser chromium --timeout 240`: PASS,
  including 11,685 actual EEL/GUI/MIDI checks, 18 grid and 36 free SMF fixtures,
  162,709 normal/ASAN Controller policy checks plus 543 host checks per run,
  native API, updater, persistence/bridge, dummy JACK and Chromium suites.
- `tests/test_recovery_browser.py`: PASS mapped enum manual ownership, named
  contextual assignment, physical-equivalent CC and actual CC7 output, curved
  scaling, custom-slot/save/load retention, ARMED/RECORDING/FINISHED and ARP output.
- `tests/test_zynthian_update.py`: 11 PASS, including actual private canary startup.
- New LOOP-wrap fixture: previous source fails with 2 events; corrected source
  retains 4, preserves offsets 15/95 and emits exactly one monitored new attack.
- Screenshot workflow uses actual private native engines; all PNG dimensions and
  layout checks pass. Software Chromium avoids Cloud GPU partial-paint artifacts.

The last engine-source change is `df1ce01a4eb7f202f14fc465eb4b33e30e7b01c6`.
The screenshot manifest reports exact UI source and native binary revisions,
including its honest dirty-build suffix. Subsequent evidence commits do not
claim a different compiled musical engine.

Classification: code/evidence preserved for review; **not yet ready for deployment**;
**not a declaration that the entire requested recovery or studio/live parity is
complete**. Guarded HOLD routes, active targeted CLEAR and legacy-source migration
above need further ownership work. Native independent free LOOP periods also
remain a platform difference from REAPER's legacy master-loop playback; do not
assume that JSFX BASE export provides equivalent execution of such a project.


## Preservation checkpoint (2026-10-12)

No additional feature development was performed during this preservation step.
All seven local implementation commits and the uncommitted evidence are retained.

Two newly identified gaps are outside the passing regression coverage:

1. `headless/engine.cpp` handles `chain_stop` by executing `panic_bridge` before
   `chain.command`. That reset may prevent `finishFree` from recognizing an active
   new take with no previous content. This is a source-inspection finding, not a
   reproduced result. Next coding step: add an actual HTTP `chain_stop` test during
   recording with a held note and sustain, inspect source/export/save-load, then
   finalize or cancel the take before resetting runtime recording state if the
   test confirms the defect. Preserve source data and existing PANIC behavior.
2. Final visual inspection found partially painted upper sections in
   `recovery-instrument-chains-1904x1032.png`, despite software Chromium and passing
   DOM checks. The real PNG is preserved without alteration, but must not be used
   as proof of complete visual parity. The recording screenshot paints fully.
   After preservation, stabilize screenshot capture and rerun/inspect the affected
   views. Zero overflow is not proof of complete rasterization or visual parity.

Keep PR #50 draft. Physical hardware remains on PR #49. No deployment, merge,
reset, source discard, token change or physical-device access occurred.
