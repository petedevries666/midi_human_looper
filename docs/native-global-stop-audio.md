# Native global STOP/PANIC audio deadlines

Global STOP previously ran a selective phrase stop, repeated interpreted clears
of expanded runtime banks and generated 2,048 EEL releases that the JACK host
discarded before sending its own channel safety. On the physical Zynthian at
48 kHz / 256 frames, three idle STOP requests caused three XRUNs; their control
round trips were 72.7–76.7 ms. Those round trips include socket scheduling and
are not callback timings.

The native JACK global path now invalidates voices and sends CC64/66/69/123/120
channel safety in the current callback. It retains the explicit PANIC's bounded
64-note-per-callback exhaustive sweep and write retries. Selective phrase stop
continues to use the existing live-note ownership logic.

Contiguous runtime clears use VM memset for standalone native operation. Global
clears coalesce transformer planes instead of scanning every instrument/owner
row. JACK preallocates and binds these runtime pages before activation, then
clears at most 262,144 doubles (2 MiB) per subsequent callback. EEL and new
commands wait until these pages are ready; incoming MIDI remains queued in order.
The current 128-phrase layout takes three callbacks, at most about 16 ms at
48 kHz / 256 frames, before a new attack can be admitted immediately after a
global stop. Ordinary playback and gesture timing do not use this gate. A running
grid recovery keeps its existing synchronous transport behavior.

REVEAL avoids target searches when a voice has no ownership token. Controller
release avoids mapping searches for unowned targets or performance-owned targets;
valid controller mapping IDs exclude both sentinel owner values.

No shared REAPER JSFX source or serialized patch layout changes.

## Physical validation, 2026-10-18

- A disconnected native JACK client loaded the resident source data and performed
  24 STOP/PANIC operations, half during phrase playback: zero XRUNs; maximum
  observed callback in the request windows 4.048 ms, against a 5.333 ms deadline.
- The independent deterministic JACK regression exercises phrase 128 in LOOP,
  ONCE and HOLD, global STOP/PANIC, source preservation, silent settled state,
  replay and an immediate STOP → PLAY. Its 12 timed stops had a 4.433 ms maximum.
- The Controller Engine's 164,245 synthetic-time checks, 579 host checks and
  production REVEAL ownership/takeover regression pass.
- The complete 24-case native capacity suite passed during development; the final
  binary also runs targeted capacity, real edge, Conductor, supercharge,
  exhaustive PANIC and global-stop replay regressions.
- After installation with exact source/Conductor restoration, twelve global
  STOPs and three PANICs on the actual musical client added zero XRUNs. JACK
  stayed at 48 kHz / 256 frames and was not restarted.
- A subsequent 118-second musical sequence still recorded 9 XRUNs during the
  phrase phase and 4 during a directly routed three-note Surge chord. Both idle
  phases and the direct single-note phase recorded zero. Average JACK DSP load
  stayed around 23–30%; this does not exclude brief deadline misses. These
  remaining XRUNs are not resolved or attributed to Surge by this STOP fix.

The JACK regression is opt-in and creates only its own disconnected MIDI client:

```sh
NATIVE_STOP_JACK=1 HEADLESS_BINARY=.build/midi-headless-engine \
  python3 tests/test_native_stop_jack.py
```

Set `NATIVE_STOP_BUDGET_MS` to add a hardware-specific callback-time assertion.
The test never starts/stops JACK or reads user patches. No five-size Web UI
capture is relevant: this change modifies no Web UI files. Short successful
measurements do not qualify prolonged performance or establish the cause of
unrelated intermittent XRUNs while a synth is playing.
