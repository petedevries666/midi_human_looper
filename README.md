# MIDI Human Looper

Experimental free-time MIDI phrase instrument for REAPER JSFX, designed through live playing rather than around a fixed sequencer workflow.

For the native Zynthian Piano/Bass/Synthesizer prototype, see
[installation, chain setup, physical test and rollback](docs/zynthian-native-chains.md).

## Core vocabulary

- **Phrase**: a recorded expressive MIDI performance. A phrase may contain notes, velocity, CC, sustain, pitch bend and multiple MIDI channels. It can play as LOOP or ONCE.
- **Instrument**: a routing destination. It listens to ALL or one MIDI input channel and can preserve or remap the output channel. It also owns a velocity multiplier and CC baselines.
- **Expression A / B**: two modulation sources. In v1.4 they are visible mouse-test sliders. The long-term design is a mapping system where each expression source can drive several parameters with independent ranges.
- **Patch**: the complete playable state: phrases, instrument routing, expression mappings and performance settings.

## Design principles

1. Preserve human timing first. Quantization is optional and non-destructive.
2. Phrase data should eventually be exportable/importable as standard MIDI (.mid). Musical material must not be trapped in plugin state.
3. Same-phrase ONE SHOT retriggers may overlap. Retrigger velocity decay makes repeated footswitch presses behave like a human-controlled MIDI echo.
4. Triggering a different ONE SHOT phrase softly chokes the previous phrase group.
5. MIDI channels inside phrases remain meaningful. Do not flatten multichannel performances.
6. Keep the REAPER prototype fast to iterate, even while the eventual engine is intended to be portable to Zynthian/LV2.

## Patch compatibility contract (from v1.4.5)

During the v1.x REAPER prototype, the current serialized phrase/event and two-patch-bank memory layout is **frozen**. New persistent features must be appended or explicitly migrated; existing addresses must not be silently moved or reinterpreted.

Header field 9 now carries `PATCH_SCHEMA_VERSION = 1`. Projects saved with v1.4.4 and earlier contain 0 in that reserved field and are intentionally treated as legacy schema 1. This means an existing v1.4.4 REAPER project should reopen with its recorded phrases/patch banks intact after updating the JSFX to v1.4.5.

Before any future incompatible storage change, add a migration path first. Do not make musical material collateral damage of UI/engine development.

## v1.4.1

The 16 phrases remain available, but the GUI now shows only **6 compact phrase rows per page**:
- page 1: P1-P6
- page 2: P7-P12
- page 3: P13-P16

This keeps INSTRUMENTS and EXPRESSION controls reachable on smaller screens without abandoning the information-rich line layout.

## v1.4.0

- 16 phrase rows, still line-based by design.
- 2048 MIDI events maximum per phrase to keep the current JSFX memory architecture safe.
- 8 instrument routing rows:
  - enable
  - MIDI IN: ALL or 1..16
  - MIDI OUT: ORIGINAL or 1..16
  - velocity multiplier
  - Level baseline (CC11 concept)
  - Mod baseline (CC1 concept)
- EXP A and EXP B are mouse-testable and exposed as REAPER sliders.
- EXP A currently demonstrates instrument Level / CC11.
- EXP B currently demonstrates Mod Wheel / CC1.
- Quantize-grid slider range corrected to expose all six divisions.

### Important persistence note

Stock JSFX provides reliable project/preset serialization through `@serialize`, but it does not provide a clean general-purpose writable named-file API suitable for pretending we already have standalone patch files. Therefore v1.4 deliberately keeps REAPER serialization rather than shipping a fake/fragile external SAVE system.

The next persistence milestone should be a **versioned patch schema** that is independent from runtime memory addresses. Standard MIDI files should hold phrase performances; patch metadata should hold routing, modes, decay, expression mappings and other Human Looper-specific state.

## Direction

Near-term:
- robust versioned patch persistence
- MIDI import/export per phrase
- configurable expression mapping with min/max and response zones
- MIDI Learn for phrase triggers, mute/solo and expression sources
- per-instrument CC configuration
- targeted note release everywhere to avoid broad panic bursts

Example live use: six free-time chord phrases can be triggered from Helix footswitches while another performer uses Expression A to reveal velocity layers and progressively introduce another instrument such as Solina. No master tempo is required.

## v1.21.0 expression assignments

Right-click a transformer parameter (or instrument volume) to assign any of the
four named controllers. Assignment immediately opens its independent multipoint
curve editor; left-click an assigned rail to reopen it. NONE retains the current value and restores manual control.
ARP HOLD and ARP ON have separate assignments; ARP ON/OFF is available in the
shared editor header. Transpose, range, polyphony and ARP-enable changes wait for
held source notes to release so note-offs retain their original transformation.

Update both the JSFX and the companion Lua ReaScript, and restart the ReaScript.
Existing schema-1 JSON patches remain readable; new patches use schema 2 with an
appended expression extension. All old RAM offsets and bank addresses remain
fixed. The v1.20.1 baseline already uses external JSON rather than project
`@serialize`; the older project-serialization discussion above is historical.

See [the regression audit, migration contract and test instructions](docs/expression-assignments.md).

## v1.21.1 Transformer Editor UX

Transformer rails now match VOLUME's 18px height, with 34px row spacing. Assigned
rails display their own live multipoint/bend preview. Choosing NONE closes the
curve only when that parameter is displayed. MIDI processing and schema 2 are
unchanged; the v1.21.0 GUI/audio counter isolation is retained.

## v1.22.0 Smart Switches / Phrase Conductor

Four programmable momentary note/CC switches provide TAP, DOUBLE and HOLD actions,
64-position phrase-reference sequences, independent traversal and RESUME/RESTART
on section re-entry. Special actions include targeted module control, sequence
reset, phrase STOP and explicit global PANIC. Scroll below the expression editor
for configuration and MIDI Learn. Update both JSFX and the Lua patch daemon;
schema 3 reads existing schema-1/2 patches with switches disabled.

See [configuration, persistence, tests and live acceptance](docs/smart-switches.md).

## v1.22.1 Learn, popup, TEST and SAVE fixes

OPTIONS now closes with ×, an outside click or Escape. MIDI Learn has one exact
switch/controller target, consumes its capture event and offers explicit reassignment
for conflicts. FORGET clears only the selected MIDI mapping. TEST TAP / DOUBLE /
HOLD use the same action dispatcher even for disabled switches. SAVE waits for
pending switch edits before snapshotting the complete patch; update and restart
the Lua daemon for the patch-script compatibility indication.

## v1.23.0 Phrase TIME DECAY

PHRASES has an independent bipolar TIME DECAY rail (×0.50–×2.00, neutral ×1.00,
double-click reset). ONCE/HOLD voices scale original MIDI timestamps using the
existing VEL DECAY retrigger/reset rules. Active overlapping voices retain their
own factors. LOOP timing remains unchanged. The existing DECAY label is now VEL
DECAY. Settings persist with the current schema-3 patch system.

See [timing examples, reset rules and tests](docs/time-decay.md).

## v1.24.0 — modular UI stage 1

ADD TRANSFORMER can be dismissed without selecting an effect. Multiple CC MOD
blocks now have independent settings and expression curves; duplicate destinations
show a warning and use deterministic last-writer behavior. Save uses schema 4;
update the companion Lua daemon together with the JSFX. Old patches still load.

See [CC generator behavior and the following modular stages](docs/modular-cc-generators.md).

## v1.25.0 — stateless Transformer stacking

Multiple transpose, range and velocity blocks own independent settings and
expression curves. Stacked note processors use visible serial order; note-changing
edits wait for source releases to preserve Note Off pairing. ARP and polyphony
remain single-instance per instrument. See [stacking behavior](docs/transformer-stacking.md).

## v1.26.0 — dynamic Smart Switches

Compact cards replace the permanent four-switch panel. ADD/EDIT opens one draft
editor; DONE commits, while Cancel or dismissal discards edits and cancels Learn.
The engine and patch banks support sixteen independent switches with stable IDs.
See [workflow and persistence](docs/dynamic-smart-switches.md).

Dynamic Instrument panels and schema-7 compatibility: [implementation notes](docs/dynamic-instruments.md).

Project reopen and popup integration: [validation notes](docs/project-persistence.md).

## Zynthian / Linux headless first test

The runnable JACK MIDI host and reconnecting browser interface live in `headless/`.
Start with [the first-test guide](docs/zynthian-first-test.md); build/run/test scripts
are in `scripts/`. This preserves the REAPER JSFX. Physical Pi/Helix validation is
required; the desktop dummy JACK graph is a functional test, not a latency claim.
