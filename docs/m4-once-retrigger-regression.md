# M4 ONCE retrigger regression

## Root cause and complete execution path

The actual mode mapping is **0 LOOP, 1 ONCE, 2 HOLD** (catalog, Conductor
`playMode` compiler and EEL dispatcher agree). The reported mode-2 instances are
HOLD, even if the intended selection was ONCE. Their `independent` flag describes
admission policy, not play mode. Record the effective Conductor override as well
as the source mode when reproducing.

1. Native Phraser PLAY / learned MIDI enter `process_phrase_trigger` through the
   existing chain/source dispatcher. Conductor compiles the block's effective mode,
   temporarily applies its velocity/time overrides, and calls
   `phrase_admit_independent`, which uses the same admission function.
2. Admission reserves one of twelve voice slots, assigns a serial/generation,
   captures instrument identities/output policy, and snapshots repeat gain and
   time factor. Native mute group zero does not call a choke path. Direct HOLD
   replaces its prior direct occurrence; independent Conductor owners remain
   subject to the existing cancellation/release policy. LOOP keeps its toggle.
3. `phrase_voice_repeats` makes ONCE finite, independent LOOP repeating and native
   HOLD non-repeating. `phrase_render_voice` renders source events;
   `phrase_render_span` intentionally ignores recorded HOLD Offs. HOLD renders its
   source once then remains active until replacement/STOP/Conductor cancellation.
4. `send_once_to_instruments` reserves an attack record and applies existing
   filters/velocity/output routing. `route_emit_note` increments logical ownership.
   **Regression:** contract v2 returned success without emitting Note On whenever
   the physical channel/pitch already had another owner. It still captured output
   ownership, so diagnostics showed admitted instances and no rejection/overflow,
   but repeated same-pitch phrases could be completely inaudible.
5. Native `headless/engine.cpp` normally drains these EEL MIDI events into its
   bounded, timestamp-sorted output batch. Once ECHOCITY has been configured, it
   instead consumes the native source journal and routes notes through
   `echocity::Runtime`; its dry `Outputs` ledger independently suppressed repeated
   attacks. Both routes now emit repeated phrase On messages without inserting an
   Off before them. Existing live duplicate coalescing and delayed-echo explicit
   Off/On retriggers remain unchanged.
6. Matching source Offs release FIFO records using captured destination/pitch.
   Only the final physical owner emits Off. Natural ONCE completion calls
   `instance_stop_voice`, releases remaining records/pedals/transforms, closes
   REVEAL and marks the slot inactive. The ECHOCITY journal records EndInstance
   rather than cancellation so existing delayed tails may finish. No host rewrite
   or change to MOVEMENT/private marker routing is needed.

The lifecycle exclusion `native_phrase_contract && phrase_voice_mode(vi)==2` is
**intentional HOLD retention**, not an ONCE cleanup bug. There is no alternative
natural-completion mechanism for latched HOLD: replacement, targeted STOP,
Conductor cancellation or panic release it. The reported retained mode-2 rows
alone are not evidence of a leak. Actual mode-1 natural completion, missing-Off
cleanup and full-capacity reuse are covered by executable regressions. The source
file remains byte-identical; the focused changes apply only to generated native
EEL, consistent with the frozen REAPER policy.

## Velocity decay

Previously native VEL DECAY accepted **20–100%**, step **1%**, default **80%**.
It now accepts **20–200%**, with the same step/default. ONCE repeat gain already
existed but was inaudible when its Note On was suppressed. For source velocity 40:

| Ratio | Successive overlapping triggers |
| --- | --- |
| 50% | 40, 20, 10 |
| 100% | 40, 40, 40 |
| 150% | 40, 60, 90 |
| 200% | 40, 80, 127 |

Each voice keeps its trigger-time gain; existing direct/independent repeat/reset
histories remain unchanged. Native ratios above one bound the exponent before
`pow` to prevent overflow on long sessions; final sounding velocity still clamps
to MIDI 1–127. Calculations at or below 100% remain exactly the existing path.
This does not activate the separate, unfinished pitch-bias feature. Native catalog
bounds feed Conductor validation, charge, Controllers and Snapshots. Phraser's
slider now reaches 200%; legacy REAPER bounds and patch schema are unchanged.

## Deterministic validation

Run with the pinned ysfx checkout:

```sh
scripts/once-retrigger-test.sh
scripts/echocity-native-test.sh
scripts/velocity-native-test.sh
scripts/movement-test.sh
scripts/echocity-core-test.sh
```

The ONCE test executes the generated production EEL in ysfx and the actual native
Conductor compiler, not a simulated phrase engine. It checks actual channel-3
MIDI packets, both trigger paths, identical pitches inside/across phrases, ratios
50/100/150/200%, final-only releases, targeted STOP, natural completion, missing
recorded Off, twelve-slot saturation/refusal/reuse, LOOP toggle and HOLD retention/
replacement/cancellation. It also exercises the native ECHOCITY terminal ledger.
The combined runner includes it. The unchanged pre-fix native source fails its
second same-pitch attack assertion; the repaired source passes 397 checks.

Additional passing checks: native EEL source journal 369; terminal ECHOCITY runtime
93; native velocity 22; MOVEMENT 6250; delayed-note foundation 8139; ECHOCITY core
12208; descriptor registry 7. Exact legacy suites/results are listed in the PR.

### Environment limitations / web evidence

`scripts/screenshots.sh` was attempted against the real application. This Work
container refuses AF_UNIX socket bind with `EPERM`, in both `/tmp` and the
workspace. The native HTTP fixture therefore cannot start (`engine socket failed
to start`). No successful screenshots or visual inspection are claimed; existing
PNGs/manifest have not been replaced with stale or fabricated evidence. All five
required viewport captures and inspection remain required before marking the PR
ready. Socket-dependent HTTP, JACK and hardware suites are not qualified here.

## Explicit Zynthian validation (manual, no automatic deployment)

1. Use a separate test checkout/build; keep the live checkout and user patches
   untouched. Run the focused scripts above. Build the native binary with the
   matching generated source, then start a private test session.
2. Connect one instrument to channel 3. Disable MONO/ARP and other Transformers.
   Load a 2–4 second phrase with a sustained note plus several later notes. Select
   **ONCE**, mute group **0**, VEL DECAY **100%**, TIME DECAY **1**. Confirm telemetry
   reports effective **mode 1**, `nativePhraseContract=2`.
3. Trigger the same phrase from Phraser several times before it ends. Capture MIDI
   at the synth input: every trigger must produce Note On, including identical
   pitches; the first instance's Off must not release a surviving owner. Listen
   for each attack and the overlapping later phrase notes.
4. Repeat from Conductor with a block explicitly overridden to ONCE, then INHERIT
   from an ONCE source. Release the pedal between presses. Check new independent
   IDs and mode 1. Repeat with ECHOCITY absent, configured/bypassed and enabled.
5. Try decay 50%, 100%, 150%, 200%: verify the table above using source velocity 40.
   Adjust while playing and verify existing voices keep their captured gain.
   Save/reload and verify 200% survives. Check Controller, Snapshot and Conductor
   charge endpoints reach 200%, with final output never exceeding velocity 127.
6. Wait beyond the final phrase length: no ONCE instances/attack reservations/
   output ownership may remain. Trigger again. Repeat until the twelve-slot limit,
   verify explicit refusal preserves survivors, wait, then reuse all slots.
7. Check LOOP start/stop; HOLD stays active beyond source length, ignores recorded
   Offs, direct retrigger replaces it and STOP clears it. Check Conductor release/
   cancellation, a nonzero mute group, REVEAL volume restoration and MOVEMENT CC
   output. STOP one of two identical-pitch owners and verify the survivor remains.
8. Run `scripts/screenshots.sh` in a socket-capable environment; visually inspect
   every generated view at 320×240, 800×480, 1366×768, 1440×900 and 1904×1032 and
   commit the real PNGs/manifest. Verify Phraser and Conductor display/edit 200%.

MIDI 1.0 has no per-note instance identity on one channel/pitch. This repair emits
all phrase attacks and preserves logical ownership without destructive synthetic
Off/On pairs. Whether the connected synth stacks or restarts identical-pitch voices
is synth-specific and must be checked on the actual Zynthian instrument; the fix
does not silently remap channels or claim universal same-pitch synth polyphony.

Legacy source suites also passed: instance ownership 6698, phrase output 704,
M0 playback 114, M0 ONCE 17, M0 HOLD 51 and M0 entries 100. Additional legacy
suites are not green on the unchanged base source: `--m1-groups` fails at
`M1 grouped mono source cleanly refused before attack`; `--m2-gestures` fails at
`M2 TEST HOLD actual selected STEP MIDI`. These ran against the byte-identical
base JSFX (not the generated native variant) and are disclosed rather than fixed
outside this regression's scope. The full combined suite was not run because its
HTTP/socket-dependent startup is unavailable in this environment.
