# M5 native Conductor actions (draft PR #103)

This branch is stacked on PR #99. No deployment or merge is included.
The frozen REAPER JSFX is unchanged; native generation declares the existing
STOP/PANIC helpers before the new bounded dispatcher.

## Supported subset

Non-MASTER ACTION layers accept PRESS, HOLD, LONG_HOLD, RELEASE, or SUPERCHARGE_RELEASE. These map to the existing native Conductor phases 0–4 respectively; the dispatcher runs only when the selected phase is applied. This uses the same gesture and charge lifecycle as PHRASE and MOVEMENT layers. STOP targets a phrase, a mute
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
and legacy traversal migration remain subsequent work.

## Switch creation and editor

New switches created through the Web receive one empty Conductor step. Existing
switches, sources and shared phrase/controller settings remain unchanged. Both
schema 7 and schema 8 patch layouts are supported without editing the frozen JSFX.
The dedicated Conductor editor offers ACTION blocks on non-MASTER layers, with
explicit action, trigger and destination fields.

An existing utility preset may replace only the exact empty default Conductor,
after the normal preset preview. Authored steps remain protected. This compatibility
path retains the existing utility executor: automatic migration of legacy traversal
and gesture behavior is not yet proven equivalent. A failed library write restores
the previous native configuration; guarded captures prevent activation during play.
If native rollback is refused, its recovery journal is retained and failure is
reported, rather than claiming successful restoration.

## Reproducible isolated validation

GitHub Actions run 39745792263 passed on head commit
13147f88be682c98b579c4f60acdd877b47b8188. Updated phase tests exercise ACTION dispatch at LONG_HOLD, RELEASE, and SUPERCHARGE_RELEASE and confirm those actions do not fire on PRESS. The workflow built pinned ysfx and the
real generated engine without a JACK daemon, Zynthian service, saved user patch
or musical port. It passed the HOLD/group-zero ownership regressions, typed
native action tests, switch creation and preset rollback tests, legacy contracts,
and the recovery browser test. The workflow captured and automatically audited
the native editor at 320×240, 800×480, 1366×768, 1440×900 and 1904×1032.

The screenshot files are retained in the
`m5-real-native-screenshots` workflow artifact for that run. They have not yet
been manually inspected or committed as repository PNG evidence, so visual
qualification remains pending. Physical performance and Zynthian qualification
also remain pending. This is a tested first slice, not completion of M5
unification.

The PR50 ARP fixture predated already-shipped modes. The regression pins all 13
existing modes while preserving the original three indices; production ARP
behavior was not changed.
