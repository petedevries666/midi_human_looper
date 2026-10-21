# M5 native Conductor actions (draft PR #103)

This branch is stacked on PR #99. No deployment or merge is included.
The frozen REAPER JSFX is unchanged; native generation declares the existing
STOP/PANIC helpers before the new bounded dispatcher.

## Supported subset

Non-MASTER ACTION layers accept PRESS or HOLD. STOP targets a phrase, a mute
group or all phrases. RESET_CURSOR and RESET_SHUFFLE_BAG target a switch.
STOP_RESET targets a switch (global phrase stop, then that cursor reset).
PANIC targets all phrases. PAUSE/RESUME remain preserved configuration but
explicitly unsupported for execution; no fallback or automatic legacy migration.

Targets resolve during compilation. Missing targets and unsupported actions
reject the whole step before any note admission. Maximum 32 action records per
step. Source/group STOP runs before new admissions and preserves unrelated
owners. Existing capacity preflight remains conservative: a STOP does not grant
extra admission slots in advance. Layer 01 remains PHRASE or EMPTY; an ACTION
never becomes MASTER. Other-switch resets do not invoke that switch.

Global STOP, STOP_RESET, PANIC and self-reset must be alone in the step, including
across gesture phases. These helpers clear pending gestures; allowing a PRESS
barrier beside a HOLD layer would silently discard that layer. Conflicting
steps are refused, not partially executed. Arbitrary MIDI, recall, pause/resume,
legacy traversal migration and editor controls remain subsequent work.

## Reproducible isolated validation

GitHub Actions builds pinned ysfx and the real generated engine on Ubuntu;
no JACK daemon, Zynthian service, saved user patch or musical port is used.
Run scripts/once-retrigger-test.sh and scripts/m5-hold-wrap-test.sh.
The latter tests real MIDI switch edges, five steps with independent group-zero
HOLD re-entry, exact final shared-owner Note Off, STOP/PANIC/reset, targeted
STOP followed by a fresh attack, held-pedal timing, conflicts and missing targets.
Direct EEL calls outside an audio block are not used as MIDI output evidence:
the host clears that output at the next processing block.

Final code validation: GitHub Actions run 39587720213 on commit
 a0b7455b38a8dbbf74a72b64fa9792f07713ebcb passed:

- 397 native PR #99 ownership/retrigger/lifecycle checks.
- 110 five-step HOLD/group-zero wrap checks; terminal STOP trace [[130,48,0]].
- 116 actual native action checks, including cross-phase barriers/missing targets.
- 24 real native persistence tests and 5 legacy source/parameter tests.

The PR50 ARP fixture predated already-shipped modes. The regression now pins
all 13 existing modes while preserving the original three indices; production
ARP behavior was not changed. Physical performance and editor qualification
remain pending. This is a tested subset, not completion of M5 unification.
