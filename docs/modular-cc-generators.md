# Modular UI rollout, stage 1: CC MOD generators

The first PR implements ADD TRANSFORMER dismissal and independent CC MOD
instances. General note transformer instances, dynamic Smart Switches and dynamic
Instruments remain separate stages of the requested rollout.

## Playing and editing

ADD TRANSFORMER offers CC / MOD even when another CC / MOD exists. Up to six
transformer blocks fit in an instrument's existing six-slot engine collection;
other transformer types share that capacity. Every added CC block has its own
CC number, amount, bypass state and stable creation ID. Additional CC instances
also expose OUT CH: 0 follows instrument routing; 1–16 overrides it. The first,
legacy CC instance keeps its existing instrument routing controls.

Both amount and CC-number rails support independent expression assignment,
multipoint curves, bends, immediate curve opening and inline previews. Removing
an instance closes its open curve. A replacement receives a fresh ID and default
configuration, so it cannot inherit an old expression assignment accidentally.

The ADD popup closes with ×, Escape, or either outside mouse button. It also
closes after selection. Dismissal consumes the entire input frame. OPTIONS and
expression-controller assignment popups support the same outside mouse buttons;
OPTIONS continues to cancel unfinished MIDI Learn on dismissal.

## Routing and conflicts

CC MOD generates controller events independently; it does not process incoming
Note On/Off events in a serial chain. Generation order is instrument order, then
visible block order from left to right. Identical CC/channel targets are allowed
and show an orange warning in the selected editor. The last active writer wins.
If any writer changes, the entire matching group emits again in order. Removing
or bypassing the final writer restores its predecessor on the next audio block.
Unchanged groups do not continuously send redundant events.

A removed, bypassed or rerouted CC64 instance releases sustain on its saved old
channel. Remaining writers then restore their configured destination state. CC
removal/bypass does not trigger blanket Note Offs for unrelated playing notes.
CCs other than sustain have no universal reset value; removal leaves the receiving
instrument's last value unless a remaining writer restores it.

The existing note processors are unchanged: transpose, range filtering, velocity,
polyphony and arpeggiation use their established fixed stages and per-instrument
state. Their visual order has never selected a serial chain. Multiple ARPs cannot
be enabled safely by merely drawing duplicates: held-source tables, active-note
state and Note Off ownership currently belong to the instrument. A later general
instance PR must introduce explicit routing and per-instance ownership first.

## Persistence

Schema 4 appends a CC configuration extension after the complete schema-3 wire
payload. All legacy working RAM, expression data, Smart Switch data and internal
bank addresses retain their values. New internal banks and runtime caches live
after the existing TIME DECAY voice factors. The extension contains a next-ID
counter, legacy CC IDs, and fifteen additional CC records (five per instrument),
including channel overrides and two complete expression curves per record.

Legacy schema 1, 2 and 3 patches remain loadable. Existing legacy CC parameters
retain their routing and curves, and receive deterministic instrument-scoped IDs
on migration. Replacements use the patch's monotonically increasing ID counter.
SAVE includes the extension in its DSP snapshot and in both internal patch banks.
The updated companion Lua daemon supports schemas 1–4 and advertises version 4.
Install the JSFX and Lua updates together; older daemons reject schema 4.

These changes do not serialize runtime note state and do not move phrase events.

## Validation

The native host tests operate the actual popup, create three CC instances, verify
CC74/71/1 and independent channels, expression curves and previews, last-writer
behavior (including updates, bypass and reorder), saved IDs, both banks, legacy
migration, removal and CC64 cleanup. Concurrent GFX/audio checks cover both the
original fixed state and extra instances with duplicate targets and open curves.
Lua tests round-trip schemas 1–4 and the native GUI SAVE snapshot.

Real REAPER/Helix verification remains necessary: add CC74/71/1, move each rail
or assigned pedal independently, save/reload, dismiss each popup, and remove a
sustain instance while ordinary notes are playing.

## Following stages

1. General transformer instances: explicit serial/parallel routing, per-instance
   note ownership, stateful bypass cleanup and existing-patch migration. Resolve
   ARP routing before permitting duplicate arpeggiators.
2. Dynamic Smart Switch collection: bounded engine storage beyond four, stable
   IDs, compact live cards, a single editor with DONE/Cancel draft semantics,
   isolated Learn, deletion and migration. Four legacy records also contain
   expression-channel metadata, phrase trigger channels and TIME DECAY; preserve
   these independently of switch deletion and list undo.
3. Dynamic Instruments: independent stable IDs and visible panels, add/remove,
   targeted note release and per-instrument runtime tables. Legacy arrays all
   assume three instruments, so adding GUI-only cards would not implement this.

Each stage needs a separately reviewable migration and runtime regression suite.

The subsequent review stages are implemented in stacked PRs: [stateless Transformer stacking](transformer-stacking.md), [dynamic Smart Switches](dynamic-smart-switches.md), [dynamic Instruments](dynamic-instruments.md), and [project/popup integration](project-persistence.md). ARP/polyphony duplication inside a panel remains deliberately restricted.
