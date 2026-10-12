# Historical first-slice checkpoint — superseded for current status

See [current recovery implementation](../recovery-implementation.md). The evidence
below describes the earlier slice, not the current feature status.

# Recovery checkpoint — 2026-10-11

Draft PR #50: https://github.com/petedevries666/midi_human_looper/pull/50
Branch `fix/free-time-capture-origin`, based on PR #49 / `2068877`.
Engine implementation: `59a82e22d01fc5d3bb6d64999fa1533f54f5200f`.
Browser-test transaction fix: `f2a1389`; long native SMF regression: `1a78ae4`.
The verified binary reports the engine commit above. Later commits change tests
and documentation only. No branch was merged, installed or deployed remotely.

## Actually executed

```sh
PATH=/workspace/setup-tools/venv/bin:$PATH \
YSFX_SOURCE=/workspace/setup-tools/ysfx \
YSFX_BUILD=/workspace/setup-tools/ysfx/build \
JACK_INCLUDE=/workspace/scratch/midi-deps/root/usr/include \
HEADLESS_BINARY=$PWD/.build/midi-free-capture-verified \
JACKD=/workspace/scratch/midi-deps/root/usr/bin/jackd \
JACK_DRIVER_DIR=/workspace/scratch/midi-deps/root/usr/lib/x86_64-linux-gnu/jack \
CHAIN_JACK_BLOCK=8192 \
/workspace/setup-tools/venv/bin/python scripts/combined-test.py \
  --native --jack --browser chromium --timeout 240
```

Final result: **PASS selected combined regression suite**. Workspace transcript:
`/tmp/free-validated-combined.log`. Build used the existing pinned ysfx cache and
`scripts/headless-build.sh`; no package, JACK service or hardware changes.

| Evidence | Result / scope |
| --- | --- |
| Original native gate reproduction | Actual PR #49 ChainMode + JSFX: first attack immediately after REC at phase 12345 yields count 0, expected 1. `/tmp/free-gate-before.log`; corrected default path covered by committed free-capture tests |
| Original shared block-origin defect | Actual baseline JSFX: simultaneous second attack at origin 17 stored at 17, expected 0. `/tmp/free-before.log` |
| Shared EEL/GUI/MIDI | 7,704 checks pass, including 702 focused free-capture checks, callback interruption, no external transport and held-note finish |
| Exported SMF | 18 old grid fixtures and 36 shared/native free fixtures pass source-memory → production-writer → actual delta-tick comparisons |
| Native API | >4-second ARMED wait; first-note transition; LOOP/ONCE/HOLD mode retention; rests/channels/velocity; save/load; 8-second ONCE import without grid restriction passes |
| Actual dummy JACK | Three optional-grid processors pass; single default-free processor sends identical chronologically ordered streams to three channel-aware virtual receivers; LOOP/ONCE/HOLD/short tap/release/STOP/transport/removal cleanup passes |
| Controller / Snapshot / persistence | Existing normal and ASAN controller suites, native ownership, morphing, portable contract, atomic project activation/restart, bridge and patch tests pass |
| Chromium | Existing ten browser suites pass, including sliders/curves, transactional editing, source isolation, source MIDI download/upload/CLEAR and native held release |
| Browser failure investigated | Earlier committed-build run timed out at TEST TAP. Native commit observation preceded popup-response rendering. Test now waits for actual dialog closure and clicks its real disclosure; musical assertions remain. Standalone rerun and final combined run pass |
| ARM64 / REAPER / Zynthian / Helix | **Not executed on physical hardware.** Dummy JACK at 8192 frames is functional evidence, not low-latency/XRUN certification |
| New screenshots | None: this slice changes no web presentation. Existing screenshots are baseline evidence, not a claim of restored visual parity |

## Remaining implementation, not merely hardware validation

- ARP ENABLED is missing from web module parameters; ARP modes need full actual
  native routing/output qualification. Next coding step: append existing kind 3
  to ARP descriptor parameters, preserve the first four row identities, update
  the shared row adapter/generator and test enable/mode/gate/bypass/persistence.
- Free-time overdub with simultaneous playback, capacity exhaustion with explicit
  failure reporting, variable-length LOOP layers and sustained-note boundaries
  need further integration qualification. No silent-truncation safety claim.
- Add per-phrase authoritative recording/playing state, correct stale grid-labelled
  browser text and generate real ARMED/RECORDING/FINISHED screenshots.
- Contextual expression assignment, safe legacy ownership migration, slider curve
  previews and screenshot-led visual fidelity remain unimplemented in this slice.
- Cross-version rollback after saving a new free-time project is not qualified:
  PR #49's old grid can reject its different duration. Preserve the pre-update
  project revision and export new takes; never truncate or overwrite data to force
  old runtime activation. The existing updater is not certified for that case.

Continue from this branch/PR #50, then create a focused stacked ARP/editor repair
PR with actual native MIDI and browser tests plus required inspected screenshot
artifacts. Do not merge, deploy or reinterpret this checkpoint as a finished
musical/UI release candidate. See `mbmf-jsfx-native-parity.md` and
`../free-time-recording-recovery.md` for the source-backed audit and physical tests.
