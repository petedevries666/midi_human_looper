# Zynthian SOLO restoration: isolated upstream candidate

Inspected upstream UI revision `37b776a126f48c2e214f016b081f1554513cbc24`.
No live snapshot was loaded, mixer value changed or service restarted.

## Root causes reproduced

In `zyngine/zynthian_engine_audio_mixer.py`, `set_solo(main, 1)` calls
`lib_zynmixer.setSolo`. The C implementation in `zynlibs/zynmixer/mixer.c`
treats the main strip as **clear all individual solos**, regardless of its value.
Python instead writes that input value into individual controller caches. It
also excludes the last individual strip with `MAX_NUM_CHANNELS - 2`.
Consequently the GUI/cache can show solo while the native engine is not soloed;
`get_state` persists those cached values.

`set_state` restores individual strips, then the main strip last. A persisted
main SOLO value is replayed as the clear-all command, defeating intentional
individual solos restored moments before. MBMF has no audio mixer strip, which
is consistent with the reported exception; no MBMF-specific solo setter is
needed to reproduce these upstream methods.

## Candidate and evidence

`zynthian/patches/m5-mixer-solo-state.patch` targets the inspected upstream source:
clear-all synchronizes all individual caches to zero, and snapshot restoration
does not replay the main-strip command. Individual saved solos and momentary
flags remain intact. This is **not** an UNSOLO ALL after-load workaround.

Run `python tests/test_upstream_solo.py PATH_TO_UPSTREAM_MIXER` on the original
and a separate copy with the patch applied. The test extracts and executes the
actual upstream `set_solo`, `set_state`, `get_state` methods with deterministic
controller and native-mixer adapters. Original: three failures. Candidate:
three passes. This validates Python restoration behavior against the inspected
C API contract, not physical audio, the complete controller implementation or
GUI event ordering. The patch is not installed or automatically applied by MBMF.

## Hardware qualification and compatibility

On a disposable test rig, save and restore (1) no solos, (2) one intentional
solo, (3) several solos including the final strip, (4) clear-all before save.
Compare `getSolo`, controller values, screen highlights and actual audibility.
Exercise MIDI momentary learn and partial ZS3 restore. Check notification order.
Keep the upstream file and snapshot copies for rollback before an approved test.

Old snapshots may already contain polluted individual cache values. They cannot
be safely distinguished from intentional solos: do not silently sanitize them.
Re-save only after the musician verifies the desired individual solo states.
The exact historical trigger of every user snapshot is not proven; this
candidate explains and reproduces the observed class of failure without claiming
the live system is fixed.