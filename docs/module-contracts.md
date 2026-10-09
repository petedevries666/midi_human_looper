# Module / parameter contract v1 (issue #18, PR B)

`modules/catalog.json` is the UI-neutral metadata source. The generic browser renders
cards and numeric rails from it; parameter edits carry stable Instrument and module
IDs plus an expected revision. The native bridge resolves those IDs into current
slots and validates the complete transaction before applying any value. The REAPER
JSFX and patch schema remain unchanged: this is an adapter around its existing model,
not a parallel MIDI implementation or a new sound-changing migration.

## Four domains

- **PHRASES** own immutable recorded MIDI offsets and retrigger/record scheduling.
  Runtime voices apply existing TIME/VEL DECAY, without changing event storage.
- **INSTRUMENTS / TRANSFORMERS** own routing, serial processing order and note
  ownership. Independent instances retain IDs across editing/reorder/SAVE/LOAD.
- **CONTROLLER ENGINE** is a global domain. Controller takeover/return must own
  per-target effective values; it is not a note Transformer. Legacy expression
  assignment remains in JSFX until the separately tested controller bridge is ready.
- **EDITOR** owns draft copies only. Numeric input, rails and default reset are
  generic. DONE sends one transaction; CANCEL, ESC, X and outside clicks discard.
  A revision conflict leaves the editor open with an explicit reopen instruction.

No browser timer performs MIDI scheduling. HTTP/JSON remain off the processing
thread. Static descriptor validation rejects duplicate types, unknown parameters,
invalid ranges and unsupported contract versions. The processing thread alone owns
live EEL state. A request/ack queue is bounded at 64, configuration edits at four
parameters per command, and at most eight commands are processed per block.

## Descriptor fields and instances

`ModuleDescriptor`: `typeId` (stable textual ID), audited numeric engine adapter ID,
`scope`, ordered parameter IDs, `serializationVersion`, `migration`,
`processingStage`, `orderingConstraints`, `stateResetHook`, `panicHook`, bypass.

`ParameterDescriptor`: stable ID/kind, float/int/enum/toggle, min/max/default/step,
unit/label, normalized conversion (`linear_quantized` or `equal_bins`), assignment
eligibility and curve support. Conversion mirrors `param_scale` including enum bins
and signed rounding. Metadata lists capabilities; it does not mean every capability
has a browser control yet. The future controller/curve UI uses the same contract.

`Instance`: engine session + stable Instrument ID + stable Transformer ID + type +
ordered parameters/bypass. IDs are not screen indices. A restarted engine advertises
a new session; deletion and patch revisions invalidate old drafts. Existing schema
1–7 patch loading remains the canonical migration path. Snapshot values are current
effective values; expression-owned fields are read-only in this editor to avoid a
manual edit being silently overwritten. Base/effective separation belongs to PR C.

The six native adapters are TRANSPOSE, RANGE, POLYPHONY, VELOCITY, ARP and CC MOD.
TRANSPOSE/RANGE/VELOCITY/CC can repeat independently. ARP/POLYPHONY are limited to
one per Instrument, matching confirmed JSFX ownership restrictions. ADD/DELETE and
bypass use the existing bounded Transformer queue and wait for note release when
required. Reorder currently sends PANIC before swapping positions, deliberately
releasing active voices rather than reinterpreting their Note Offs. Parameter updates
use `param_apply` and per-instance pending storage; held-note pitch changes defer.

## Registering an extension without a new editor page

The registry test executes this example:

```python
from registry import Registry, REGISTRY
registry = Registry(REGISTRY.document())
module = dict(registry.modules['velocity'],
              typeId='example_velocity', engineType=99,
              label='EXAMPLE VELOCITY')
registry.register(module)
```

It immediately provides the same generic velocity rail, units/default and draft
semantics. This is a **contract extension test**, not a new shipped processor: type
99 remains rejected by the native host until an audited adapter exists. A real new
module registers its descriptor and a native adapter with event, reset/panic and
migration hooks; the editor needs no bespoke page. Stateful timing processors also
need scheduler/ownership tests before becoming creatable. Descriptor registration
must not be mistaken for proof that arbitrary processors can safely run or persist.

Future HUMANIZER requires a timestamped ownership queue; VELOCITY CURVES requires
separate response and AMOUNT mapping curve identities. Their specifications from
#11/#12 were inspected; neither is silently substituted by these descriptors.

## Tests

`python tests/test_module_registry.py` checks conversions, extension registration
and invalid metadata. `tests/test_headless_mvp.py` additionally checks independent
Transformer transactions, audible MIDI pitch results, held Note Off ownership,
bypass/reorder/delete, stateful duplicate restrictions, SAVE/LOAD and atomic routing.
`tests/test_headless_editor.py` checks actual browser draft dismissal and stale edits.
The unchanged native REAPER suite remains required for integration.
