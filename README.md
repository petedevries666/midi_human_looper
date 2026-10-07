# MIDI Human Looper

Experimental free-time MIDI phrase instrument for REAPER JSFX, designed through live playing rather than around a fixed sequencer workflow.

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
