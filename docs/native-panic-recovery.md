# Explicit native PANIC

Explicit PANIC accepts an old patch revision within the same engine session.
The engine-session guard remains mandatory. Other editing operations retain
their ordinary revision checks.

The JACK chain cleanup releases sustain, sostenuto and hold-2 (CC64/66/69), then
sends all-notes-off and all-sounds-off. Explicit PANIC additionally sends every
Note Off on every channel, including notes absent from its ownership tables.
The 2048-note sweep emits at most 64 events per callback, retains its cursor on
a rejected write, and contributes to pendingOutput until completely drained.
Ordinary XRUN recovery does not start this full sweep.

Web PANIC stays enabled during ordinary pending commands, bypasses the editor
command queue and invalidates older queued gestures so they cannot restart a
phrase afterwards. A request already executing is followed by the panic request.

Validation: standalone sweep coverage/budget/retry/restart test; real native
capacity regressions for HOLD phrase 128, stale-revision panic, wrong-session
rejection and expanded clear-patch. Actual live JACK verification observed 2128
messages written (80 channel resets plus 2048 Note Offs), no failed writes,
zero active notes and no remaining output. This is a short functional check,
not prolonged audio qualification.
