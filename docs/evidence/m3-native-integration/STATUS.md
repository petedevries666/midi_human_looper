# M3 integration checkpoint

## Scope and immutable starting points

- User task: GitHub issue #84
- Musical source: PR #82, branch `feat/conductor-reveal`, base HEAD `78dcf8e6a787b0de6a82c9fd3123354ad40086c0`
- Routing source: PR #83, branch `fix/mbmf-native-midi-feedback-guard`, source HEAD `74d7a6676e042bd50d80ef7ea48e7cabec671b28`
- Integration: PR #85, branch `integration/m3-mbmf-native-routing`, based **only** on #82. Exactly six routing source files incorporated; no musical runtime binary/JSFX/Webconf source overwritten.
- Do not merge main, rewrite source PRs, or install on user's Pi until physical qualification.

## Completed in this working session

1. GitHub ancestry verified: #82 is 51 commits ahead of #67, without missing ancestor; #83 and #82 had diverged.
2. Created integration branch at exact #82 SHA. Added the six net-new/modified #83 files. Compare confirms no commits removed from musical parent.
3. Opened draft PR #85 against `feat/conductor-reveal`.
4. Safety hardening: require explicit physical opt-in list before admitting virtual MB input; no opt-in now **fails closed**, rather than silently exposing a path that caused hardware feedback.
5. Added virtual-source quarantine before restoring any saved physical keyboard bypass routes. On failed quarantine, preserve physical isolation instead of restoring a potentially cyclic matrix.
6. Added change-of-keyboard-selection restoration to avoid stale native exclusions.
7. Updated original native firewall tests to isolate their own opt-in mocks, while exclusive opt-in and fail-closed behavior are tested separately.
8. Extended exclusive policy tests for native matrix note propagation, internal sequencer return, 2 new quarantine/restore behaviors, configuration retarget and idempotent refresh.
9. Added focused GitHub Actions Python test workflow and expanded it to installer/legacy routing suites. Final green Actions run 38789501210 completed with 67 / 67 tests passing on Ubuntu/Python 3.11 (4 + 7 + 14 + 30 + 7 + 5).
10. The runner initially detected a genuine fail-closed bug on malformed JSON (`requested` was unbound in the catch path). It was fixed, and tests were re-run green. The failure log is retained in Actions run 38789108763.
11. Added `scripts/zynthian-m3-safe-smoke.py`, an optional bounded native-output MIDI/XRUN checker with emergency JACK disconnect for hardware acceptance. Python source compilation passed in CI.

## Risks and current status

**Not physically validated.** Existing hardware evidence is unchanged:
- With MB native virtual source connected: +38103 MIDI output events, +50 lateBlocks in 2 seconds.
- Disconnecting only MB -> dev2 gave +0/+0.
- Previous #83 source guard alone passed idle but REC still ERROR/chopped.
- With MB output disconnected, REC + FINISH succeeded and PLAY advanced silently; keyboard remained audible due native direct hardware bypass.

A successful GitHub CI simulated matrix is **not** a real ZynMidiRouter/Oram qualification. Readback setter wrappers may behave differently on hardware; test on user's installed Oram before merge. Precise source of REC loop remains unproven; `zynsmf` internal return is a plausible additional path, NOT a confirmed culprit. Installed `install.json` has not been edited and the Pi is unchanged.

## Tests

Focused test scripts targeted by CI:
```sh
python3 tests/test_zynthian_channel_source.py -v
python3 tests/test_zynthian_feedback_guard.py -v
python3 tests/test_zynthian_exclusive_input.py -v
```

All 3 router test modules use stdlib-only mocked native lib API. **GitHub Actions run 38789501210 succeeded** at commit `e0a4cd8c5eca4978d259cc28fe69ea4f431e3fbb`: 25 focused native routing tests, 30 managed installer tests, and 12 legacy adapter/routing tests = **67 PASS**. The compile step also covered the hardware smoke monitor. Source tests run on GitHub-hosted x86 Ubuntu, not a Pi.

Musical engine regression suites from #79-#82 were not reexecuted here: the integrated diff does not touch engine source or its tests, but an integrated-HEAD qualification is still required before merge.

## Rollout protocol

1. Save Zynthian snapshot, make `install.json` backup, leave manual JACK MB virtual output disconnected.
2. Stage integration branch at immutable approved SHA. Run `python3 .../zynthian/install.py --binary "$BIN" --native-channel-routing --check`. A failure must end procedure, with no writes.
3. Review intended config. Enable only exact approved `"exclusive_midi_input_ports": ["system:midi_capture_1"]` on existing `install.json`; preserve all other keys and verify keyboard index in JACK. For a non-matching/missing input, do not guess a replacement port.
4. Run managed installer for router helper (`--native-channel-routing` only; no adapter upgrade), restart only Zynthian UI when user is ready.
5. Check `mbh_1:midi_out -> ZynMidiRouter:dev2_in` only (no direct synth), idle MIDI/lateBlocks 2s +0/+0, keyboard clean note on/off, short REC/FINISH/PLAY without ERROR, channel filtering, CC7/conductor, and VideoTrigger.
6. Safety: on storm/error immediately run `jack_disconnect mbh_1:midi_out ZynMidiRouter:dev2_in` and stop testing. User controls any rollback; no automatic merge.

## Next checks

- Run real Python tests and review failures on a runner once available.
- Check pinned Oram native route getters/setters and snapshot/chain recreation behavior against actual V4 runtime.
- Capture device qualification evidence, then consider merging only with explicit approval.
