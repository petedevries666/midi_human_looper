# DICKINSON — ARP completion and safe MIDI recall

Implementation base: PR #93, `03ade326d38b2777c65396cd94d05d0eb32cd6da`,
which contains #89 → #90 → #91 → #92. #95/#96 are excluded. REAPER is frozen;
its JSFX bytes are unchanged. No hardware deployment, merge or routing change.

## Musical contract

The existing generic native ARP editor gains **STEP MAX** (1–4, default 2) and
**PLAYBACK** (CONTINUOUS default / ONCE). Native parameter identities are 27/28;
all existing identities, including mode IDs 9–12, remain unchanged.
Controller mappings and snapshot capture/instant/morph use the existing ownership
and discrete-switch mechanism. New controls use native Controller mappings,
not the frozen legacy expression TI pages. DONE/CANCEL use the existing editor.

CLIMB still chooses the preferred direction with probability 70%, backtracking
with 30%. Distance is sampled uniformly from 1..STEP MAX then clamped at the
chosen boundary. Preferred direction reverses at the held-note endpoints. It
uses actual held-note positions, not chromatic semitones, cached patterns or
an octave generator. IDs 9/11 still share the upward initial direction; 10/12
share the downward initial direction. Distinguishing/consolidating them remains
a separate musical decision.

ONCE traversal lengths:

| Modes | Complete traversal |
| --- | --- |
| UP, DOWN | Each effective held pitch once, ascending/descending |
| RANDOM, NO REPEAT, WALK, WEIGHTED | One draw per effective held pitch; randomness retains the mode's usual rules, not guaranteed coverage |
| BAG | One complete shuffled held-pitch bag |
| LOOP, MUTATE | One complete eight-step motif |
| CLIMB 9–12 | From initial endpoint to opposite endpoint and back; one held pitch emits once |

CLIMB traversal length is stochastic: the callback performs bounded single-step
work with no retry search, but elapsed musical traversal time is not given a
new arbitrary cap. Gates still release the last emitted note. A completed ONCE
never restarts just because its chord remains held.

An effective held-pitch-set change is a new triggering gesture: it starts a new
ONCE traversal from the appropriate boundary. The release of the final pitch
rearms it; a new chord can then play again. Same-pitch overlapping Note Ons do
not change that set and cannot retrigger a completed traversal. Existing latch
semantics determine the effective pitch set. Releasing a physical key that is
still latched does not rearm ONCE; clear the latch or change the effective chord.
Mode/STEP MAX edits do not reset the ONCE admission count. Switching an already
completed continuous traversal to ONCE stops further attacks, without a new
reattack; switching back to CONTINUOUS resumes at the next processing block.
These are ARP policies, independent of PHRASE ONCE/HOLD.

CONTINUOUS retains the legacy timing and selectors: changing its held pool does
not newly reset its step phase. STOP/PANIC keep the existing ownership cleanup.
Bypass releases generated notes; these settings never change their pitch/channel
or already emitted gate release destination.

## Persistence and compatibility

Native schema 8's existing memory layout remains unchanged. New saves add:

```json
"nativeArp": {"version": 1, "configuration": [1, 2, 101, 4, 1, 102, 2, 0]}
```

Wire: version, number of rows, then stable Instrument ID / STEP MAX / playback
(0 CONTINUOUS, 1 ONCE) for each row. One ARP per instrument remains the existing
restriction. IDs are resolved only against the loaded patch; missing/duplicate
IDs and invalid ranges are rejected. No cursor, held notes or running traversal
is serialized. Missing carrier (old schema-8 patch, or migrated legacy patch)
loads 2/CONTINUOUS. Loading is validated worker-side and committed with the
existing paused transaction; invalid destinations restore prior patch memory.
Instrument deletion clears its extra settings before any slot reuse.

Snapshots store eligible effective values by existing stable Instrument/module
identity, including kinds 27/28. Old snapshots simply omit these targets. An
older runtime that does not understand the nativeArp carrier must refuse the
new patch instead of dropping it. Native schema-8 export to frozen REAPER stays
explicitly unsupported. No user's patch file is converted in place.

## MIDI Program Change

`loadedPatchSlot` is native session status, not patch content or UI selection.
It starts at 0 (unknown) and is set only after successful LOAD with an optional
`loaded_patch N` worker marker. Legacy clients retain their original wire syntax.
The existing guarded LOAD argument is unchanged. Web library LOAD, physical
patch-1 LOAD, host recall/rollback and explicitly identified Zynthian snapshot
restore supply identity. SAVE/selected slot never prove identity; full-patch
PASTE invalidates it. In-patch Conductor/switch/clipboard edits preserve it.
New snapshots carry optional loaded identity; old snapshots restore 0, never a
persisted selected number guessed as an active patch.

Only the production MIDI recall worker performs the identity check, before any
file validation/export/STOP/MBMF reload/linked snapshot operation. Matching PC
is a true no-op even with unsaved edits, missing saved files or missing links.
RAPPELER PATCH stays an intentional reload. Rapid external PCs retain the latest
intent, including returning to the previously loaded patch during another load.
After that load/rollback, the worker checks the actual session identity again.
Internal snapshot-origin PCs remain suppressed. A failed recall restores the
prior actual identity, including unknown (0). No opt-in/channel policy changes.

## Reproduction

Use the documented pinned ysfx/JACK development environment (AGENTS.md):

```sh
scripts/headless-build.sh
scripts/dickinson-arp-test.sh
python3 -m unittest discover -s tests -p test_dickinson_native.py
python3 -m unittest discover -s tests -p test_native_arp_config.py
python3 -m unittest discover -s tests -p test_patch_recall.py
python3 tests/test_dickinson_browser.py
scripts/dickinson-jack-test.sh
```

Use the prepared Python venv for browser/SMF tests (`TEST_PYTHON`,
`SCREENSHOT_PYTHON`); provide `HEADLESS_BINARY`, `YSFX_SOURCE`/`YSFX_BUILD`,
`JACK_INCLUDE`, `JACKD`/`JACK_DRIVER_DIR`, `CHROMIUM_PATH` where required.
JACK script creates only its named private dummy server and test ports. It does
not connect instruments or change the hardware JACK service. Set
`DICKINSON_MIDI_EVIDENCE=/path/trace.json` to retain actual receiver events.
`SANITIZE=1` enables ASan/UBSan on the compiled native test host. The pinned
precompiled ysfx archive itself is not fully sanitizer-instrumented.

Full results and failures are retained in `docs/evidence/dickinson/`.
The repository-wide screenshot workflow currently flags clipped Smart Switch
TEST labels at 320px in the unchanged #93 Web sources. That run is not green.
Targeted actual native ARP screenshots and interactive layout tests cover all
five sizes separately; neither claim full-application visual qualification.

## Physical qualification — NOT RUN

After human review only: load a disposable copy of a patch on Zynthian V4,
play narrow/wide chords with STEP MAX 1/4, test all mode families in ONCE and
CONTINUOUS, release/latch/retrigger, sustain, bypass, STOP/PANIC and snapshots.
Save/restart/reload. With MIDI recall deliberately enabled on a non-master
channel, hold notes/run phrases and edit without saving: repeat the loaded
patch PC; verify unchanged engine session, sound, edits, Conductor and linked
rig. Then test a different saved patch, latest-request queue and a broken link
on disposable fixtures, including rollback. Explicit RAPPELER PATCH must reload.
No ARM64, Helix, synthesizer sustain or Oram snapshot service was exercised in
Cloud. Existing CPU/XRUN hardware concerns remain outside this focused change.
