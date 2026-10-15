# Native Zynthian integration candidate — issue #75

Branch: `integration/zynthian-release-candidate`, created from actual main
`ab37a752693bf7d2d126a3a9e1ca1c863a5826a9` on 15 October 2026.
This document replaces #44 as the delivery entry point, not historical evidence.
The integration PR supplies the exact final tested HEAD, commands and exit codes.
Do not use ancestor test logs as final qualification. No tag/deployment is made.

## Integrated implementation

- Native ysfx/EEL engine; free-time first-note-origin REC/FINISH/cancel/overdub,
  LOOP/ONCE/HOLD, SMF note import/export, persistent editable phrase names.
- Stable instruments/Transformer IDs and restricted safe stage order; native ARP
  enable/rate/gate/modes; expression curves and named Controller bindings.
- Twelve independent ONCE instances, generation/actual-emission ownership,
  overlapping physical/phrase voices, bounded refusal, STOP/PANIC cleanup.
- Stable-reference CONDUCTOR PHRASE/MOVEMENT STEP/LAYER model, transactional editor,
  actual PRESS and TEST dispatcher, persistent local overrides and missing refs.
- MOVEMENT curves/rates/dedupe, parallel GLIDE, same-target replacement, physical
  CC takeover, STOP PHRASES independence; snapshots/timed/A-B ownership.
- Oram catalog refresh and dedicated source using ZynMidiRouter's **channel filter**,
  not direct synth JACK destinations; persistent PHRASE ORIGINAL/ALL/CH1–16.
  Instrument OUT ALL is not implemented; MOVEMENT keeps its explicit channel.
- Immutable portable projects/atomic activation/revision conflicts/restart authority,
  existing SEND/GET/PUSH/PULL bridge preserved as legacy, without new REAPER work.
- `mbmf.local` trusted-local or retained-token gateway, dynamic instance discovery;
  separate opt-in `az.local` portal from #69 in existing Webconf, no extra daemon.
  LUMAZ helper files, services and configuration are not modified by integration.
- Reviewed UPDATE Web/native controls share a separately authorized worker, verified
  release manifest/merged ancestry, candidate preflight, rollback/recovery and
  configuration-drift refusal. A draft cannot be offered as an executable update.
- #72 unknown-extension data-loss refusal; #73 shared observation JSON bytes;
  #74 stale updater-configuration guard; #63 optional bounded RT diagnostics.

[All PRs, states, exact SHAs, bases and treatment](release-candidate-75-pr-inventory.md).
#74 exact HEAD `5aaee11`, #69 `a784aff`, #63 `d6169f9` are merged into the new
candidate, in that order. Only mechanical conflict: `tests/conductor_jack.cpp`:
retain #63 acyclic source/sink diagnostic option and #68 safe two-byte messages.
No musical event transformation/order was changed by that conflict resolution.
Original branches are untouched. Source PRs remain open pending integration review;
“superseded” describes the delivery path, not a false GitHub merge/closure claim.

Excluded #45/#46 overlap newer HOLD/persistence/screenshot implementations. Do not
merge their old schema/UI paths. #25 HUMANIZER/#28 ECHOCITY remain non-playable
foundations; do not advertise effects. #11/#12/#35/#36/#39/#55/#59/#65/#70 are
reference/design/history, not executable features. #55's latest master spec is
retained byte-for-byte; its REAPER parity language is superseded by the freeze.
LIVE BYPASS/MIDI LOG, JOIN/REVEAL/FECK/random multitrack behavior are not delivered.

## Controller Learn isolation correction

Before: updating an existing source invoked global `Host::panic()`, and FORGET
invoked global `core.panic()`. Learning CH2/CC21 cancelled unrelated CH1/CC11
MOVEMENT and all external Controller leases. Conflicting-source confirmation also
relied on this global side effect to release the displaced source.

Now reset only mapping runtimes whose stable source ID changed, through existing
`Engine::configure`. This clears stale pickup/GLIDE/return runtime and releases
only mapping-owned tokens. It preserves effective values, committed bases,
Snapshot/MOVEMENT external tokens (even on a mapped target), other physical
owners, source names, Learn conflict confirmation and quarantine. Displaced
source mappings are reset explicitly for both source/command Learn. No new
ownership system, schema, MIDI routing or scheduler.

Tests include a deterministic failing-before host fixture; real native HTTP
Learn/FORGET/source reassignment; real JACK-captured automation continuing through
physical Learn, with every expected integer value and exact 1,920-frame cadence
at 25 Hz. Explicit PANIC must still invalidate all leases. Existing A/B-edit
cancellation at the engine adapter is unchanged, not claimed solved.
The 3-second first JACK fixture expired while several acknowledged commands
completed at 8192 frames; it is retained as failed evidence. The final fixture
uses an 8-second triangle with **201 exact values/timestamps**, not a weakened
ownership/cadence assertion. No engine change was made to improve that fixture.
The inherited test typo `returnPolicy` is corrected to actual `returnMode`.

## Reproducible qualification

Prepared Cloud environment: see AGENTS.md. From this checkout:

```bash
scripts/headless-build.sh
python scripts/combined-test.py --native --jack --browser chromium --web-access --timeout 240
```

Use the dependency-enabled test venv for `python`, export `TEST_PYTHON` accordingly,
and set `YSFX_SOURCE`, `YSFX_BUILD`, `JACK_INCLUDE`, `JACKD`, `JACK_DRIVER_DIR`,
`CHROMIUM_PATH` as in the existing Cloud setup. `HEADLESS_BINARY` must be the fresh
candidate build, not an ancestor. The aggregate gate includes Oram installation/
channel filtering, 704 PHRASE-output checks, MIDI/SMF/overdub/ownership, Controller
and MOVEMENT ASAN/UBSAN, actual native sanitizer diagnostics, both prior UI races,
Web/native update authorization/rollback, preservation and observation-cache tests,
Webconf + AZ browser/peripheral fixtures and zero-allocation trace-ring test.
No test assertion or known legacy ONCE compatibility XFAIL is removed.

Private diagnostic profiles (not the physical Pi):

```bash
MOVEMENT_RT_TEST=tests/movement_live_profiles.py scripts/movement-realtime-test.sh \
  --output /tmp/mbmf-rc-live --buffers 512,256 --seconds 12
```

The profiles publish actual active-source counts, input gestures, note/CC output,
thread CPU vs wall p95/p99/max, XRUN and refusal/overflow counters. They are not a
certificate of concert stability. Optional `--rt-trace` writes via a separate
worker; normal runtime enables no tracing. No browser/edits run in the measured
live windows. Large-buffer functional tests are a different workload.

## Blockers and boundaries

- Historical and possibly current Cloud deadline/XRUN excursions require attributed
  traces and physical V4 testing. No “Cloud noise” dismissal or guard reduction.
  Sample-rate/buffer-size changes during a live client are still unqualified.
- UPDATE stops/restarts the Zynthian UI and its children, potentially interrupting
  other instruments. Final stopped check is not an atomic physical-MIDI admission
  freeze; configuration CAS fixes a different race. No update during performance.
- Administrator authorization over plain HTTP is not encrypted. Use an isolated
  trusted LAN or existing HTTPS access; a tokenless editor is not admin authority.
- No eligible reviewed stable release is currently published. Do not publish a
  release/tag before review just to bypass updater safety. Webconf/AZ helpers are
  separately provisioned/rolled back; runtime UPDATE does not silently replace
  registration, routing or Webconf integration files.
- SMF import is notes-only; export can retain other recorded channel messages.
  Such files cannot be imported losslessly today. No silent flatten/truncation.
- Sustain-aware receiver sound, real Oram/mDNS/hotspot/Helix and interrupted
  activation/power loss need hardware. Tests explicitly label peripheral fixtures.
- Old runtime rollback may not execute new free-time/channel policy. Validate
  candidate restore before switching; preserve separately versioned old projects.

These are review/release gates, not reasons to force a merge or delete assertions.
The JSFX blob remains identical to #74; all 25 protected issue-54 files must remain
SHA256-identical. No changes to live Pi, LUMAZ, Zynthian OS or JACK service.

## Manual install and rollback after separate review (not executed)

Use the existing `/root/midi_human_looper` checkout only. First save/export projects,
record actual running SHA, keep current rollback journal/owned-file backups and
Zynthian snapshot, finish REC, STOP PHRASES/MOVEMENTS/morphs, release sustain.
Do not `git reset`, remove patches or overwrite a dirty checkout.

The first reviewed candidate installation follows the existing installer preflight
and runtime workflow in [Zynthian updates](zynthian-runtime-update.md),
[native filtered routing](zynthian-channel-source.md),
[local access](zynthian-local-web-access.md) and
[AZ installation/rollback](az-local-control-hub-implementation.md).
Check the actual document paths in the linked procedures; runtime and optional
Webconf helpers are separate owned transactions and separate restarts.
Do not install this draft SHA through the reviewed-release UI.

Routine reviewed UPDATE/ROLLBACK uses the common admin worker; failed activation
restores prior config and adapter bytes, starts the old runtime and validates
project fingerprints. Interrupted pending journal uses RECOVER. Never delete the
journal to force another update. If no healthy runtime returns, retain evidence
and use the documented previous configuration/runtime with its matching project.
No promise that old binaries execute new semantics merely because schema stays 7.

First V4 acceptance after review: one MBMF source into three independent synth
channels 2/3/4 through Oram; physical overlap/sustain/STOP/PANIC/ALL output; save,
restart, snapshot restore; browser closed LIGHT/NORMAL 512 then 256 only if clean.
Test optional Webconf/AZ/update recovery in a separate stopped session. No concert
qualification, automatic deployment or phase-G implementation is authorized here.
