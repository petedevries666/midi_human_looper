# VELOCITY CURVES with modulatable AMOUNT

**Status: specification / design PR, no MIDI engine code yet.** Defer implementation until the current dynamic Transformer/instrument work is integrated; audit merged code first.

## Concept

A VELOCITY CURVE module remaps incoming Note On velocities through the project's **existing shared multipoint curve editor**, including editable points and segment bends. A separate **AMOUNT** parameter continuously blends between unmodified input velocity and the curve-processed result. AMOUNT is itself assignable to an existing expression controller with its own response curve.

**Critical distinction:** the curve editor defines *how velocity is reshaped*; AMOUNT controls *how much of that reshaping is heard*. Do not confuse the curve for the velocity response with the expression mapping curve assigned to AMOUNT.

## Formula

For Note On input velocity v in 1..127:
- Normalize x = (v - 1)/126.
- Evaluate the editable velocity response curve f(x), clamped to [0,1].
- Compute processed velocity p = 1 + 126*f(x).
- Let a = clamp(AMOUNT, 0,1).
- Output velocity = clamp(round(v + a*(p-v)), 1,127).

Thus AMOUNT=0 is exactly transparent; AMOUNT=100% applies the complete curve. Values between interpolate **per note**, not by morphing the curve control points. Note Off velocity is left unchanged. Note On velocity 0, if encountered, retains MIDI note-off semantics, not a new Note On. Preserve original MIDI channel/pitch/note ownership.

Suggested default response curve: linear identity, with optional presets SOFT, HARD, COMPRESS, EXPAND, INVERT, and user-defined multipoint/bends. Default AMOUNT=0 or identity curve for backward-safe bypass; UI should make a useful preset one click away.

## Placement

Prefer an **INSTRUMENT-level VELOCITY CURVE Transformer instance**, since it shapes playing dynamics for a particular destination. Optionally evaluate a PHRASE-level variation later if requested, without duplicating the engine now. If multiple instances are supported, each owns independent points, bends, AMOUNT, expression assignment and stable instance ID. Existing velocity multiplier and other velocity processing must have explicit documented processing order.

## User interaction

- ADD TRANSFORMER → VELOCITY CURVE.
- Compact module shows a preview of its velocity response and a full-width AMOUNT rail with numeric 0..100% value.
- Click response preview / EDIT CURVE opens **the existing multipoint/bend curve editor**. Reuse editor gestures, constraints, redraw isolation, popup dismissal and existing curve evaluation where appropriate, rather than creating a different widget.
- Right-click AMOUNT → existing expression controller assignment (NONE or named controllers), with immediate opening of its *separate* expression mapping curve. Left-click an assigned AMOUNT rail reopens its mapping curve.
- Label editor clearly **VELOCITY RESPONSE** vs **AMOUNT EXPRESSION**, avoiding editing the wrong curve.
- Manual AMOUNT remains adjustable when unassigned. NONE retains the last effective AMOUNT, consistent with existing parameter UX.
- Consider a visible mini-preview of the *effective* curve at the current AMOUNT, while keeping the stored base response curve unchanged.

## Architecture and safety

- AMOUNT is a continuous target in the existing expression assignment model, not a new controller source.
- Audit parameter target addressing: v1.21 docs identify targets by instrument/type; the modular instance PR changes this. Bind AMOUNT to **stable instrument ID + Transformer instance ID + parameter ID**, not screen row or Transformer type alone.
- Reuse the project's parameter apply and GUI/audio isolation pattern; never let GUI redraw write MIDI engine state or share mutable scratch with @block.
- Compute velocity at Note On, once per event at the chosen chain stage. A changing AMOUNT affects **future Note Ons only**; do not retroactively rewrite sounding notes or Note Offs.
- Do not randomize timing or velocity here; HUMANIZER is separate.
- Ensure no accidental extra MIDI messages, channel changes, or Note Off mismatch.
- No unbounded allocations, no blocking or heavy UI work in real-time processing.

## Persistence

- Versioned JSON patch schema extension with backward-compatible migration, including per-instance response points/bends, AMOUNT, expression assignment, and expression curve.
- Default disabled/identity for old patches. Respect frozen legacy phrase/bank memory offsets and companion Lua daemon validation.
- SAVE/LOAD, patch banks, REAPER restart, instance duplication/removal, and controller reassignments must roundtrip without cross-instance leakage.
- Ensure compatibility with future headless Zynthian engine and Firefox UI through parameter/curve data rather than JSFX gfx-specific serialization.

## Acceptance tests

1. AMOUNT=0 yields exactly original velocity 1..127, regardless of response curve.
2. AMOUNT=1 yields mapped velocity, clamped to 1..127.
3. AMOUNT=0.5 yields the midpoint of input and mapped output, with documented rounding.
4. Identity curve is transparent for any AMOUNT (allow only documented rounding).
5. Velocity=0 Note On is interpreted as Note Off and never transformed into a sounding note.
6. Curve endpoints, multipoint bends, inversion, flat and steep sections are deterministic and bounded.
7. Expression assignment modulates AMOUNT smoothly and independently of the response curve; NONE preserves last value.
8. Two VELOCITY CURVE instances retain independent curves, AMOUNT and assignments.
9. Correct order and composition with existing velocity multiplier, velocity Transformer, ARP, VEL DECAY and future HUMANIZER.
10. Patch migration, SAVE/LOAD, both banks, REAPER restart and note lifecycle regression tests pass.

## Implementation handoff to Codex

After current modular PRs land: audit actual JSFX, Lua daemon, JSON schema, expression editor, instance storage and test harness; propose minimal schema/parameter changes; implement in a separate code PR with automated tests. Do not merge automatically. This PR only records the design.
