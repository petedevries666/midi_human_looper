# M0 native musical playback contract 2

Draft #79, stacked on #78 / #76. No merge, installation or hardware validation.
The original issue-54 working checkout is untouched. #77 remains separate.

## Musical behavior

| Entry | ONCE | LOOP | HOLD |
| --- | --- | --- | --- |
| Native direct Web / learned MIDI / legacy switch | Independent occurrences, including across sources | PRESS starts, next PRESS stops, next restarts | Play source once, retain notes, next PRESS cuts direct occurrence and restarts; RELEASE ignored |
| CONDUCTOR independent admission | Existing NEW INSTANCE policy | Independent repeating instance | Independent latched instance; RELEASE ignored |

HOLD here is **PLAY MODE**, not long-press admission. Its approved meaning is the
user's 15 October 2026 decision. An explicit source STOP releases all instances
of that source, including CONDUCTOR, while retaining unrelated and live owners.
Direct HOLD retrigger replaces only its direct occurrence, not independent
CONDUCTOR owners. STOP/PANIC remains the way to end latched notes.

No schema or stored MIDI changes. Native ChainMode sets runtime-only
`native_phrase_contract=2`; the shared EEL defaults to zero for frozen REAPER
execution. No `@gfx` or REAPER feature development. The separate pre-M0 HOLD
fixture explicitly opts into contract zero; new M0 tests use the real native
constructor and prove the new behavior, rather than rewriting legacy assertions.
The API reports `nativePhraseContract:2`, `nativeHeldRelease:false`. The Web
editor enables latched HOLD based on this capability, uses ordinary accessible
click/keyboard activation, and never labels the active HOLD button as STOP.

LOOP uses one DSP dispatcher for native commands, learned triggers and legacy
switches. A mode edit no longer pre-arms a native LOOP: a real JACK test exposed
that the new toggle otherwise stopped a dormant armed source on its first PRESS.
Mode selection now only selects the mode. This correction is native-only.

## Safety and evidence

- Twelve ONCE slots unchanged; thirteenth admission emits neither attack nor
  destructive release, and reports capacity rejection.
- Unsafe independent mono/ARP overlap remains refused. No new support is claimed.
- Existing emitted-destination ownership remains authoritative. Same pitch/channel
  across two sources and a held physical note is tested: phrase endings do not
  release the physical owner.
- No new scheduler, allocation, I/O or JSON in DSP. Bounded existing 16-command
  mailbox now also carries direct LOOP commands; full-mailbox refusal propagates.
- M0 tests: 114 LOOP, 17 ONCE, 51 HOLD, 56 shared-entry checks, all exit 0.
- Full shared host regression: 18,508 checks, exit 0. Recording/SMF conversion
  fixtures and API free capture/overdub/cancel/save-load remain separate gates.
- Native API CONDUCTOR tests: 3 passed. Browser: real native pointer, keyboard,
  learned MIDI, ignored RELEASE, retrigger, STOP/PANIC passed.
- Actual JACK source/engine/sink test at 48 kHz, 8192 frames: expected attacks
  `60,62,64,64,65`; HOLD Off-before-On and LOOP Off observed. PANIC receiver CC
  cleanup and native zero instances checked; output overflow zero. Events are
  checked in received order, never sorted to make them pass.
- The full Chromium screenshot workflow passed at all five sizes; all 184
  manifest views were visually reviewed in viewport contact sheets. Layout is
  unchanged; narrow screens scroll vertically. Static views do not establish
  continuously repainting live qualification. The screenshot run preceded the
  last native-only mode-edit correction; its manifest truthfully records a dirty
  build. No final-SHA or hardware screenshot claim is made.

Raw logs: `docs/evidence/m0/`. Early failed JACK assertion is retained separately:
first PLAY remained STOPPED, second PLAY became PLAYING due to implicit mode
arming. The final test asserts both real MIDI and native state. An initial manual
full-host invocation omitted its required historical JSFX argument (exit 139),
then passed a nonexistent baseline file (exit 1); neither was an engine runtime
qualification. The correct baseline is `git show fa200857:midi_human_looper.jsfx`.

## Reproduce in prepared Cloud checkout

```sh
source /tmp/mbmf-b-env.sh # local prepared cache paths, not a device command
scripts/headless-build.sh
scripts/m0-playback-test.sh
PYTHONPATH=headless:tests "$TEST_PYTHON" tests/test_native_hold_browser.py
PYTHONPATH=headless:tests "$TEST_PYTHON" tests/test_conductor_execution_native.py
PYTHONPATH=headless:tests "$TEST_PYTHON" tests/test_native_free_capture.py
```

`tests/run_host_tests.sh` supplies the historical baseline and runs source/SMF
fixtures. `scripts/headless-test.sh` with `RUN_JACK_TESTS=1` includes the new
private JACK fixture. `scripts/combined-test.py --native --jack --browser chromium`
includes all focused M0 gates, preserving existing global tests/failure reporting.

## Five-minute musician check after explicit build review

Back up the patch/snapshot and record installed SHA; keep the prior working
runtime and updater rollback. Do not install this unreviewed draft automatically.
1. Use two ONCE phrases with different notes, then a shared pitch. Trigger both;
   the second must not cut the first or a physically held keyboard note.
2. Select LOOP without pressing PLAY. Play another phrase: LOOP stays stopped.
   PRESS LOOP three times: start / stop / start; browser state follows.
3. Select HOLD on a short two-note phrase. One PRESS sustains both notes beyond
   the recorded Note Offs; release does nothing. PRESS again cuts then restarts.
4. Explicit STOP that source; unrelated phrase and live keyboard keep sounding.
5. Save/load stopped, repeat, then PANIC; verify no sounding notes. Listen for
   synth-specific sustain behavior. No physical V4/Helix qualification yet.

M1 MUTE GROUP, gesture layers, JOIN/REVEAL, FECK and full release qualification
remain later milestones. Cloud/JACK timing risks from #76/#77 are not resolved
by these musical tests. Optional legacy grid capture is not newly qualified here.
