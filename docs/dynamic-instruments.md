# Dynamic Instruments (v1.27.0)

ADD INSTRUMENT creates a full visible panel, initially disabled. Each panel owns
routing, name, volume, all fourteen primary expression targets and its six-slot
Transformer chain. The original three panels remain visible on old patches.
The engine admits eight panels, including deleted/reused legacy slots. This is a
bounded DSP collection, rather than an unbounded allocator in the audio callback.
A ninth addition is refused. The same deliberate single-ARP/single-polyphony
restriction applies within each panel; independent panels retain their own state.

Panels have stable creation IDs and sparse storage slots. Processing follows
visible panel order, then the visible Transformer chain order. Reusing a deleted
slot receives a new ID. Queued Transformer edits capture the instrument ID and
cannot edit its replacement. X opens a removal confirmation; outside/ESC cancels.
Removal runs in the DSP command queue, clears only that panel's input/runtime
ownership, releases its active output, and clears Smart Switch module actions
pointing to it. Other panels' phrase sequences and settings are retained.
Shared channel/pitch owners defer the physical Note Off until the last owner
releases it; unmatched passthrough has separate ownership storage.

Schema 7 appends configuration and both banks for the additional panels, their
IDs, expression curves and extra Transformer records. Every old configuration and
bank address, every old parameter ID, and schema 1–6 payload prefix remain frozen.
The pure address resolver reads immutable overflow metadata; GUI and DSP use no
shared scratch counters. Runtime ownership is separate from patch data.

Native tests cover addition, appended parameter identity, expression control,
serial Transformer stacks, independent CC output, removal, shared-pitch ownership,
stale commands after slot reuse, both banks, eight-panel capacity and dismissal.
The full previous Phrase/Smart Switch/CC/expression suite remains active.
REAPER/Helix acceptance on hardware is still required.

Follow-up lifecycle review: ONCE/HOLD voices snapshot enabled destination instrument
IDs and input channels when triggered. Removing/reusing a slot cannot route an old
voice's later Note Off into a newly created instrument. New panels join subsequent
ONCE/HOLD retriggers; live and LOOP routing remain available for new incoming notes.
New panels ignore source Note Off events for which they have no input owner.

Deleting a panel quarantines its outstanding physical releases separately from
playback. MIDI releases drain that quarantine before Learn/performance dispatch,
even while the panel is absent. This protects a replacement's freshly held note.
Missing releases expire after the established ten-second missing-release policy;
PANIC clears the quarantine. Deletion also clears pending Smart Switch module actions
so a reused slot cannot inherit an old bypass/enable command. Regression fixtures
cover same-phrase overlap across deletion/recreation, live overlapping releases,
absent-slot releases, Learn-consumed releases, timeout and PANIC sustain cleanup.

Patch LOAD cancels prior runtime voices before applying new phrase/configuration data, preventing an old playback cursor from replaying events from the new patch.

LOAD and explicit PANIC also clear old ONCE references and ARP/mono input ownership, preventing inherited held sources from sounding after the transition.
