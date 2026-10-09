# HUMANIZER: research and implementation design

Status: **research/design PR only; no DSP/MIDI code has been implemented**. This proposal must not interrupt the dynamic instrument/Transformer work. Rebase and audit the merged code before coding.

## Goal
Non-destructively randomize MIDI **onset timing** and **Note On velocity** at either:
- **PHRASE level**: playback effect on a stored phrase, affecting the phrase before routing to instruments;
- **INSTRUMENT level**: independent Transformer instance in that instrument's MIDI chain, affecting notes routed there.

A phrase can be played through multiple instruments, each with its own feel. The two levels may coexist, but must use independent stable seeds and avoid accidentally applying the same jitter twice. UI should make stacking clear.

## Hard invariant: attack at T=0
The **earliest note-on attack group at phrase timestamp zero** must remain at timestamp zero. If a phrase's first attack is later than zero, preserve its original timestamp rather than silently shifting it to zero: distinguish *phrase timeline origin* from *first note*. Notes at timestamp zero may form a chord; protect the whole simultaneous group so chord integrity is preserved. Preserve Note Off pairing and note duration by shifting corresponding Note Off with the same offset unless a separate, future duration feature is explicitly enabled.

For instrument-level live incoming MIDI there is no universal phrase T=0: provide a defined **first note of a newly triggered phrase/voice** anchor when metadata exists, otherwise use zero added delay for the first event of an identified gesture, and document the limitation for ungrouped live input. Do not promise identical anchoring semantics without phrase/voice identity.

## Proposed controls (per placement)
- ENABLE
- TIMING AMOUNT: 0–40 ms initial useful range, optional advanced larger range. 0 = bypass.
- VELOCITY AMOUNT: ±0–40 MIDI velocity units initially, 0 = bypass; clamp resulting Note On velocity to 1..127 (never create velocity zero Note On).
- FEEL: UNIFORM / GAUSSIAN (bounded Gaussian; exact ranges defined by tests).
- VARIATION: FIXED (repeatable each loop) / EVOLVING (new deterministic variation each loop, indexed by iteration).
- SEED: integer, editable; REROLL explicitly changes it.
- Optional later: timing bias early/late, correlated groove/drift, chord lock, accents. These are not required for first PR.

### Determinism
Generate per-note offsets from a stable hash of (patch seed, placement/instance ID, phrase ID or voice ID, original event identity, loop iteration if EVOLVING, independent timing/velocity stream ID). Avoid mutable global PRNG order so overlapping phrases, reordered instruments and unrelated events do not reshuffle earlier results. A changed amount scales the same underlying random value. No permanent edits to source phrase events.

## Timing, scheduling and looping
- JSFX MIDI output is sample-offset based; schedule Note Ons in a future-safe event queue across @block boundaries, not with negative offsets. Reference: https://www.reaper.fm/sdk/js/midi.php
- At phrase T=0, anchored first attacks emit exactly on trigger; all other notes must be **clamped to >=0** relative to that trigger. In v1, prefer clamping negative displacements at phrase start over wrapping into the preceding loop, which could sound *before* a newly triggered phrase. Document audible compression if near start.
- For looped phrases, distinguish *loop boundary* from *new trigger*. Preserve the protected original first attack at the start of every iteration by default. Delayed notes at the tail may spill into the next iteration; use absolute scheduled timestamps and per-voice iteration IDs to avoid dropping or duplicating notes. For early offsets near loop end/start, never schedule in the past.
- Keep chord note groups together by default (same original timestamp => same timing offset), except optional later 'loose chord' mode.
- Enforce stable ordering for coincident events and correct retrigger behavior; note-off-before-note-on policy for identical pitch/channel must be carefully designed for overlapping voices.
- Note On and corresponding Note Off must be tracked by **voice/event identity** rather than channel+pitch alone, so overlapping same-pitch notes cannot steal each other's Note Off.
- STOP, PANIC, patch switch, phrase deletion, module removal, retrigger choke and transport discontinuities must cancel pending events and release only owned active notes.
- Instrument-level HUMANIZER must integrate with existing Transformer order and note ownership, including ARP-generated notes: specify whether HUMANIZER is before or after ARP, expose order if stacking is supported, and test both.

## Placement architecture
PHRASE HUMANIZER applies before instrument fan-out, retaining a shared timing/velocity performance across routed instruments. INSTRUMENT HUMANIZER applies only to that instrument, optionally after other generators. Never alter original recorded events or other instruments. Both use common reusable timing/velocity algorithm but separate per-instance configuration and runtime queues.

### Interaction with TIME DECAY
Current v1.23.0 TIME DECAY scales ONCE/HOLD timestamps; LOOP remains unchanged. Proposed order: compute source event timing under phrase/voice TIME DECAY first, then humanizer jitter, with T=0 protection after both. Repeated ONE SHOT voices must have independent event IDs and not reseed unpredictably. Preserve existing VEL DECAY behavior: apply velocity decay before bounded humanizer variation, or explicitly document an alternative and test it.

## Patch and UI
- PHRASES: compact HUMANIZE button/section per phrase, TIMING, VELOCITY, FIXED/EVOLVING, SEED/REROLL, enable. Keep row compact.
- INSTRUMENTS: add HUMANIZER to ADD TRANSFORMER menu as independent instance, same controls and instance IDs.
- Extend versioned JSON patch schema additively, with migration and old-patch defaults disabled. Audit Lua companion daemon and RAM offsets before changes. No shifting frozen phrase storage.
- Zynthian future: same settings/seed algorithm must run without a browser and remain stable across patch reload.

## Acceptance tests
1. Earliest note-on group at T=0 remains exactly T=0 for 1000 seeds, FIXED and EVOLVING.
2. A first note at T>0 is not moved to zero; its behavior is explicitly documented.
3. Amounts zero are bit-for-bit MIDI transparent and add no latency.
4. FIXED: each iteration identical; EVOLVING: varies across iterations but deterministic for the same seed and iteration.
5. Same-timestamp chord attacks stay together; distinct notes can move independently.
6. Note On/Off matched, duration preserved, no stuck notes across loop boundary, overlap, STOP, PANIC, retrigger, module removal and patch switch.
7. No event sent with negative/out-of-block sample offset, no unbounded RT allocations, no blocking calls.
8. Per-phrase and per-instrument independence and stacked instance persistence.
9. Existing v1.23 TIME DECAY, VEL DECAY, ARP and Smart Switch regressions pass.
10. Save/reload and REAPER restart reproduce the same FIXED groove; old patches load unchanged.

## Prior art and sources
- REAPER official JSFX MIDI scheduling API: https://www.reaper.fm/sdk/js/midi.php
- Existing MIDI humanizer with stable seeded hashing and careful note-off management: https://github.com/salvolm84/MIDI-Humanizer
- Humanizer with learned correlated drummer timing/velocity distributions (potential future GROOVE mode): https://github.com/JakebGutierrez/wobblemidi
- Open-source timing/velocity/drift reference: https://github.com/vincerubinetti/midi-humanizer
- REAPER's existing JS MIDI Velocity and Timing Humanizer is a useful UX baseline, but this project needs phrase-aware T=0 anchoring and loop-aware ownership.

## Implementation sequence after current modular PRs
1. Audit current scheduler, event storage, Transformer ownership, schema, UI and test harness; confirm actual limits.
2. Implement pure deterministic jitter function and unit tests.
3. Implement phrase-level scheduling and note ownership with anchored first attack, then instrument-level Transformer.
4. Add persistence/migration, UI and integration tests.
5. Submit a separate **implementation PR** only once tested. This document PR is not that implementation.
