# Velocity Decay Pitch Bias: implementation checkpoint

Not a delivered performance capability yet. `phrase_velocity_decay_gain` in the
shared EEL source implements and tests the response contract but is not called by
playback. Existing patches therefore still execute the exact previous code.

For source pitch p, pivot c and normalized bias b, use
`d=(p-c)/(24+abs(p-c))`, `e=2^(-2*b*d)` and gain `rate^(repeatCount*e)`.
Zero bias and the pivot explicitly use the unchanged `pow(rate,repeatCount)`.
Positive bias reduces decay above the pivot; negative bias favors notes below it.
The response has no split and is continuously monotonic. A 24-semitone distance
gives half the limiting response; the exponent stays between 1/4 and 4 for valid
inputs. It cannot amplify a valid legacy decay ratio. Velocity rounding/clamping
must remain at the existing sounding Note On output; releases remain untouched.

Next coding step: append a versioned **33-cell schema-8 section**: one extension
marker, 16 pivot values (default 60), 16 normalized bias values (default 0).
Allocate live and both slot banks outside existing configuration/runtime storage.
Extend `payload_addr` and `project_bank_addr`; migrate schemas 1–7 with neutral
defaults. Keep the existing instrument-section marker at 7: it describes that
section, not the new whole-patch schema. Merely changing `IO_SCHEMA` would
invalidate existing instrument banks.

Update native PatchModel schema sizes/validators, Lua slot codec, REAPER project
serializer/bridge and portable carrier. Portable v1 requires exact schema-7 data:
retain its reader and explicitly version new exports; immutable old revisions
and hashes must not be rewritten. Test old schema-7 import preserving every value,
neutral defaults, new slot/RPP round trips, portable old/new materialization and
explicit refusal by older hosts.

After migration passes, add descriptor identities 25/26 for pivot/bias; extend
generated bounds (currently fixed at 25 kinds), phrase target resolution,
Controller validation, Snapshot capture/application and web editing. Pivot is
0–127 integer; bias -1..1 displays percent. Put note name/number and bias in
compact phrase options, preserving the required main row. Reuse existing owners
and policies; no new controller system or scheduler.

Snapshot ratio, repeat count, pivot and bias per ONCE voice at trigger time.
Apply the helper only to sounding Note Ons using recorded source pitch;
overlapping voices retain their own trigger-time settings/count. Keep retrigger
and reset conditions. At zero bias retain the old cached gain path exactly.
Add actual MIDI-output tests for pairing, timing, first pass, reset, independent
phrases, overlap, controller/snapshot changes and SAVE/restart/LOAD. Only then
mark Pitch Bias implemented in the capability matrix.
