# Headless Controller integration, issue #18 C2

This branch connects the #21 policy core to the real ysfx/JACK host and browser.
It supports 16 stable logical sources, 32 independent mappings and 16-point curves.
Sources have exact note/CC/channel identity; source IDs and mapping/target IDs are
independent of storage slots. One source may drive many targets; many sources may
compete for a target. IDs are 24-bit integers; the editor generates unused random IDs.
All configuration commands require the engine session and expected revision.

## Ownership and processing

The JACK input path and HTTP MIDI simulation call the same `controller::Host::midi`.
One Learn target exists globally. Starting Learn cancels the existing JSFX Learn lease.
The next valid note press or CC captures only that source. Capture exits automatically;
conflict capture waits for CANCEL or explicit REASSIGN. Old assignments stay intact
until confirmation. Existing phrase/switch/legacy-controller inputs cannot be silently
reassigned: the UI reports the conflict and requires another input. FORGET removes
only the source MIDI identity, preserving its mappings and all phrase/switch settings.
Captured note releases are quarantined even after CANCEL/FORGET; unrelated held-note
releases still reach performance routing. Sustain CC64 and channel-mode CC120–127
remain reserved for safety and are never captured as controller sources.

The processing thread owns the adapter and policy engine. Physical input → exclusive
Learn/source routing → per-mapping curve → takeover/priority/return arbitration →
normalized effective value → descriptor scaling → existing `param_apply`/instance
pending storage → JSFX scheduler. Timing derives from the sample clock. GLIDE and
returns tick once per processing block; controller application is block-rate, not
sample-accurate automation. No sockets, disk, JSON, allocation or locks run in this path.

DIRECT/PICKUP/GLIDE/SLEW and OFF/IDLE/RELEASE/COMMAND return modes use the #21 semantics.
Numeric enum values are shown in the editor. RELEASE is Note Off or CC value zero;
use IDLE/COMMAND for a continuous pedal when zero should not imply release. CAPTURE STATE changes the active return
snapshot; RETURN acts only on a COMMAND-return owner. Higher priority wins; equal
priority uses newest source event, with lower stable mapping ID breaking same-event
ties. Ownership tokens protect against stale returns. Creating a mapping captures a committed deferred value when notes are held,
rather than the older value still sounding. Manual parameter commits reset
ownership and update the committed base. PANIC, LOAD, overload recovery, target
deletion and source reconfiguration cancel runtime ownership. Deleted/retargeted
mappings retire unused target records, so repeated edits do not exhaust target storage.

## Targets and shared editor

Mappings address Instrument VOLUME, each existing Transformer parameter, and each
phrase's TIME DECAY / VEL DECAY. Phrase targets use reserved native kinds 14/15;
the wire's instance carrier is `instrumentId`, interpreted as phrase ID for those
kinds, with `moduleId=0`. Instrument targets use stable Instrument/module IDs. This
is an adapter encoding, not a new note Transformer. Phrase timing uses the existing
logarithmic ratio scale (×0.5…×2); velocity decay uses ×0.2…×1. Original events and
existing retrigger/reset conditions are untouched. Other phrase controls are not yet
mapping targets.

Policy fields and phrase decay parameters are registered in `modules/catalog.json`
with scope, stage, reset/panic hooks and serialization versions. The editor builds
policy fields from descriptors. The reusable multipoint browser component previews
points and bends using the existing EEL bend exponent; DONE validates the whole
mapping, while CANCEL/ESC/X/outside dismissal discards the draft. Existing expression
assignments remain functional. Their targets are rejected by the generic adapter to
avoid two writers. Automatic legacy-assignment migration is not implemented yet.

## Persistence and REAPER boundary

SAVE writes the full configuration-v1 `controllerEngine` extension into the **same**
canonical patch JSON, not a sidecar. The schema-7 payload stores committed bases,
not transient pedal/GLIDE/return values. Runtime ownership, Learn candidates,
quarantine and captured return snapshots are excluded. LOAD validates before commit,
releases notes, applies the patch and atomically recalls valid mappings. Invalid
identities, curves, capacities, duplicate keys or conflicts roll back the configuration
and legacy payload while playback remains stopped. Browser/worker restart does not
own or erase configuration; a fresh engine restores it through explicit LOAD.

The REAPER JSFX remains functional with its existing assignments and schema. Full
bidirectional new-policy support in REAPER is **not implemented**. EXPORT REAPER BASE
writes `patchN-reaper.json` separately, retaining legacy assignments and base values,
while preserving the original headless file. Copy/rename that exported file to the
REAPER daemon's `patchN.json` location. The companion Lua daemon refuses to load or
overwrite files containing nonempty/unknown headless configuration, preventing a
silent destructive round-trip. Migrating this extension into a shared JSFX/project
schema and implementing REAPER policy processing remain a later compatibility task.

## Regression commands

```sh
scripts/controller-test.sh
SANITIZE=1 scripts/controller-test.sh
HEADLESS_BINARY="$PWD/.build/midi-headless-engine" python3 tests/test_controller_integration.py
# Use the optional browser/Lua test virtual environment:
HEADLESS_BINARY="$PWD/.build/midi-headless-engine" python3 tests/test_controller_browser.py
HEADLESS_BINARY="$PWD/.build/midi-headless-engine" YSFX_SOURCE="$PWD/.build/ysfx" \
  NATIVE_PATCH_FIXTURE=/tmp/midi-native-patch.json \
  python3 scripts/combined-test.py --native --jack --browser chromium
```

`--jack` is a named dummy desktop test; never run it against Zynthian's existing server.
Pi/Helix timing and stock Firefox remain physical acceptance work. Desktop late-block
and callback maxima are diagnostics; the host does not claim hard realtime deadlines.
