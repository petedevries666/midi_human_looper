# Native chain timing v2

Dependency: #30 → #34 → #37 → #38 → this correction. No prerequisite merge is
required to review the stacked implementation.

Version 1 remains the native command-line default and the fallback for existing
`install.json` files. Its rounded-block two-bar grid is preserved for old patches.
New installations write `chain_timing_version: 2`; the Zynthian adapter passes
`--chain-timing 2`. API state reports `chainTimingVersion`. Unknown versions fail
startup. Standalone REAPER/free-time semantics and schema-7 payload addresses are
unchanged. Configuration selects the execution version; it is not inferred from
MIDI content or silently changed when loading a patch.

V2 uses `round(sample_rate * 480 / BPM)` samples for two 4/4 bars: at most half a
sample of duration error, independently of audio buffer size. Playback starts
from the exact transport frame modulo that length. The existing EEL playback
segment loop emits events across in-buffer wrap boundaries, retaining offsets.
Record arm can start inside a block; input capture is gated to the half-open
musical window. Attacks outside it and releases without a captured attack are
excluded; captured notes crossing its end receive the existing bounded closing
release. Capture state is runtime-only and preallocated. GUI scratch, normal
REAPER overdub and the existing scheduler are not duplicated.

Tempo changes/transport seeks still cancel safely rather than silently stretching
recorded source data. V2 does not implement variable meters or transport chasing.
A v1 portable loop whose length differs from a v2 grid is rejected explicitly by
the existing activation guard. To preserve the old performance select version 1;
to opt into v2, create/record or deliberately import a phrase on the new grid.
No automatic retiming or truncation is performed. Back up configuration and patches
before changing execution version. All processors intended to synchronize must
use the same version/rate/tempo contract.

Validation includes actual shared EEL playback and capture at nonaligned boundaries,
three rates (44.1/48/96 kHz), buffers 128/256/512/8192 and tempos 73/120/137 BPM.
The three-processor dummy-JACK probe now injects MIDI at in-buffer boundaries,
instead of assuming the musical origin is always a block start. Run the combined
suite with the normal build commands. Run `CHAIN_TIMING_VERSION=1` with
`tests/test_zynthian_chains.py` to qualify legacy adapter execution too.

Physical qualification remains required: real REAPER, Raspberry Pi JACK settings,
Zynthian graph, Helix, port disconnection/reconnection, CPU/RSS and playable latency.
Cloud 8192-frame functional tests are not low-latency performance certification.
