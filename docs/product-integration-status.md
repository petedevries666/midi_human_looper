# Product integration status

Application: **MIDI BAD MOTHER FUCKER**. Modules are independent MIDI pedals;
controllers and snapshots are shared performance infrastructure within one patch.

## Dependency order

Main already includes PRs #19–#24 (headless host, descriptors, controller policy,
controller integration and chronological JACK output). PR #27 adds opt-in native
Zynthian chain transport without changing REAPER's free-time engine. PR #29 adds
Controller-owned external morphing; PR #30 builds the Snapshot manager on it.
The integration branch joins #27 with #29/#30, resolves native command collisions,
and validates the complete combination before proposing it for main.

PR #25 is a HUMANIZER mathematical/descriptor foundation, **not playback**.
PR #28 is a bounded scheduler foundation, **not a playable ECHOCITY module**.
Neither is needed to record and loop phrases or to use existing Transformers.
Do not enable or advertise either effect merely by merging its infrastructure.

## Existing processing restrictions

The JSFX engine preserves legacy fixed processing stages for older single-instance
patches. Stateless duplicate Transpose/Range instances opt pitch processing into
visible serial order. Velocity multipliers run before Polyphony/ARP; ARP is a
terminal note generator and CC MOD is a separate controller-emission stage.
Consequently the editor must not promise arbitrary pedal ordering around ARP,
Polyphony or delayed effects. At most one ARP and one Polyphony module per
Instrument is currently supported. Future scheduler continuations must preserve
those ownership constraints or explicitly reject unsupported placements.

There are at most eight Instruments, six Transformers per Instrument, sixteen
phrases, sixteen logical Controller sources and thirty-two Controller mappings.
Native Zynthian processors have independent memory, sockets, patch directories
and JACK ports. Synchronization uses JACK transport; phrase storage is never shared.

## Hardware qualification

Automated desktop JACK routing, real EEL2 execution, HTTP/WebSocket and Chromium
checks are software tests. The Zynthian adapter test stubs only the physical UI/base
classes and creates three actual native MIDI processors on a dummy JACK graph.
No Raspberry Pi, stock Firefox, Helix, native Zynthian UI or audible-synth acceptance
is claimed. Native loops initially support two bars of fixed 4/4; tempo changes and
transport seeks stop safely instead of silently retiming recordings.

Use [native installation and rollback](zynthian-native-chains.md), then the three
Piano/Bass/Synth hardware protocol in that document. Review experimental and draft
capabilities before choosing an integration revision; do not use all open branches
as a presumed release.
