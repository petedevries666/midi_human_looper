# Conductor entry/exit and step-advance audit

## Status

Design proposal only. This PR does not change runtime behavior, patch data, or the Zynthian installation. It records an audit and a candidate model for a later implementation PR.

## Problem to resolve

The Conductor currently combines several ideas that need explicit boundaries:

1. **Block entry**: when a Phrase, Movement, or Action layer starts responding to a gesture.
2. **Block exit/release**: what an already-running block does when the gesture is released.
3. **Step progression**: when the Conductor selects or starts the next horizontal step.

These are related but are not the same control. In particular, the current switch-level RELEASE advance defers step admission until release. That differs from “start this step on press, then advance on release.” We must not silently treat those as equivalent.

## Proposed mental model

- **Layers are simultaneous.** Blocks placed on different layers in the same step may have different entry triggers and can overlap. Example: Phrase on PRESS, Movement on RELEASE.
- **Horizontal steps are sequential.** Use successive steps for movements or phrases that should happen one after another. A second layer is not a later point on the timeline.
- **Each block owns its entry trigger and, where meaningful, a type-specific exit policy.**
- **The Conductor owns step progression.** A global or per-switch progression policy determines when a step is selected/launched; it does not implicitly define the release behavior of every block.
- **One physical release may produce multiple effects.** Define deterministic ordering between block release handling and Conductor progression, and reject or explicitly resolve conflicting combinations.

## Candidate block model

### Entry trigger

Retain the existing gesture vocabulary where supported: PRESS, HOLD, LONG_HOLD, RELEASE, and SUPERCHARGE_RELEASE. Trigger recognition stays separate from the block’s playback mode.

### Exit policy, constrained by block type

Do not offer one misleading universal “release mode.” Present only meaningful policies for each block kind.

- **Phrase:** continue to its natural end; stop on release; optionally hand off to an explicitly selected next step after completion. A phrase’s natural completion and the switch release are distinct events.
- **Movement:** stop at the current value; return to its configured neutral/start value; or transition toward an explicitly defined destination with a duration/curve. Movement ONCE/LOOP/PING-PONG remains its playback mode, not an exit policy.
- **Action:** one-shot actions remain fire-and-forget. A release-triggered action is a separate entry event; do not invent a persistent exit for actions unless an action type explicitly needs one.

Names and exact options require a compatibility audit before becoming patch schema.

## Step progression needs an explicit contract

Keep the current behavior named **DEFER START UNTIL RELEASE**. Audit whether a second mode should be added:

- **START ON PRESS, ADVANCE CURSOR ON RELEASE:** play the current step on press; release selects the next step, which starts on the next press.
- **START NEXT STEP ON RELEASE:** play the current step on press; release both advances and launches the next step.

The second mode could make a press/release pedal behave like a phrase envelope across steps, but it can also overlap with block release actions. The UI should state whether release only selects the next step or launches it. Do not change the default until this contract and its compatibility behavior are tested.

## User-facing examples to preserve

1. Same step, two layers: Phrase enters on PRESS and Movement enters on RELEASE. They are independent and may overlap.
2. Sequential movement: Movement 1 is on step 1 and Movement 2 is on step 2; choose the step progression policy to determine when step 2 is selected/launched.
3. Phrase on PRESS with “continue to natural end”: releasing the pedal does not truncate the phrase.
4. Movement on HOLD with “return on release”: release initiates a configured return; step progression is independently selected.

## Audit and implementation checklist

- Inventory Phrase, Movement, Action, Smart Switch, and Conductor event paths; document which currently receive press, hold threshold, long-hold threshold, release, and supercharge release.
- Trace phrase natural completion, stop, movement completion, and movement retrigger separately from gesture release.
- Specify same-tick ordering for block exit, release-triggered blocks, and step progression.
- Check multiple layers, mute groups, simultaneous notes/controllers, step 1, wraparound, HOLD at the first step, cancellation, and retrigger.
- Define schema defaults and migrations so existing patches retain their exact behavior.
- Validate UI labels against engine semantics; distinguish “advance cursor” from “launch next step.”
- Add deterministic native tests for the event matrix before changing playback behavior.
- Run patch round-trip/legacy tests, then isolated MIDI/JACK verification. Hardware listening is a separate qualification; do not infer it from CI.

## Out of scope

- No ECHOCITY changes.
- No runtime implementation or patch migration in this design PR.
- No Pi deployment.
