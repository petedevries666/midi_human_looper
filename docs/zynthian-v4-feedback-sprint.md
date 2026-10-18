# Zynthian V4 feedback sprint — issue #51 / PR #50

The user reports physical testing of `d82f932` on Oram ARM64. This sprint runs only
in Cloud, on `fix/free-time-capture-origin`. No device access, deployment, merge,
JACK/OS changes, snapshot alteration or LUMAZ change.

## Working increment

- GLOBAL STOP finalizes the current capture before resetting runtime state. A
  failing production HTTP/export test reproduced an unpaired note in the previous
  candidate; the correction preserves its first attack at zero and closing Off.
- The shared JSFX has 12 voices. Native code previously scanned 24 and read the
  adjacent phrase-ID table as active flags, producing phantom playback. Observers
  now validate the shared capacity and stop reporting expired/empty playback.
- LOOP PLAY changes to STOP and stops just that loop using saved source ownership
  and the existing instrument router. HOLD retains pointer/keyboard release and
  provides STOP for a MIDI-held phrase. ONCE remains retriggerable PLAY.
- Inactive CLEAR works while another loop plays. It uses bounded callback writes
  and does not pause JACK for a worker-side RAM edit. Clearing an active or
  recording target remains rejected; CLEAR is also guarded while any capture is armed/active. Only content is cleared, not its settings.
- Controllers can be created, named/renamed, edited, learned and removed. Streaming
  observations preserve rename focus. REMOVE deletes only that source's mappings
  and cancels its Learn; it does not PANIC unrelated controllers.
- Three phrase rails share one horizontal row; base velocity reads one decimal.
  Numeric curve coordinates are collapsed under POINTS / PRECISION. Existing
  graphical edits, bends, presets and Controller policies remain available.
- Transformer edits apply live through the existing parameter/ownership API.
  Selecting another module flushes the current edits and replaces the same editor.
  DONE closes; CANCEL restores this editor's values when they remain unchanged by
  other writers. Engine-safe deferred edits retain their existing scheduling.
- Smart Switch OPTIONS exposes the existing 64-step shared phrase sequencer:
  ordered/reorderable chips, FORWARD / REVERSE / PING-PONG / RANDOM, press or gesture
  classification, TAP/DOUBLE/HOLD actions, MIDI assignments and RESET ON RE-ENTRY.
  SNAP opens the existing snapshot-action editor. Configured snapshot actions
  visibly take precedence; the sequencer does not silently overwrite them.
- Confirmed CLEAR PATCH restores the current MBMF factory patch: three initial
  instruments, empty chains/phrases, cleared mappings and MBMF snapshots. It
  stops this processor. Saved patch files, other chains and Zynthian snapshots
  are untouched; SAVE is required to persist the cleared patch.

## Sequencing contract

NEXT advances one step per configured gesture through the original `sw_traverse`
/ `sw_action` dispatcher. No second sequencer, timer or scheduler was added.
Authored MIDI channels and instrument input/output settings determine destination;
portable projects contain no Zynthian chain IDs. The native fixture exercises Bass
CH1, Piano CH2 and Synth CH3, actual output, MIDI press/release and re-entry reset.
LOOP layers can continue together; ONCE/HOLD retain legacy voice/choke semantics.
This is not autonomous timed step advancement or a new four-track CONDUCTOR.
RANDOM retains the existing shuffle bag; no new cross-restart random-seed contract.

## Remaining work

- Base velocity still has its established **0.2–3.0** range; **0.0 is not exposed**.
  Implement paired zero-gain suppression first, including live transitions and
  overlapping notes, then extend the authoritative descriptor and migrate stored
  normalized Controller/Snapshot values. Simply changing the lower bound would
  silently alter older mappings and recalled values. No fake zero control ships.
- Native HOLD retains its documented mono/ARP guard. Active targeted CLEAR still
  needs the corresponding complete ownership support. Import/export restrictions
  and legacy-expression migration limitations remain documented in the recovery
  record. Controller BACK TO STATE / TAKEOVER / EASING were not redesigned.
- Smart Switch MIDI fields can be configured directly; this iteration does not add
  a separate Smart Switch Learn interface. Existing Controller/phrase Learn stays.
- Physical ARM64/Firefox/Helix/sustain and low-buffer JACK tests remain pending.
  Dummy JACK in Cloud uses 8192-frame buffers without weakening timing guards.

## Human acceptance after reviewing a new SHA

1. Back up the current MBMF patch/project and Zynthian snapshot. Update only by the
   existing reviewed runtime updater; this work does not run it on hardware.
2. Hard-refresh Firefox. Confirm the software revision in diagnostics. Save the
   old patch before confirming CLEAR PATCH for a disposable test patch.
3. REC an empty ONCE phrase, play a held note, then GLOBAL STOP. Export MIDI and
   verify first attack at tick zero and a matching Off. Reopen browser: no phantom
   PLAYING, ARMED or RECORDING status.
4. Select LOOP, PLAY, then its STOP. Keep another loop playing while CLEAR removes
   an inactive phrase. Verify the other loop continues and PANIC releases notes.
5. Test ONCE retrigger and supported HOLD pointer/keyboard/Helix release. Releasing
   or pressing STOP on a hardware-held phrase must end its notes safely.
6. Type a Controller name slowly. EDIT, MIDI LEARN, assign a rail, bend its curve;
   REMOVE that source while another source remains assigned. SAVE/LOAD and refresh.
7. Configure three instruments IN/OUT 1, 2, 3. Use source phrases on those channels.
   In OPTIONS build three steps; exercise four traversal modes and re-entry reset.
   Confirm TAP/DOUBLE/HOLD and SNAP assignments retain the intended precedence.
8. Change a Transformer live while playback continues; switch to another editor.
   CANCEL a preview and verify unrelated settings survive. Monitor XRUNs.
9. SAVE/LOAD, restart, restore and test PANIC. Disconnect browser/controllers and
   reconnect. Use the existing documented rollback guard for older grid runtimes;
   do not truncate new free-time phrases to make rollback succeed.

## Executed validation

- Final `scripts/combined-test.py --native --jack --browser chromium --timeout 240`: PASS using the prepared Cloud toolchain and `CHAIN_JACK_BLOCK=8192`.
- Six actual native HTTP/SMF tests, including synthetic Smart Switch STOP/PANIC during capture, three-channel sequencing, MIDI press/release and re-entry reset: PASS.
- Shared EEL/GUI/MIDI: 11,685 checks. Controller policy: 162,709 checks plus 543 host checks, normal and ASAN. Existing recording fixtures, portability, bridge, updater and Chromium suites: PASS.
- New hardware-feedback browser workflow: PASS rename focus, targeted EDIT/REMOVE, aligned rails, live MIDI parameter/output changes while the pointer is held, module switching, real STOP/CLEAR, sequence SAVE/LOAD and confirmed CLEAR PATCH.
- One earlier JACK run failed with 1 XRUN and 1,986 of 2,048 expected PANIC releases, no engine queue overflow. Another run hit the existing missed-callback safety stop during HOLD (3 XRUNs). No timing/overflow assertion or safety guard was weakened. An orphaned private non-JACK test engine was cleaned up; the final serial combined run passed. This does not establish why every XRUN occurred or certify low-buffer hardware reliability.
- A browser run revealed that live writes could disable a button between pointer-down and pointer-up, swallowing HOLD. The bounded coalescing live queue now avoids global button disabling. Unchanged Controller DOM is preserved during streaming updates.
- The first screenshot run rejected a 320-pixel live-editor overflow; the nested range grid placement was corrected. Failed runs leave previous published images intact.

Native implementation commits: `bfc450f`, `025867f`, `380c16c`, `967f28f`, `f8c9871`. Screenshot manifest identifies exact source/build provenance; documentation and PNG evidence commits follow without claiming a different compiled engine.

**Suitable for human-reviewed, controlled V4 functional retesting; not a completed release or low-latency hardware qualification.** Velocity ×0.0 and the listed ownership/interchange restrictions remain unfinished.

Screenshot command: `SCREENSHOT_PYTHON=/path/to/playwright/python HEADLESS_BINARY=$PWD/.build/midi-recovery scripts/screenshots.sh`. Final run: **118 real PNGs**, five viewport sizes, zero layout failures; every view visually inspected. Software raster priming resolves the previously observed partial-paint captures in this run. Primary performance, reference chains, live editor, ARMED/RECORDING, assignment menu and curve screenshots are actual native fixtures. No hardware or mock API is used.

After the combined pass, narrow-screen rails were grouped into three equal peer controls and shared headers aligned; the focused hardware browser, density and full screenshot workflow were rerun. Core MIDI code was unchanged.

Next coding step: implement note-pair-aware zero-gain handling and versioned normalization migration before exposing velocity ×0.0. For the old 0.2–3 range, transform stored normalized bases/curve Y values with `(0.2 + 2.8*y)/3` when extending to 0–3, while retaining X/bends and physical defaults; explicitly version the new representation and preserve unsupported originals. Validate live zero/nonzero transitions, overlap, sustain, controllers, snapshots and REAPER interchange. Do not simply change the slider bound.
