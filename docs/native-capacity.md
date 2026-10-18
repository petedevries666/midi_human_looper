# Native collections: 64 Smart Switches, 128 phrases

The native Zynthian editor exposes an **+ SMART SWITCH** button and an active
count out of 64. The four existing switches keep their identities and settings.
New switches start unassigned, so creating one cannot steal an existing MIDI
source. Allocation stops explicitly at capacity; it never overwrites a slot.

Phrases have 128 source slots. The page selector jumps directly to a range such
as 127–128. Recording, playback, HOLD/LOOP stopping, MIDI import/export,
parameters, snapshots and Conductor references use the same source IDs 1–128.
This raises source storage capacity; the existing limit of 12 simultaneous
independent phrase voices remains unchanged.

Each Smart Switch has one **TEST** button. Mouse/touch down and up, or keyboard
Space/Enter down and up, feed the native gesture recognizer. TAP, DOUBLE, HOLD,
LONG HOLD and charged RELEASE use the configured timing and INSTANT/CLASSIFIED
policy. Pointer cancellation, focus loss and hidden-page handling send release.
The browser does not schedule notes or infer a separate gesture. Test buttons
stay available while preceding edge commands are queued, permitting a double
tap. The native charge meter remains authoritative.

## Storage and compatibility

`headless/native_capacity.py` generates a native-only EEL variant from the shared
schema-7 engine. The shared JSFX and REAPER GUI remain unchanged. Zynthian uses
the variant only when `expanded_capacity` is enabled in its install configuration.

Schema 8 has a distinct payload size and marker. Its source event prefix,
per-phrase arrays and dynamic-switch allocation are enlarged. Extra phrase
timing, output policy and trigger-channel settings have an explicit appended
carrier. They do not alias another switch's configuration.

Schema 7 is copied by named allocation ranges into schema 8. Existing source
events, names, parameters, switch IDs and Conductor source UUIDs remain intact.
Only the legacy ALL SWITCHES sentinel changes from 16 to 64. Missing phrase
source identities 17–128 are added once and then saved with the patch. Schemas
1–6 first use the established migration in an ephemeral legacy worker without
JACK; the original input is preserved. Schema 8 execution/export to frozen
REAPER is explicitly refused rather than dropping native data.

Phrase and switch release/STOP overflow uses bounded per-slot flags, avoiding
32-bit mask truncation. Snapshot switch actions have dedicated storage for all
64 slots, separate from the native control ring. Snapshot parameter capacity is
2048, including the performance target pool, so that parameters of all 128 phrase sources can be captured. Runtime RAM
is allocated and OS pages warmed before JACK activation; no resizing or source
JSON parsing is performed by the audio callback.

## Validation

`HEADLESS_BINARY=/path/to/native-engine python3 tests/test_native_capacity.py`
starts private real native workers and a loopback HTTP editor with temporary
patches. It exercises slot 64, phrase 128, gesture edges, Conductor, charge,
recording, MIDI export, portable round trips, presets, snapshots, legacy
migration and invalid capacity data. It does not use JACK or a live patch.

Run the RELEASE/SUPERCHARGE regressions against the generated source too, using
`HEADLESS_SOURCE`, and validate the actual editor before deployment. These tests
qualify the native event path; they are not a physical pedal or prolonged audio
qualification.

The synchronous control worker uses eight request/reply queue slots. This avoids
reserving 64 large snapshot configurations per worker. Test workers must run
sequentially on the 2 GB Pi; concurrent capacity suites exhausted its memory.
Pending phrase descriptor edits use a separate 456-slot runtime region, clear of
the legacy voice cursors. A charged MOVEMENT also activates inherited patch charge
timing when it is the only charged block in the step.

Idle descriptor work is skipped until an edit actually becomes pending. Deferred
edits keep their pending flag until safe admission; the native snapshot regression
checks phrase 128 volume and mute restoration. This avoids a 456-slot idle scan.

Request queues copy the large snapshot configuration only for snapshot/patch
commands (5, 27, 42). Replies copy source details only when detailRevision is set.
Ordinary telemetry and MIDI requests carry scalar fields without megabyte copies.
The clear-patch regression covers all 128 sources and the factory four switches.
A 15-second real JACK idle observation after this change reported zero XRUNs;
this short observation is not prolonged performance qualification.
