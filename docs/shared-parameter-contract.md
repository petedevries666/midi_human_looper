# Shared parameter execution contract

The catalog now generates the C++ parameter identity/count/range/conversion
contract and the embedded EEL bounds/scaling/normalization functions. No extra
REAPER deployment file or runtime JSON parsing is introduced. Run
`python3 scripts/generate-parameters.py` after intentional catalog changes; builds
and regression tests refuse stale generated artifacts with `--check`.

Stable engine kinds and the existing Controller/Snapshot switching policy are
preserved. CC NUMBER explicitly declares discrete snapshot switching. A/B is
marked continuous, matching existing native execution rather than imposing UI
step quantization on a Helix pedal. Equal-bin normalization now uses cell centers
in Python too, consistent with native conversion. Existing musical ranges,
positive-half rounding, logarithmic TIME DECAY and MIDI enum bins are unchanged.

The descriptor suite verifies generated identities, Python/C++ scaling and inverse
normalization including boundary inputs. The actual shared EEL harness compares
all 25 parameter kinds with C++ at ten positions, including either side of enum
boundaries. Existing GUI, phrase and Controller regressions remain required.

This is an executable normalization parity slice, not full Controller/Snapshot
parity. C++ still owns native takeover/token policy and snapshot scheduling;
REAPER still executes its legacy expression engine. Populated native extensions
remain preserved and refused by REAPER execution. Do not advertise complete
project parity until a shared ownership vertical slice is qualified on both hosts.
No HUMANIZER/ECHOCITY/Motion or new scheduler is introduced here.
