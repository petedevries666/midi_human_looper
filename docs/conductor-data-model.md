# CONDUCTOR PR C: configuration model and persistence

Base: PR #57 `25c78f791421650ce73b446eb07bbc00d6d26784`, depending on
#56 and #50. Contract: PR #55 `73cdee5604992ca3bd68e4c6c3b97c545333b127`
(the complete 878-line specification, including resolved Q1/Q2/Q4).
This is configuration infrastructure. No new CONDUCTOR execution, interface,
JOIN, REVEAL, FECK, MOVEMENT library, ownership policy or scheduler is added.
The shared EEL engine, 12 ONCE voices, UI and installation are unchanged.

## Format audit and compatibility

The current production patch is schema 7 with 171,649 numeric cells and nine
globals. Its native Controller and Snapshot records are top-level versioned
extensions. Legacy patch schemas 1–6 migrate through the existing production
loader; source MIDI and legacy Smart Switch sequences remain authoritative.
Portable project v1 carries this patch and canonicalizes source timing to
seconds. Unknown fields/versions are refused rather than stripped.

PR #45 HEAD `d1abbc327b8184e1f400548126ab248eebd7380a` adds schema 8
(marker + 16 playback policies), portable v2 and two ONCE policies. It does
**not** contain four-track storage or STEPS × LAYERS. It is not merged here.
Appending numeric CONDUCTOR offsets as schema 8 would collide with #45.
Instead C uses a separate `conductor` extension with its own version 1. No
numeric offsets, portable envelope version, timing semantics, bank records or
legacy source modes are reinterpreted. Integrating #45 later still requires its
explicit schema/portable-version migration; C does not claim schema-8 execution.

## Typed model

The decoded document has exactly `version`, `sources` and `switches`.

```json
{
  "version": 1,
  "sources": [{"id": "00000000-0000-0000-0000-000000000001", "type": "PHRASE", "slot": 1}],
  "switches": [{
    "switchId": 1,
    "traversal": "SEQUENTIAL", "transition": "IMMEDIATE", "gesture": "INSTANT",
    "steps": [{
      "id": "00000000-0000-0000-0000-000000000002", "transition": "INHERIT",
      "layers": [{
        "id": "00000000-0000-0000-0000-000000000003",
        "block": {
          "id": "00000000-0000-0000-0000-000000000004", "type": "PHRASE",
          "sourceId": "00000000-0000-0000-0000-000000000001",
          "overrides": {"playMode": {"mode": "OVERRIDE", "value": "ONCE"}}
        }
      }]
    }]
  }]
}
```

Array order is musical order, never source identity. Each STEP, LAYER and BLOCK
has its own canonical UUID. Smart Switch ownership uses its existing stable
numeric ID. Duplicate identities, source-slot aliases and duplicate switch
owners are rejected. A source's MIDI is **not** copied into a block.

`block: null` is EMPTY. First LAYER is PHRASE MASTER or EMPTY, with validation
on every complete commit/load, including reorders/replacements. A masterless
STEP with MOVEMENT in a later LAYER is valid. Later LAYERS accept PHRASE,
MOVEMENT and typed action references. Whole-column reorder keeps IDs, layers and
options attached. Removing a BLOCK only removes that reference.

Switch traversal: SEQUENTIAL/BACKWARD/PING_PONG/RANDOM/SHUFFLE_BAG. Switch
transition: IMMEDIATE/END_OF_PHRASE. STEP transition adds INHERIT. Gesture:
INSTANT/EXCLUSIVE. These are persisted intentions, not newly implemented behavior.

PHRASE overrides: playMode (LOOP/ONCE/HOLD), trigger (PRESS/HOLD),
instancePolicy (JOIN_EXISTING/RESTART/NEW_INSTANCE), join
(TRIGGER/JOIN_NOW/JOIN_AT_LOOP_START), referenceTime (CYCLE/ELAPSED), entry
(TRIGGER/REVEAL), release (LATCH/GATE), phrase_time_decay,
phrase_velocity_decay, phrase_base_velocity. Numeric ranges come from the
existing authoritative descriptors. MOVEMENT overrides: trigger, join,
referenceTime, movementPlayMode (ONE_SHOT/GATED), retrigger
(SOFT_RESTART/DIRECT), destination (CC+channel or exposed parameter identity).
Every local option is either `{mode: INHERIT}` or `{mode: OVERRIDE, value: ...}`;
absence also means inheritance. MUTE GROUP is explicitly forbidden locally.
No local edit writes source parameters.

Action blocks contain `id`, `type: ACTION`, `action`, `target`, `trigger`.
Stored actions: STOP/PAUSE/RESUME/RESET_CURSOR/RESET_SHUFFLE_BAG/STOP_RESET.
Typed targets use a PHRASE source UUID, MUTE_GROUP ID, ALL_PHRASES, or SWITCH ID;
reset actions target a switch. These records have no dispatcher in C. The existing Smart Switch dispatcher
continues to execute its legacy configuration; CONDUCTOR metadata is dormant
until D. Do not treat a legacy TEST action as playback of the new document.

## Stable source adoption and unavailable references

`conductor.migrate(patch)` adopts the existing 16 fixed phrase slots explicitly:
once at adoption, each gets a UUID. Those identities are persisted thereafter.
An existing extension is deep-copied without allocating replacement identities.
Legacy patches without an extension stay legacy: LOAD/SAVE never synthesizes a
CONDUCTOR or converts sequence indices into blocks. Clearing MIDI content keeps
the phrase identity; removing a source binding leaves references unresolved.
Reusing its slot with a new source requires a **new UUID**. Tests prove the old
reference never resolves to that replacement.

The production MOVEMENT library is not present yet. MOVEMENT source UUIDs can
be referenced and round-tripped, but remain reported as unavailable; C does not
invent curve storage or silently map them to a controller. Missing switch and
source references are retained and reported by `resolve` / the read endpoint.
Unknown extension versions/options are rejected before activation; the original
file is preserved for correction or a future compatible reader.

## Carrier and atomic activation

The patch adds:

```text
conductor = {version: 1, configuration: [canonical ASCII JSON bytes...]}
```

This follows the existing native extension/wire pattern, without frozen EEL
memory offsets. The typed document has no names needing Unicode escaping;
source and switch names remain in their existing authoritative records. Python
serializes sorted keys and compact separators. The native control worker
validates both byte framing **and the complete typed document** before handoff.
It retains configuration outside the callback and includes it in SAVE.
The two validators are tested through production paths, including direct socket
requests bypassing HTTP. Descriptor ranges are reused in both adapters.

`GET /api/v1/conductor` returns `model`, `missingReferences` and
`executionSupported: false`. No browser interface is added.
`conductor_commit` uses the existing protocolVersion/session/revision command
contract, guarded patch capture and guarded atomic activation. It is currently
**STOP-only**, refusing held notes, recording, running playback or morphs. This
is a configuration transaction, not a performance action. PR D must provide a
bounded execution handoff before enabling live editing.

A failed parse/validation/conflict retains the old document; successful LOAD
swaps it only after the existing patch/controller validation succeeds. LOAD
resets musical runtime and does not start PHRASES. Factory NEW clears the
extension. HTTP-worker restarts do not lose engine-held configuration. Disk SAVE
uses the existing fsync/atomic-rename implementation; SAVE/LOAD/SAVE bytes are
identical for unchanged stopped configuration. Patch SAVE and project revisions
carry the extension, and invalid existing files cannot be overwritten silently.

## Studio/live boundary

Portable v1 native round-trips the extension at 44.1/48/96 kHz without treating
configuration bytes as musical timestamps. REAPER execution of CONDUCTOR is
**not supported yet**. Portable materialization and EXPORT REAPER BASE explicitly
refuse it; the original portable/headless document remains intact. The actual
Lua patch daemon refuses both LOAD and overwrite of such files, before payload
writes. This is compatibility by safe preservation/refusal, not execution parity.
No unsupported data is silently erased and no success claim covers REAPER
hardware or the physical V4.

## Capacity and Q3

C does not select a maximum STEP/LAYER/MOVEMENT/instance count. Existing source
storage remains 16 × 2,048 events, and playback remains 12 ONCE instances.
Existing transport security ceilings still apply: 16 MB engine/file command
ceiling, 32 KiB HTTP command ceiling (including `conductor_commit`), JSON nesting
32 for the worker parser (this schema needs fewer levels). These are parser/
transport limits, **not** approved musical capacities. Oversize requests reject,
never truncate. Larger configurations can travel through validated patch LOAD.

Measured example (four STEPS × two LAYERS, sixteen source identities):
2,756 typed JSON bytes, 9,028 patch-carrier bytes, 2,867 HTTP command bytes.
The reproducible sizing recipe is in the evidence README. This is one fixture,
not a capacity benchmark or an approved upper limit.

Before live execution in D, measure admission costs and derive a bounded
handoff from the existing 12-voice budget. Propose limits with measurements;
no assertion here treats Q3 as resolved. MOVEMENT update rate, runtime storage,
handover duration and curve limits remain open for their later phases.

## Validation and gate

Run `tests/test_conductor_persistence.py` against the **built C binary**. It
exercises real HTTP/native worker/patch files, legacy migrations, source
isolation, unavailable references, reordered/deleted blocks, malformed socket
requests, conflicts, STOP-only guards, worker restart, silent LOAD, portable
preservation and Lua refusal. The combined runner includes it. Results and exact
commands are recorded in `docs/evidence/conductor-data-model/`.

The two existing UI failures remain non-blocking only with unchanged signatures:
pending PANIC can drop a mode edit, and telemetry can replace an EDIT button
during pointer-down. C changes no web file, JSFX/GFX, MIDI rendering or installer.
They must still be reported, not counted as PASS. Legacy ONCE cross-source choke
remains an explicit compatibility XFAIL distinct from independent admission.

PR D may proceed only after the complete regression gate passes and these known
failures retain their signatures. Its minimal PHRASE execution must use B's
instance admission/ownership, reject unresolved references, preserve legacy
paths and measure real-time handoff/capacity. C alone does not qualify a release
or prove CONDUCTOR MIDI execution.
