# Per-phrase TIME DECAY (v1.23.0)

PHRASES now shows **VEL DECAY** (the existing percentage control, unchanged) and a
compact **TIME DECAY ×ratio** rail underneath the velocity rail. TIME's center is
×1.00; left compresses event spacing and right expands it. The logarithmic rail
ranges from ×0.50 to ×2.00. Double-click it to reset that phrase to ×1.00.
Each of the 16 phrases has its own independent ratio.

## Playback and reset rules

TIME DECAY uses the existing VEL DECAY retrigger counter. On an ONCE/HOLD attack:

```
timing factor = time ratio ^ existing retrigger count
playback timestamp = original recorded timestamp * timing factor
```

The first trigger has count 0 and factor 1. Each retrigger of the currently active
phrase increments the shared count. TIME and VEL ratios are independent; changing
one does not change the other. Switching phrases resets the progression, as does
clearing the phrase. STOP/HOLD stop resets the next attack by clearing the active
phrase history. **Natural ONCE completion also clears that history**, exactly as
in the existing velocity-decay engine: a later ONCE attack starts at factor 1.
Progressive examples therefore require retriggers while an ONCE voice remains
active, or while HOLD remains latched. Clearing phrase data preserves its decay
settings, matching the existing VEL DECAY behavior.

LOOP uses the existing shared transport and does not use the VEL retrigger counter;
its playback timing and BPM/quantization behavior remain unchanged. No BPM-derived
clock is introduced for TIME DECAY.

For original note onsets at 0, 50, 100 and 150 ms, with no intervening counter reset:

| Ratio | Attack | Factor | Onsets (ms) |
| --- | --- | --- | --- |
| ×1.20 | First | 1.00 | 0, 50, 100, 150 |
| ×1.20 | Second | 1.20 | 0, 60, 120, 180 |
| ×1.20 | Third | 1.44 | 0, 72, 144, 216 |
| ×0.80 | First | 1.00 | 0, 50, 100, 150 |
| ×0.80 | Second | 0.80 | 0, 40, 80, 120 |
| ×0.80 | Third | 0.64 | 0, 32, 64, 96 |

## Timing safety

Each voice snapshots its factor when triggered. A later retrigger or slider edit
cannot move events already scheduled by an older voice. All timestamped events,
including Note On, Note Off and CC, use the same positive scaling. Note durations
and the voice's phrase-end time scale consistently. HOLD retains its established
behavior of ignoring recorded Note Offs until stop/choke.

Original event timestamps and phrase lengths are never modified. Scaling is applied
only in the existing bounded voice playback scan, without allocating an event queue.
Total voice factors saturate at **1/64 through 64**, with the logarithmic exponent
bounded before exponentiation. The existing 12-voice limit, ownership bookkeeping,
voice recycling, phrase-change choke and Smart Switch STOP/PANIC paths remain in
place. MIDI timestamp precision is limited to host samples; very compressed events
can share a sample, retaining their original emission order.

## Persistence

TIME ratios occupy formerly reserved schema-3 configuration fields 112–115 in each
of the four extension records (four phrase ratios per record). Existing schema-3
payload size and all earlier patch/bank addresses remain unchanged. Both internal
banks and external JSON save/reload preserve the values. Older schema-1/2 patches
initialize TIME to ×1.00; zero reserved values in older schema-3 patches also migrate
to ×1.00. The current schema-3 Lua daemon needs no change.

## Validation

Run `YSFX_SOURCE=/workspace/setup-tools/ysfx tests/run_host_tests.sh`.
`tests/time_decay_cases.hpp` checks actual MIDI sample offsets for the examples above,
scaled note durations and CC timestamps, independent velocity decay, unchanged
recorded data, phrase-change/natural-end/clear resets, frozen overlapping voice
factors, STOP/PANIC, finite progression limits, bank/JSON migration and double-click
reset. Existing Smart Switch, phrase Learn, recording/overdub and concurrent GUI/audio
regressions run alongside it.

For REAPER validation, record a staggered chord with a sufficiently long silent tail
and retrigger before ONCE completion, or use HOLD to retain the progression. Test
×1.20, ×0.80 and ×1.00, then switch phrases, stop, save/reload and double-click reset.
Verify the established natural-completion reset separately. Native host tests do not
replace live REAPER/Helix testing.
