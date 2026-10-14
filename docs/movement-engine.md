# Phase F — first native MOVEMENT engine

Base: PR E #61, `86e2f52be6c5810b0e551f747fe885d6b92f700f`.
Dependency chain: #50 → #56 → #57 → #58 → #60 → #61 → this draft.
Contract: PR #55 `73cdee5604992ca3bd68e4c6c3b97c545333b127`.
No merge, hardware deployment, issue #54 change or phase G implementation.

## Working subset

Sources are authored in the collapsed MOVEMENTS library, independently of STEPS.
They contain UUID, name, target, normalized multipoint curve, duration in seconds,
LINEAR/HOLD interpolation, SOFT_RESTART/DIRECT and GLIDE duration. Curves share
immutable storage across compiled block views. Local destination/retrigger overrides
never modify the source. LAYER 01 remains PHRASE MASTER/EMPTY. Later layers accept
PHRASE and MOVEMENT together; a masterless MOVEMENT STEP is valid.

SEQUENTIAL / IMMEDIATE / PRESS INSTANT admits independent ONE_SHOT automation.
STEP changes and STOP ALL PHRASES leave it running. A new source on the same target
replaces the old one; its generation token prevents the loser from returning.
Natural completion retains the final value and releases its ownership. It does not
send CC0 or automatically restore a preset. Physical parameter mappings retain
existing priority/PICKUP/GLIDE/SLEW and return policies. Snapshots and manual edits
use the same target identities/tokens; a superseded Movement never reacquires.
Legacy expression-owned parameter targets are refused, not assigned a second writer.

User decisions: configurable shared GLIDE, default 0.2 s; an unmapped physical CC
is passed unchanged through the existing MIDI path and cancels Movement on that
MAIN/channel/CC target. The current implementation advances the curve from PRESS
while GLIDE runs, without lengthening the curve. GLIDE uses the shared Controller
Engine response; for shorter curves it ends by the curve endpoint. This timeline
choice was explicitly confirmed by the user before final qualification.

The worker validates and prepares all JSON, UUID references and curves while the
engine is paused. The callback only holds immutable definition pointers, existing
Controller target tokens, bounded voices and sample positions. It reuses the native
processing-block MIDI batch, chronological sort and guarded JACK output queue.
The existing 64-entry host action ring carries STEP automation admissions with
sample offsets. Actual physical CCs and admissions are merged in chronological
order; a later physical CC in the same block cannot be overwritten by deferred
STEP dispatch. No second note scheduler is added; PHRASE ownership remains B's.

## Rate and timing

CONFIG / MIDI OUTPUT / MOVEMENT CC RATE is global: 10, 25 (default), 50 or 100 Hz.
Each source emits initially at its actual trigger offset, then at
`start + ceil(k * sampleRate / rate)`, with an explicit final sample. Curve values
are calculated from absolute source position, independently of that cadence.
Unchanged rounded CC values are deduplicated by effective MAIN/channel/CC.
Replacement emits its own initial value. Final values are never discarded by
dedupe when they change; an unchanged final value is already present at the receiver.
HOLD switches precisely at a point; endpoints match both UI previews and runtime.

Raw CCs use MAIN MIDI OUT and channels 1–16. Sustain CC64 and channel-mode CC120–127
are explicitly refused as automation; live safety messages remain unthrottled.
No Zynthian-specific chain IDs enter a project. Parameter automation uses existing
normalized descriptors and safe application/deferred paths at block boundaries;
it does **not** claim sample-accurate intra-block parameter changes to phrase notes.
New STEP parameter automation is dispatched after shared DSP and first affects the
next note-processing block; raw CC initial output uses the actual trigger offset.

## Persistence and compatibility

Numeric patch schema 7, portable envelope v1 and conductor byte carrier v1 remain
unchanged. Typed CONDUCTOR document v2 adds exactly `movements` and `ccRate`:

```json
{
  "version": 2,
  "sources": [],
  "switches": [],
  "ccRate": 25,
  "movements": [{
    "id": "00000000-0000-0000-0000-000000000001",
    "name": "FILTER RISE",
    "target": {"type": "CC", "channel": 1, "number": 74},
    "points": [[0, 0], [0.5, 0.2], [1, 1]],
    "duration": 2.5,
    "interpolation": "LINEAR",
    "retrigger": "SOFT_RESTART",
    "glideSeconds": 0.2
  }]
}
```

PARAMETER targets retain C's `{type,instrumentId,moduleId,kind}` identity.
Points are strictly ordered normalized `[x,y]`, endpoints x=0/1. Durations must be
positive and finite; execution refuses unrepresentable sample horizons instead
of truncating them. GLIDE range is the existing Controller Engine range (0–60 s,
strictly positive). Names are printable, unescaped ASCII; invalid strings are
rejected explicitly. Unknown fields, modes, versions, duplicate UUIDs and malformed
curves are rejected by both actual production validators before activation.

V1 LOAD/SAVE stays v1. Creating a source explicitly adopts v2, preserving identities,
source data, existing STEPS and switches. Missing references survive deletion and
are visibly identified. A duplicate PHRASE/Movement UUID cannot silently rebind.
LOAD never starts automation or PHRASES. No active owner, token, progress, Learn or
runtime cadence is serialized. SAVE uses existing atomic disk persistence and CAS.
Native portable round trips retain v2 configuration at different sample rates.
REAPER execution remains unavailable: existing portable/Lua adapters explicitly
refuse CONDUCTOR playback/materialization instead of erasing the data. Older native
readers refuse v2 rather than downgrade it. Keep the original patch during rollback.

## Authoring and API

Browser: open MOVEMENTS → + MOVEMENT → choose target → edit curve/duration → DONE.
Canvas add/drag/delete and numeric point keyboard controls reuse the existing curve
editor. Ramps and stairs are available. CANCEL discards the source draft. PREVIEW
starts the actual engine; STOP cancels all running views of that source. Open a
switch's CONDUCTOR → LAYER 02 `+` → MOVEMENTS → choose the source → DONE.
Use the existing TEST TAP or physical learned PRESS; save and reload the patch.

`conductor_commit` remains a STOP-only, guarded configuration transaction, including
source edits/deletion/rate changes. Running source edits are refused without mutation;
use STOP/PANIC before DONE. This first slice does not replace an active immutable
curve while preserving unrelated running notes. `movement_preview` / `movement_stop`
resolve UUIDs against the worker-owned document and then execute native commands.
A new read-only configuration command avoids the old patch-capture/stop path during
library telemetry. Browser reconnect observes native source IDs/progress and never
controls execution timing. Stale editor/session revisions are not blindly retried.

## Bounds and remaining limitations

Stored sources/points have no new musical count limit. Existing 16 MB native
transport and 32 KiB HTTP authoring ceilings still reject oversized documents
explicitly. Compiled source curves are shared rather than duplicated per reference.
Runtime storage reuses the Controller Engine's 512-target ceiling; PHRASES retain
exactly 12 independent instances. STEP dispatch uses the existing 64-action ring.

Raw CC admission reserves a worst-case cadence plus initial/final cost against the
existing 64-event callback drain: `cost = ceil(blockFrames * rate / sampleRate) + 2`.
Replacement on the same target reuses its reservation. At 48 kHz / 8192 frames this
allows at most 16 / 9 / 5 / 3 independent raw targets at 10 / 25 / 50 / 100 Hz. These
are derived host-budget limits, not new fixed source-library limits. Overload refuses
the new source before its initial CC and preserves existing automation; total MIDI
burst failure still uses the unchanged queue/PANIC guard. This does not reserve
headroom against arbitrary simultaneous note bursts or qualify Raspberry Pi latency.

Unsupported: GATED/HOLD admissions, JOIN/REVEAL/FECK, looped Movements, beat/bar
source durations, live source editing, independent mono/ARP PHRASE routes and REAPER
Movement execution. Unsupported stored local combinations are preserved and refused.
A STEP with several new Movement targets may hit runtime admission/priority refusals
individually; there is no atomic combined PHRASE+Movement reservation transaction.
This limitation must be closed before claiming all-layer atomic admission in G.
Recorded PHRASE CCs retain their existing output behavior; this slice does not give
those events Controller ownership or arbitrate them against automation. Use separate
CC targets if the source phrase already contains the same CC.

## Validation and physical test

```sh
scripts/headless-build.sh
scripts/movement-test.sh
SANITIZE=1 scripts/movement-test.sh
python3 tests/test_movement_persistence.py
MOVEMENT_BROWSER_AUTHOR=1 scripts/movement-jack-test.sh
"${TEST_PYTHON:-python3}" scripts/combined-test.py --native --jack --browser chromium --timeout 240
scripts/screenshots.sh
```

Use the existing Cloud caches/environment from AGENTS.md. Evidence records the
exact built source, exit codes, actual JACK port timestamps/values, callback costs,
all failed preliminary runs, screenshots and hardware qualification boundaries.

After human review only: on V4 create one 2.5 s MAIN CH2/CC74 ramp, attach it to
LAYER 02 beside a safe PHRASE on MASTER, and TEST/press the learned Helix trigger.
Confirm the receiving synth reacts; change STEP while it continues; test a second
source on the same CC; move an unmapped physical CC74 and confirm immediate takeover.
Disconnect Firefox/network and verify the ramp finishes. Test STOP PHRASES separately
from Movement STOP/PANIC. Save, restart and reload: neither source should start until
triggered. V4/ARM64, Firefox/touch, real Helix, receiver CC behavior, small-buffer XRUN
and concurrent note-burst latency require physical validation; Cloud JACK is not that.

Executed results and phase verdict: [evidence/movement-engine/README.md](evidence/movement-engine/README.md).
