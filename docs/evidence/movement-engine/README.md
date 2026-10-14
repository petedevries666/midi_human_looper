# Phase F executed evidence

Draft PR #62, stacked on #61 `86e2f52be6c5810b0e551f747fe885d6b92f700f`.
Runtime/web source qualified at `a4cb1b8d8fd91bc8c5ec5f9ae944d7e9077c583c`.
Final evidence/test/metadata changes do not change those production files;
`summary.json` records their SHA256 hashes and the exact native binary hash.
Screenshots used d550d7a for demo and a4cb1b8 for recovery; those commits' production
runtime/web files are byte-identical (the intervening fix changes screenshot flow).
No merge, deployment or phase G work; original issue54 file hashes remain intact.

| Executed check | Result |
|---|---|
| Combined native/JACK/Chromium with prepared venv | exit **0** |
| Actual shared EEL/GUI/MIDI | **18,508** checks PASS |
| Movement runtime / Controller normal + ASAN/UBSAN | **1,204** checks each PASS |
| Native Movement persistence, malformed socket rejection, mapped physical takeover and legacy-owner refusal | **4** cases PASS |
| Strict native child ASAN/UBSAN gate, including Movement activation/ownership/persistence | functional exit **0**, diagnostic files **0** |
| Historical pending-command and EDIT races | both positive contracts **PASS** |
| Actual JACK + browser authoring/SAVE/LOAD/TEST | exit **0** |
| Expanded actual JACK matrix | exit **0** |
| Screenshot workflow | exit **0**, **179** actual PNGs, zero findings |

Commands use the prepared Python environment, not an interpreter missing the SMF
oracle dependencies:

```sh
source /tmp/mbmf-b-env.sh
scripts/headless-build.sh
"$TEST_PYTHON" scripts/combined-test.py --native --jack --browser chromium --timeout 240
MOVEMENT_BROWSER_AUTHOR=1 scripts/movement-jack-test.sh
SCREENSHOT_PYTHON="$TEST_PYTHON" scripts/screenshots.sh
```

The source EEL, native Controller, capture/SMF/overdub, independent instances,
queue-overload recovery, JACK sorting, three-chain compatibility, patch/portable,
bridge, browser and existing issue53 tests remain in the combined runner.
Legacy cross-source ONCE stays the explicitly separate shared/native XFAIL;
independent admission remains positively tested. No assertion/safety guard is removed.

## Real MIDI evidence

`jack-final.json` is the full combined run's actual JACK capture.
`jack-expanded.json` adds independent destinations, stepped interpolation, short
duration and SOFT restart; it also repeats browser authoring → native transaction →
SAVE/LOAD → browser TEST → actual output port capture. Events are
`[JACK_frame, offset, status, number, value]`; safety messages are retained.
They are not UI action echoes or simulated engine output.

- One-second ramps: exactly **11 / 26 / 51 / 101** changed-value events at
  10 / 25 / 50 / 100 Hz. Sample differences are exactly **4800 / 1920 / 960 / 480**.
  All start at CC0 and finish CC127 at sample +48000.
- Physical takeover: CC14=77 is emitted intact, with no following stale Movement.
- Same block: deferred PRESS emits CC18=0 at offset16; physical CC18=77 at
  offset220 wins, in the **same** actual JACK block, with no later automation.
- Replacement: CC15 outputs **25 → 102**, then remains102; the old source never
  regains ownership after the replacement's natural completion.
- Independent destinations: CH1/CC21 ramp continues across the STEP that starts
  CH2/CC22. The stepped source emits **0,25,114,13** at relative samples
  **0,13440,24960,48000**. The three-second ramp completes with76 events.
- A 10 ms source emits initial/final values exactly **480 samples** apart.
- SOFT restart from known physical CC100: next source emits100 initially and
  follows the confirmed parallel GLIDE/curve timeline, ending127 at one second.
- PHRASE notes and Movement coexist. Existing STOP ALL PHRASES ends the notes
  while automation continues; source STOP/PANIC and LOAD invalidate automation.
- Browser-authored CC17 has26 actual port events, starting0 and ending127.

## Performance and qualification boundary

`runtime.log` and the combined log contain measured 10/25/50/100 Hz runtime costs,
using the production C++ class and Controller tokens over1024 render blocks.
Normal mean costs in the combined run were0.34/0.39/0.84/0.62 µs. These are isolated
C++ wall measurements; they are not full JACK callback or ARM64 CPU qualification.

The expanded browser/JACK run reported **104,684 µs** maximum callback, **zero**
JACK XRUN notifications and **zero** output overflow at48 kHz /8192 frames.
The combined Movement fixture reported25,055 µs; an intermediate fixture14,406 µs.
The large maximum has not been attributed to a specific callback/source versus
Cloud scheduling or configuration work. Do not explain it away as environment
noise or extrapolate safety to small buffers. The actual port timestamp assertions
passed, but real V4 low-buffer latency and note-burst headroom remain unqualified.
A separate no-browser run is retained for comparison.

No physical Zynthian V4/ARM64, real Helix, Firefox/hardware synth or REAPER execution
qualification took place. ysfx is the existing pinned uninstrumented library;
ASAN instruments the native adapter, not all third-party engine internals.

## Screenshots and review

All manifest artifacts were viewed in ten contact sheets grouped by viewport;
the Movement editor was also inspected at original resolution. All five viewports
are covered, including small-screen empty/source/layer states and existing recovery
views. Small screens intentionally scroll vertically. The new editor preserves
black/gray/yellow curves and compact controls; source authoring has no hidden fake
transport or unsupported GATED control.

The stale pre-E screenshot metadata saying CONDUCTOR was unavailable was corrected
without changing the rendered PNGs. Manifest provenance retains the actual capture
revision. Links in the PR point directly to real committed PNGs.

## Failed preliminary runs, retained

- `combined-initial-python-environment.log`: exit1; Python system interpreter lacked
  `mido`. The prepared venv rerun passed; no test was skipped or weakened.
- `browser-initial-hidden-editor.log` / `browser-initial-preview-scope.log`: new
  preview code referenced an out-of-scope variable. Corrected before qualification.
- `browser-initial-menu-collapse.log`: hover opened MOVEMENTS, then click closed it.
  Mouse/touch click now deliberately opens the category.
- `persistence-initial-fixture-path.log`: fixture addressed the new Movement observation
  through the unrelated snapshots array. Fixture corrected; engine state was intact.
- `native-initial-fixture-action.log`: fixture used a nonexistent legacy-assignment
  API. It now uses actual serialized JSFX addresses and production LOAD.
- `screenshots-initial-indentation.log`: insertion matched the performance-only
  branch as well as the full capture path. Corrected, syntax-checked, committed.

## Phase verdict

**GO for review and the documented native ONE_SHOT/PRESS subset**, backed by
real production MIDI and browser evidence. **NO-GO for an unrestricted phase G**
until atomic combined PHRASE/Movement target admission and recorded-PHRASE CC
arbitration are explicitly closed, and real-time headroom is assessed for the
intended buffers. GATED/HOLD/JOIN/REVEAL, beats/bars, live source editing and REAPER
execution remain unsupported rather than approximated. This is not hardware
release approval; no phase G was begun.
