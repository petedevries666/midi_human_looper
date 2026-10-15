# Candidate verification: 10 October 2026

Integration branch `integration/studio-live-rc`, draft PR #44. No merge to main.
Fetched heads #30 `50b5db4`, #34 `243f10f`, #37 `2bec9f6`, #38 `6bc7b7b`,
#40 `361e183`, #41 `6408ba9`, #42 `cd140df`, #43 `57910e7` were each checked
with `git merge-base --is-ancestor` against this candidate. Remote main remained
`ab37a752693bf7d2d126a3a9e1ca1c863a5826a9`.

The complete command below passed twice. The final run used a native binary built
from committed `e21a9ed` (the subsequent installer preflight and diagnostic UI
changes do not change its MIDI execution). New preflight checks were separately
executed after modification; diagnostic UI checks were included in the final
browser run. Logs: `/workspace/scratch/v4-rc-regression.log` and
`/workspace/scratch/v4-rc-clean-regression.log` in the development workspace.

```sh
CHAIN_JACK_BLOCK=8192 PATH=/workspace/setup-tools/venv/bin:$PATH \
YSFX_SOURCE=/workspace/setup-tools/ysfx YSFX_BUILD=/workspace/setup-tools/ysfx/build \
JACK_INCLUDE=/workspace/scratch/midi-deps/root/usr/include \
JACKD=/workspace/scratch/midi-deps/root/usr/bin/jackd \
JACK_DRIVER_DIR=/workspace/scratch/midi-deps/root/usr/lib/x86_64-linux-gnu/jack \
HEADLESS_BINARY=/workspace/scratch/midi-headless-engine-v4-rc \
python3 scripts/combined-test.py --native --jack --browser chromium
```

Passed: 5,796 shared EEL/GUI/MIDI checks; 41 portable EEL MIDI parity checks at
44.1/48 kHz; native API tests including read-only monitoring/build identity;
Controller policy/host tests with sanitizers; Snapshot/persistence/authority and
SMF/bridge regressions; three independent native processors with real dummy-JACK
I/O and mocked Zynthian UI base; JACK graph/overload/timestamp-ordering tests;
all six Chromium workflows. Three-chain JACK uses 8192-frame cloud buffers; the
separate graph/ordering/overload probes use 512 frames. Neither is Pi latency proof.
Six reliability-reducer tests passed. Installer tests (three methods, including
non-mutating preflight and changed-adapter detection) passed separately.

JSFX SHA256 for the tested source:
`56cdf227af0defe2d6a86a39fc9460fbc80efd989942b347c481150d42fba4d8`.
The clean e21a9ed x86 test binary SHA256 was
`90cf0a0fdd6e3f265fdeb53cb9128890620e28d50a854af723c28c6b68251e49`.
Build the ARM candidate on the target/matching environment; this x86 binary is
not an install artifact for V4.

Cloud JACK reported memory-lock permission warnings. Tests use dummy/non-real-time
JACK, so success does not establish real-time priority/memory-lock behavior.
The earlier recording failure and its XRUN/gap evidence remain retained at
`/workspace/scratch/consolidation-rc-interrupted-recording.log`; root cause is
unresolved. No safety check, timeout or recording rejection was relaxed.

Physical test instructions: [V4](zynthian-v4-first-test.md) and
[REAPER](reaper-studio-live-acceptance.md). Stock Firefox, real REAPER APIs/RPP,
V4 routing/synths/Helix, low buffers, interrupted ports and power recovery remain
unrun. Pitch Bias is an inactive tested response helper, **not** completed
playback/UI/persistence: [next exact coding step](velocity-decay-pitch-bias-checkpoint.md).
