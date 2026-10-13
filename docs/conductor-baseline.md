# CONDUCTOR PR A: executable baseline before instance ownership changes

Base: PR #50, `25fcb1e458ffdce7286ff4c60cd4546d586e19a4`.
Contract: PR #55, `d63431a7dda54ce69317ad29e0ddded89ee42404`,
`docs/movement-phrase-conductor-master-spec.md`.
This PR changes tests and documentation only. It does not implement CONDUCTOR,
change musical behavior, merge prerequisites, install software, or touch hardware.
Issue #54's independent uncommitted work remains in the original checkout.

## Reproduced MIDI failures

These are **three unmet future contracts**, not three successful features.
The executable runs the complete production JSFX in pinned ysfx/WDL EEL2;
the first and third cases inject actual Note On/Off footswitch messages into
the existing Smart Switch dispatcher. The saturation case uses the same phrase
trigger path used by the engine. No alternate renderer or mocked scheduler.

| Case | Input / precondition | Actual output | Required foundation in PR B |
|---|---|---|---|
| `ONCE_CROSS_SOURCE_CHOKE` | PRESS starts source 1 (48); RELEASE; PRESS starts source 2 (72), before source 1's recorded Off | `[128,48,0]`, then `[144,72,83]`; only one voice remains | Independent admission context must preserve the preceding instance unless an explicit lifecycle/group/STOP rule ends it |
| `VOICE_EXHAUSTION_GLOBAL_RELEASE` | Twelve simultaneous instances of source 1; request a thirteenth | `[128,48,0]`, then `[144,48,91]`; voices drop from 12 to 1 | Bounded rejection or targeted eviction, never a global release disguised as single-voice recycling |
| `CHOKE_RELEASES_LIVE_OWNER` | Physical Note On 48 remains held; phrase 1 also plays 48; switch advances to phrase 2 | `[128,48,0]` despite one live output owner still present | Cleanup must respect surviving physical/instance ownership at the actual output destination |

`tests/test_conductor_native_baseline.py` also reproduces the first case through
actual production HTTP commands, native callback, source SMF import and
authoritative per-phrase observations. It checks native PANIC and byte-identical
source exports after patch SAVE/LOAD. Its state observation complements the raw
MIDI evidence from EEL; it is not a claim of JACK or physical synth observation.

The current legacy ONCE cross-source choke is deliberately documented rather
than removed here. PR B must separate old trigger semantics from the new
independent instance admission policy. The thirteenth-voice implementation does
not match its comment about recycling the oldest voice: it clears every voice.

### Expected-failure policy

Baseline mode checks the exact current symptoms and prints **XFAIL**. Unexpected
fixture failures exit nonzero. An **XPASS also fails**: a corrected behavior must
be promoted to a normal passing regression rather than silently keeping a stale
expected-failure marker. `--strict` exits 1 for the unmet contracts.

The combined runner explicitly includes these baseline cases for `--native`.
An exit-zero baseline means its reproductions completed, **not that the new
CONDUCTOR contracts pass**. PR B's gate must resolve/promote its affected cases;
it must not weaken the contract or merely remove the XFAIL output.

For the legacy cross-source choke specifically, preserve a named compatibility
test for the old admission policy and add an independent-admission regression
for the new CONDUCTOR context. Do not make every historical ONCE trigger
independent just to obtain XPASS. Physical-owner corruption and global capacity
cleanup must be corrected without changing authored source modes or decay rules.

## Compatibility fixtures

`tests/fixtures/conductor/legacy-source.json` retains overlapping same-pitch
notes, separate channels, velocities, explicit Note Off velocities and a
velocity-zero Note On. The tests preserve authored source timing and independent
phrase slots through portable native/REAPER materialization at 44.1/48/96 kHz.
An independent mido parser checks actual exported SMF ticks, including attack at
tick zero. Unknown project fields are rejected without mutation; source data
persists while playhead/trigger/retrigger counters are excluded.

`legacy-parameters.json` freezes the existing 25 parameter identities, kinds,
ranges, defaults and normalization semantics. It permits future additional
parameters but does not allow silently changing older meanings. An intentional
future change requires an explicit version/migration and revised fixtures.
Existing bank/schema migration, controllers, snapshots, native recording and
JACK lifecycle suites remain required; these fixtures do not replace them.

## Capacity audit and measurements

Runtime-derived values and wall-clock measurements are recorded in
`docs/evidence/conductor-a-baseline.json`. They cover 24 combinations:
44.1/48/96 kHz × 128/256/512/8192 frames × 1/12 held ONCE voices,
64 processing blocks each after four warm-up blocks. Compilation, GUI and
fixture writes are excluded from the measured interval. The workload is one
POLY instrument and two source events with a long held note; it does **not**
characterize dense MIDI, eight destinations, ARP, callback allocation, or
worst-case modulation work. No flaky timing threshold is made a test assertion.

Current capacities, not approved future product limits:

| Storage / execution | Existing limit |
|---|---|
| Source phrase pool | 16 slots (`LAYERS` means source slots, not future conductor layers) |
| Source events | 2,048 five-cell records per phrase |
| ONCE voices | 12 |
| Instruments / Transformer slots | 8 / 6 per Instrument |
| Smart Switch slots / sequence positions | 16 / 64 |
| EEL expression curve / native Controller curve | 6 / 16 points |
| Native Controller targets / core mappings | 512 / 64 |
| Exposed native Controller sources / bindings | 16 / 32 |
| Schema-7 serialized payload | 171,649 cells; runtime memory is separate |

The normal 12-voice benchmark is intentionally below saturation; the separate
saturation reproduction demonstrates the unsafe behavior at its boundary.
Cloud median/p95/max values are descriptive measurements, not Pi deadlines or
hardware qualification. The JSON includes machine, source/harness hashes and
commit provenance. Held-note timings alone cannot justify an update frequency
or new layer/instance cap.

**Proposal for PR B, requiring further measurement:** keep runtime instance
admission bounded, reserve ownership capacity before emitting an attack, and
reject an admission explicitly if its eventual releases cannot be represented.
Do not grow storage per callback. With 2,048 paired source events, as many as
1,024 source attacks may overlap per voice; 12 voices × 8 destinations can imply
98,304 routed attack owners before accounting for live input. This is a
conservative sizing calculation, not a recommended pool allocation or approved
limit. Measure dense fan-out and compare bounded sparse records versus grouped
source/destination ownership before fixing the representation. Preserve FIFO
pairing/generations for repeated pitches and surviving-owner aggregation.

## Decisions and dependencies

- Q1 **resolved** in PR #55: FECK retains STEP; next PRESS replays it from the
  start; following PRESS resumes normal traversal. PR A records that contract,
  but does not claim that new FECK cursor behavior exists in the legacy engine.
- Q2 non-LOOP JOIN beyond duration and Q4 held-note PAUSE/RESUME remain unresolved.
- Q3 numerical caps/handover durations remain proposals pending measurement and
  review; existing capacities are not user approval.
- PR #45 contains relevant gesture work but also schema-8/portable-v2 changes;
  do not merge it wholesale into this schema-7 base.
- PR #28 provides scheduler/owner-generation precedents with restricted
  continuation; it is not an arbitrary pipeline or a required full merge.
- Native Controller/Snapshot execution parity with REAPER remains incomplete.
  Identical portable source conversion is not proof of ownership policy parity.

## Execute

Reuse the prepared Cloud toolchain; do not run Zynthian installers:

```sh
export YSFX_SOURCE=/workspace/setup-tools/ysfx
export YSFX_BUILD="$YSFX_SOURCE/build"
export JACK_INCLUDE=/workspace/scratch/midi-deps/root/usr/include
export TEST_PYTHON=/workspace/setup-tools/venv/bin/python
export HEADLESS_BINARY="$PWD/.build/midi-headless-engine"
scripts/headless-build.sh
scripts/conductor-baseline.sh
"$TEST_PYTHON" tests/test_conductor_legacy_contract.py
"$TEST_PYTHON" tests/test_conductor_native_baseline.py
# Expected exit 1, with the known contract failures still visible:
scripts/conductor-baseline.sh --strict
"$TEST_PYTHON" tests/test_conductor_native_baseline.py --strict
```

Full regression, using a private dummy JACK only in Cloud:

```sh
export JACKD=/workspace/scratch/midi-deps/root/usr/bin/jackd
export JACK_DRIVER_DIR=/workspace/scratch/midi-deps/root/usr/lib/x86_64-linux-gnu/jack
CHAIN_JACK_BLOCK=8192 "$TEST_PYTHON" scripts/combined-test.py \
  --native --jack --browser chromium --timeout 240
```

Physical qualification remains pending: real REAPER APIs, Oram routing,
Firefox/Helix, physical sustain and same-pitch receiver behavior, playable buffer
deadlines/XRUNs. No deployment or hardware changes are part of PR A.

## Executed results and unresolved regression gate

- New compatibility suite: **5 tests pass**.
- Production EEL baseline: **85 checks complete, 3 explicit XFAIL contracts**.
  Strict execution was actually checked to exit **1**, as intended.
- Native HTTP baseline: first/second admission, PANIC and unchanged source
  SAVE/LOAD pass; the cross-source contract remains XFAIL. Strict exits **1**.
- Existing shared EEL/GUI/MIDI: **11,685 checks pass**; source capture SMF
  fixtures and portable shared-EEL MIDI comparison pass.
- Controller normal and ASAN: **162,709 policy + 558 host checks pass each**.
- Existing independent-chain, dedicated-chain and JACK graph workflows pass
  in the first full run, including bounded overload/emergency output.
- **Full combined suite is NOT green.** First run fails waiting for browser
  STOP PHRASE. An unchanged focused run passes. A stronger fixture now verifies
  that the native mode is LOOP before PLAY, retaining the original STOP assertion;
  a later run fails this new precondition. That establishes a mode-application
  failure in that workflow, not a proven root cause or an engine correction.
- A second complete native/JACK/Chromium attempt fails the three-chain grid
  recording test after dummy-JACK XRUNs: `chainError=1`, `lateBlocks=6`,
  `outputOverflow=0`, `activeNotes=0`. The safety stop is retained. This is
  independent of the source/ownership tests and does not prove a Pi defect.
- Native+Chromium without JACK passes preceding engine/portability/controller/
  browser workflows, then fails the native LOOP precondition. A later focused
  browser run times out opening the VELOCITY module editor. Root cause remains
  unresolved; there is no claim these interactions are corrected.
- The remaining issue #53 browser workflow was executed separately and passes.

See [execution evidence](evidence/conductor-a-validation.txt) and the
[measured MIDI/capacity report](evidence/conductor-a-baseline.json). No assertions,
timing guards or queue bounds were weakened. No runtime source was changed.
Keep PR A draft: its focused baseline is reproducible, but the complete
regression gate must be resolved before starting critical PR B changes. Do not
retry until green and erase failed attempts, or treat the known-failure runner's
exit zero as proof of new musical behavior.

## Exact next coding step for PR B

Create a branch stacked on this PR after its test gate. Start with a bounded
runtime admission identity/generation and a per-instance routed-note ledger in
the shared EEL path, with an explicit independent admission context. Match
releases against emitted attacks and surviving owners; do not infer ownership
from channel/pitch booleans. Add independent-admission tests alongside the
retained legacy trigger fixtures before changing `process_phrase_trigger`,
`send_once_to_instruments`, `route_emit_note` or cleanup paths. Preserve source
events, descriptors, serialized addresses and recording semantics. Resolve the
overload and physical-owner cases before admitting layered playback. Keep mono/
ARP restrictions explicit until their corresponding ledger tests actually pass.
