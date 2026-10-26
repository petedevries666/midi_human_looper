# Native HUMANIZER and VELOCITY CURVES

This PR connects the native expressive stream to routed MIDI output and adds an
editor per instrument. It does not change the frozen REAPER JSFX or the ECHOCITY
effect implementation.

## HUMANIZER

- Timing range: 0–2000 ms, with signed bias from −2000 to +2000 ms.
- Bounded Gaussian or uniform timing; FIXED draws repeat by instrument/channel or
  pitch, while EVOLVING draws include the routed onset and audio-block index.
- GROUP gives attacks on one channel a shared offset; NOTES gives pitches
  independent offsets. Simultaneous chord notes remain coherent in either mode.
- Velocity variation is an independent 0–100% draw.
- Negative offsets need explicit output lookahead. The same final output stream
  serves live input and phrase playback, so its chosen lookahead is added as
  latency to every routed source. If the resulting event would be in the past,
  it is clamped to the current sample. The default lookahead is 0.
- One offset is captured at Note On and reused for its Note Off, preserving note
  duration and Note-Off velocity. Voices are paired oldest-first for overlapping
  identical notes.

## VELOCITY CURVES

- Each instrument has a 1–127 input to 1–127 output response graph with up to 16
  points. Input X must increase; output Y can rise, fall, flatten, or invert.
- Linear interpolation is used between points.
- AMOUNT blends the original velocity with the curve result from 0–100%.
- Velocity-zero Note On is treated as a release; no zero-velocity attack is
  generated. Note-Off status and release velocity pass through the native voice
  ledger.
- HUMANIZER velocity variation runs before the response curve.

The Web editor offers SUBTLE, LOOSE and DESTROY starting presets, editable timing
controls, and LINEAR, SOFT, HARD, INVERT and GATE curve shapes. APPLY commits the
instrument configuration through the versioned schema-8 carrier. The same
carrier is retained by native patch save/load and patch copy.

## Runtime placement and limits

The stream runs after the native transformer and routing output has been built,
before the shared JACK output queue. It uses preallocated fixed-capacity voice
and due-event storage. Delayed events continue to render on later silent blocks.
PANIC, patch reload, module configuration changes and MIDI channel clear release
or clear owned voices. Queue failure enters the host's existing MIDI recovery
path; it does not knowingly leave a half-admitted pair.

At present, an instrument must use an explicit MIDI OUT channel 1–16 to identify
its post-routing stream. ORIGINAL output and duplicate explicit channel
assignments pass through unchanged because the final MIDI packet has no
unambiguous instrument identity in those cases. The engine exposes this via
per-instrument controls; physical Zynthian/Helix qualification remains necessary.

ECHOCITY itself is unchanged and remains disabled by default. When its runtime is
active, expressive processing sees its final output stream, so deliberate
HUMANIZER use can shift individual repeated notes. The effect's default behavior
is unchanged while both expressive modules are bypassed.

## Validation

- Native expressive C++ tests exercise deterministic timing, velocity boundaries,
  curve interpolation, live pairing, overlap, cancellation and channel clear
  against the real native scheduler.
- The Python patch-codec test validates round-trip and malformed patch carriers.
- GitHub Actions builds the strict C++17 core, runs ASAN/UBSAN and checks the
  editor syntax. The full DICKINSON engine workflow builds the actual engine.
- This PR has not been installed on Zynthian. Confirm musical feel, routing,
  controller assignment needs and callback load on the Pi before release.
