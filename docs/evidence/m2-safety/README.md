# M2 MIDI-safety follow-up to #82

Cloud production native DSP → private acyclic JACK ports, 48 kHz/8192 frames,
no browser, no hardware deployment. Runtime source is the untouched production
JSFX for the safety tests. The receiver asserts chronological observation order;
it does not sort, filter away failures, or retime events.

## Defect and correction

`before/sustain.json` and `before-failure.log` reproduce CC7=127 **before** external
CC64-off following a short hidden PRESS/RELEASE. This could reveal a note still
sustained by the physical pedal. Cutting CC64 or forcing all-notes-off would also
cut unrelated live music on that channel.

The existing Controller Host lease now retains the hidden volume until actual
emitted CC64-off, then restores it after that event. At most sixteen channel
restorations are stored. This is deliberate bounded ownership awaiting a real
pedal release, not a running PHRASE or untracked stale writer. New token owners
and physical CC7 invalidate it; PANIC clears it through existing global safety.
No second scheduler, callback allocations/locks/I/O, schema change or new UI.

## Actual MIDI gates

`scripts/reveal-safety-test.sh`:
- external pedal + unrelated live note + hidden short tap: 57 actual events;
- physical plus source-owned shared sustain: 58 events;
- physical CC7 takeover while restoration is deferred: 57 events, no stale CC7;
- full shared output buffer burst: 5121 requested attacks across six PHRASE layers,
  63 emitted Note Ons, 161 actual output events, explicit overflow=1, emergency
  cleanup, pending output=0, no surviving note counts/instances/REVEAL leases,
  no attacks after emergency and unchanged 2048-event source.

Structured `after/*.json` contains actual port observations and native state.
Controller-token helper tests include deferred release, replacement and PANIC;
ordinary and ASAN/UBSAN helper runs plus five native REVEAL tests pass. Existing
MOVEMENT actual JACK fixture still passes exact 10/25/50/100 Hz cadence assertions.
Native sanitizer qualification results are appended at final checkpoint.

## Three versioned historical tests

`scripts/phrase-contract-test.sh` executes each fixture in both contracts:
1. Native baseline: legacy `[2]` versus contract2 `[1,2]` playing sources.
2. JACK ownership: the original exact nine-event choke golden remains in
   `legacy_expected`; contract2 asserts its own exact eight-event golden and
   overlapping source identities plus PANIC cleanup.
3. Dedicated chain: the original release-to-stop/short-tap expectation remains
   under legacy1; native2 asserts RELEASE leaves the same HOLD IDs/notes active,
   subsequent PRESS replaces them and explicit STOP releases them.

`tests/phrase_contract_fixture.py` explicitly selects the retained **legacy-native
DSP branch**, `native_phrase_contract=0; native_hold_enabled=1`, in a temporary
source fixture. It uses the same real native host/DSP/routing, not a MIDI model.
It is a test-only selector, not a supported production legacy mode or an old
binary/host parity claim. Normal tests use the unmodified production source and
contract2. The public native build metadata remains that of the actual current
host. Frozen REAPER's historical contract-zero coverage remains separate.

No assertion has been deleted or weakened into an optional fallback. Exact old
expectations remain executable; native2 is checked against its approved semantics.
The old PR-A EEL baseline now explicitly labels its legacy register selection.

## Reproduction

Use the prepared native/JACK environment from AGENTS.md:

```sh
scripts/headless-build.sh
REVEAL_SAFETY_EVIDENCE="$PWD/docs/evidence/m2-safety/after" scripts/reveal-safety-test.sh
scripts/phrase-contract-test.sh
scripts/reveal-test.sh
SANITIZE=1 scripts/reveal-test.sh
scripts/movement-jack-test.sh
```

No repeat of #82's screenshot/global campaigns. No Web files changed. Cloud
functional results do not qualify ARM64, real synth sustain behavior or small-buffer
XRUN/CPU deadlines. Shared-channel CC7 still affects unrelated parts; MIDI cannot
isolate sustained voices on the same physical channel. Restoration waits until
pedal release rather than killing that channel's unrelated notes. The existing
nonblocking shared-channel warning and independent-channel advice remain relevant.

## Recovery checkpoint (2026-10-16)

Recovered after Cloud workspace failure. `2a62570` and its committed MIDI evidence
are preserved on `fix/reveal-midi-safety`. The combined-runner registration and
this explanatory README were uncommitted at interruption and are preserved here,
not claimed to have completed a final combined/sanitizer run. Old `/tmp` completion
logs did not survive; do not infer final exit codes from the interrupted session.
The current request is M4 based on #85; do not silently integrate this independent
M2 runtime delta into that routing/clock diagnosis.
