<div align="center">

# MIDI BAD MOTHERFUCKER

### Human timing. Machine memory. No grid required.

**A playable MIDI phrase instrument for REAPER and Linux / Zynthian.**

[![Status: experimental](https://img.shields.io/badge/status-experimental-orange)](#project-status)
[![REAPER](https://img.shields.io/badge/host-REAPER_JSFX-555)](#where-it-runs)
[![Linux / JACK](https://img.shields.io/badge/host-Linux_%2F_JACK-555)](#where-it-runs)
[![Zynthian](https://img.shields.io/badge/target-Zynthian-555)](#where-it-runs)

*Not another piano roll. A way to play with things you already played.*

</div>

---

## What is this thing?

**MIDI Bad Motherfucker (MBMF)** is an experimental, musician-led MIDI instrument built around **recording expressive phrases and triggering, transforming and combining them in real time**.

Play a chord, a bass figure, a cluster of notes, or an imperfect little accident. Keep its timing, velocity, controller gestures and personality. Then call it back from a MIDI footswitch, route it to another instrument, overlap it with other phrases, or shape what happens next.

The point is not to replace a DAW or force performances onto a timeline. It is to make **musical gestures reusable on stage** without sanding off the human part.

Think of it as a modular MIDI pedalboard: phrase memory, routing, note transformation, expressive controllers and performance logic in one instrument.

> **Design rule:** precision of musical intent, not compulsory quantization.

## Why it exists

A studio MIDI idea should not need to be rebuilt from scratch to become a live instrument.

MBMF grew out of a practical problem: composing and experimenting in **REAPER**, then wanting the same expressive MIDI material under footswitch control on a **Linux-based Zynthian**. A phrase should be something you can *play*, not just a rectangle on a DAW timeline.

This is a personal project, written around real rehearsal and performance needs. Its architecture is being developed in public, with reproducible regression tests and explicit compatibility boundaries.

## The building blocks

| Module | What it does |
| --- | --- |
| **PHRASES** | Capture and replay MIDI performances, including expressive timing, velocities and controller data. |
| **INSTRUMENTS** | Route and remap MIDI channels, apply velocity/CC controls, and build instrument-specific processing chains. |
| **TRANSFORMERS** | Stack note and velocity transformations; use range, transpose, polyphony and arpeggiator tools where supported. |
| **EXPRESSION** | Map controllers to parameters with independent ranges and editable multipoint curves. |
| **SMART SWITCHES** | Trigger musical actions from MIDI notes/CCs, with performance gestures and MIDI Learn. |
| **CONDUCTOR** | A developing STEP × LAYER system for arranging PHRASE references and, later, MOVEMENTS into playable sequences. |

**A PHRASE is a performance, not a quantized pattern.** Timing can remain free. Multiple MIDI channels inside a phrase remain meaningful.

### The idea in four presses

```text
                 SMART SWITCH
                       │
              PRESS → PRESS → PRESS → PRESS
                       │
             ┌─────────┴──────────┐
             │     CONDUCTOR      │
             ├──────┬──────┬──────┬──────┤
             │STEP 1│STEP 2│STEP 3│STEP 4│
             ├──────┼──────┼──────┼──────┤
  LAYER 1    │  C   │  Am  │  F   │  G   │
             └──────┴──────┴──────┴──────┘
                         │
                    MIDI OUTPUT
                         │
                 PIANO / SYNTH / BASS
```

This is the **target interaction** for the new CONDUCTOR work, not a claim that the complete workflow is released on `main`.

## Where it runs

### REAPER

The original instrument is a **JSFX** with a companion Lua/ReaScript workflow. REAPER is the fast experimentation and editing environment.

### Linux / JACK

A separate **native MIDI engine** and browser-based control interface live in [`headless/`](headless/). This path is being built for reliable Linux/JACK MIDI routing, state persistence and integration with other MIDI instruments.

### Zynthian

**Zynthian is the intended live hardware home**, initially on a V4 kit: MBMF as a MIDI tool in a chain, driving piano, bass and synth chains. Physical hardware performance and installation still need explicit validation. A desktop JACK test is not proof of Raspberry Pi real-time performance.

Start here:

- [Native Zynthian chain setup, test and rollback](docs/zynthian-native-chains.md)
- [First Linux/Zynthian test](docs/zynthian-first-test.md)

## Project status

**Experimental, actively developed. Not a packaged stable release.**

There are two important timelines:

**Existing project:** the REAPER JSFX, native Linux/JACK host, browser controls, patch compatibility work, Smart Switches, MIDI ownership and regression infrastructure already exist in different stages of maturity.

**Next-generation CONDUCTOR:** the new STEP × LAYER design is being built in **draft pull requests**, not silently treated as shipped functionality.

| Workstream | Status |
| --- | --- |
| Baseline and regression audit | Draft [#56](../../pull/56) |
| Independent MIDI instance / note ownership | Draft [#57](../../pull/57) |
| CONDUCTOR data model and atomic persistence | Draft [#58](../../pull/58) |
| CONDUCTOR musical execution | In development; do not assume released |
| MOVEMENTS, JOIN, REVEAL, FECK | Planned / specification stage |
| REAPER ↔ native CONDUCTOR execution parity | Not yet delivered |
| Physical Zynthian V4 / Helix validation | Pending |

The [master CONDUCTOR specification](../../pull/55) records the intended behavior. The [PR C technical notes](docs/conductor-data-model.md) describe what is actually implemented in that draft.

**Important:** PRs #56–#58 are stacked drafts. They are not evidence that `main` contains the entire new CONDUCTOR. Some legacy behaviors are intentionally retained, and known UI regressions are tracked rather than presented as passing tests.

## What makes it different?

- **Free-time first.** The phrase's original timing matters; a global clock is not mandatory.
- **Performance before programming.** The central interaction is playing and triggering, not drawing notes in a grid.
- **Independent musical layers.** Overlapping phrases should have explicit ownership of their MIDI notes, so one phrase cannot casually silence another.
- **Portable intent.** Studio composition and live execution should converge instead of becoming two separate workflows.
- **Modular by design.** Instruments, transforms, controllers and eventually MOVEMENTS are building blocks, not one giant fixed sequencer.
- **Failure is a feature to design for.** Stuck notes, stale references, patch migration, overload and rollback are first-class engineering concerns.

## Get the code

```bash
git clone https://github.com/petedevries666/midi_human_looper.git
cd midi_human_looper
```

**Choose the path you actually want to run:**

- For **REAPER**, start with the JSFX and companion Lua workflow documented in the [development history](docs/readme-development-history.md) and feature notes under [`docs/`](docs/).
- For **Linux / JACK / Zynthian**, follow the [first-test guide](docs/zynthian-first-test.md) and the [native chains guide](docs/zynthian-native-chains.md).
- To **review the next-generation CONDUCTOR**, read [PR #55](../../pull/55) and its stacked implementation PRs. Do not deploy a draft branch to performance hardware without reviewing its prerequisites and rollback procedure.

There is deliberately no magic one-line installer here: the project has multiple runtimes, evolving schemas and hardware-specific routing.

## Engineering notes

MBMF is not only a UI prototype. The native development process includes tests for MIDI behavior, persistence, JACK routing, browser controls, note ownership and failure cases. The current CONDUCTOR draft chain documents its evidence in the relevant PRs.

Useful starting points:

- [Smart Switches](docs/smart-switches.md)
- [Dynamic Smart Switches](docs/dynamic-smart-switches.md)
- [Transformer stacking](docs/transformer-stacking.md)
- [Expression assignments](docs/expression-assignments.md)
- [CONDUCTOR model, references and migrations](docs/conductor-data-model.md)
- [Original README / version-by-version development log](docs/readme-development-history.md)

## For Linux people

If you enjoy **JACK, MIDI routing, real-time constraints, state machines, old-school hardware workflows and making small computers behave like actual instruments**, this repository is very much your kind of rabbit hole.

Particularly interesting areas for review:

- deterministic MIDI Note On/Off ownership across overlapping instances;
- keeping configuration parsing and allocation away from the audio/MIDI callback;
- atomic patch persistence and schema migration;
- bounded event scheduling, overload handling and predictable failure;
- bridging a musician-friendly browser UI to a native Linux MIDI engine.

Issues, code review and reproducible bug reports are welcome. Please distinguish observed behavior on `main` from behavior proposed in draft PRs.

---

<div align="center">

**PLAY IT. KEEP IT HUMAN. TRIGGER IT AGAIN.**

*MIDI Bad Motherfucker is an independent experimental project, not affiliated with REAPER, Zynthian or the makers of any connected hardware.*

</div>
