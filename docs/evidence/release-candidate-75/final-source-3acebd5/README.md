# Final native-source LIVE rerun (3acebd5)

Actual private dummy JACK, x86_64 Cloud, 48 kHz, 12 seconds per case. Browser closed, no other test/build job in measured windows. Three preexisting standalone fixtures retained; environment recorded. Engine binary is the clean build identified by commit.txt and binary.sha256. No hardware qualification.

**Combined regression exit 0; LIVE matrix exit 1.** These are separate gates. The final PR comment publishes the complete combined rerun on the later evidence-only delivered commit. Native execution source is unchanged.

| Frames | Profile | PHRASE max / MOVEMENT min–max | Notes / CC per second | CPU p95/p99/max ms | Wall p95/p99/max ms | CPU/wall overruns | XRUN | Overflow / instance refused |
|---|---|---|---|---|---|---|---|---|
| 512 | LIVE_LIGHT | 1 / 1–1 | 2.00 / 24.49 | 0.116/0.207/0.469 | 0.122/0.243/2.488 | 0/0 | 6 | 0 / 0 |
| 512 | LIVE_NORMAL | 3 / 1–2 | 12.00 / 45.65 | 0.116/0.443/4.391 | 0.122/0.445/4.410 | 0/0 | 0 | 0 / 0 |
| 512 | STRESS | 12 / 7–8 | 719.89 / 742.39 | 0.636/1.235/2.988 | 0.637/1.237/3.849 | 0/0 | 3 | 0 / 1 |
| 256 | LIVE_LIGHT | 1 / 1–1 | 2.00 / 22.08 | 0.158/1.005/228.221 | 0.178/1.007/373.065 | 6/6 | 67 | 0 / 0 |
| 256 | LIVE_NORMAL | 3 / 1–2 | 12.25 / 45.82 | 0.085/0.215/1.750 | 0.092/0.228/3.165 | 0/0 | 0 | 0 / 0 |
| 256 | STRESS | 12 / 7–8 | 713.61 / 734.61 | 0.635/1.215/42.849 | 0.646/1.239/43.389 | 3/3 | 31 | 0 / 1 |

Configured LIGHT = 1 PHRASE + 1 MOVEMENT at25 Hz; NORMAL = 3 +2 at25 Hz, STEP changes and physical expression takeover; STRESS = **12 PHRASE sources** +8 MOVEMENTS at100 Hz and note bursts. The original report’s prose “8 PHRASES” was an error; actual table, configuration and raw source counts are authoritative. Source budget remains12, unchanged. One explicit bounded instance refusal occurs in each STRESS run, no MIDI output overflow.

NORMAL has zero XRUN/deadline/order failures in these two short windows. This does not override the previous NORMAL/256 capture failure or qualify sustained normal use. LIGHT/512 XRUN6, STRESS/512 XRUN3, LIGHT/256 XRUN67, STRESS/256 XRUN31 remain. No averages hide maxima.

LIGHT/256 peak: sample237824, JACKframe287488, **228.221 ms thread CPU /373.065 ms wall**, one active MOVEMENT, **zero active PHRASE instances at this callback**, zero input events/commands/pending output, one CC emitted. Stage `movement_cc_actions` brackets228.080 ms CPU/372.917 ms wall; EEL27.379 µs. User181716 µs +system46506 µs agree with the large CPU measurement; no minor/major fault. Unlike the earlier99.753 ms ingress/recovery peak, this peak is in a different bracket. Exact function/root cause remains unknown. Do not claim either “all Cloud scheduling” or “proven MOVEMENT algorithm defect”.

STRESS/256 peak:42.849 ms CPU /43.389 ms wall,42.828 ms CPU inside EEL/PHRASE/Transformer bracket,12 PHRASE instances and7 MOVEMENTS, no command/input at this callback. Receiver timestamp assertion fails: event10875 sees frame478208 offset112 NoteOn61 before same frame offset80 CC21/122. Native per-callback order counter remains0; no receiver callback ordinal exists. This remains a blocker, not a reason to reorder/suppress capture.

Combined source-3acebd5 result: native ASAN functional exit0 and diagnostics0;18508 EEL/GUI/MIDI checks;6824 ownership host checks plus6698 in the channel gate;704 PHRASE output checks;Controller162709 policy/579 adapter checks normal+sanitized;all selected JACK/browser/update/Webconf/AZ gates PASS. Legacy ONCE cross-source XFAIL remains explicit (shared/native observations), not a new PASS.

Commands: `scripts/headless-build.sh`; `python scripts/combined-test.py --native --jack --browser chromium --web-access --timeout 240`; `MOVEMENT_RT_TEST=tests/movement_live_profiles.py scripts/movement-realtime-test.sh --output /tmp/mbmf-75-delivered/live --buffers 512,256 --seconds 12`. Use the prepared environment in AGENTS.md. Raw callback CSVs are losslessly gzipped; MIDI and native/JACK logs are retained.

**NO-GO main merge/release. GO only for code review and further controlled diagnostics.** No deployed Pi, no phaseG, no OS/JACK/LUMAZ changes.
