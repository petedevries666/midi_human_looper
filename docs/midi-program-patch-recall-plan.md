# Planned MIDI patch and Zynthian snapshot recall

Status: design only; MIDI recall and the settings UI are not implemented by this
document. Target native Zynthian and Web only; preserve frozen REAPER legacy.

## User-facing contract

Global settings, stored outside musical patches and processor-specific runtime
folders, contain Program Change enable (default off) and one channel (1–16).
Program Change data byte 0 is ignored. Bytes 1–127 select identically numbered
patch slots: PC 1 selects PATCH 01. Controllers displaying wire byte 0 as program
1 need an explicit explanation in the UI; do not silently subtract one. Current
patch storage/API supports four slots, so capacity expansion is required before
promising slots 5–127. Unknown/unavailable slots leave the current patch intact.
Slot 128 would require a separately specified Bank Select convention.

Each patch optionally links one Zynthian full snapshot. Offer a deliberate
"Save patch + Zynthian snapshot" operation, with a proposed display name such as
"04 MONZTER" for patch 4 MONZTER. Never overwrite an unrelated snapshot with the
same display name. Persist a stable explicit snapshot reference plus patch identity
and pairing generation; matching a filename or title at recall time is unsafe.
Renaming a patch must preserve its association. Offer updating the paired display
name separately, and allow repairing or replacing a missing link.

MIDI recall supports patch-only and patch-plus-linked-snapshot policies. Enabling
linked recall must not create snapshots automatically. A missing paired snapshot
is an error before switching; do not silently open an empty patch or partial rig.
Manual Web LOAD of an empty slot retains its existing new-patch behavior; remote
MIDI recall must not replace an ongoing performance with a blank slot.

## Host integration and transaction

The installed Oram state manager already dispatches Program Change to snapshots
on its master channel and to ZS3/presets elsewhere. MBMF needs one authoritative
host-level dispatch before those handlers on its configured input/channel, with
matched recall messages consumed there. Ignore PC 0 on this reserved channel
without also selecting a synth preset. Other channels retain normal behavior.
Detect/report conflicting master-channel configuration; never apply two recalls.
Do not handle the same PC again inside the native MIDI engine.

Run orchestration in a host-owned control worker, outside the audio callback and
outside the editor/native processes that snapshot loading may replace. Keep global
settings and the pairing registry available across processor recreation. A request
has an identity, an explicit target and a lifecycle: preflight, stopping, snapshot
loading, waiting for engine/chains, patch restoration, relinking, ready or failed.

Before stopping, validate the patch and snapshot, their pairing metadata, engine
availability and restoration compatibility. Retain the previous runtime state and
snapshot reference locally for recovery. Stop owned notes and sustained voices
using the existing bounded panic path; prevent old queued performance commands
from entering a new session. No new attacks until restoration completes.

A full Zynthian snapshot includes MBMF state. Avoid restoring a stale embedded
patch over the selected saved patch: load the host snapshot, discover the new
engine session and control endpoint, then explicitly restore the selected library
patch and its saved host-chain links. Never use the old revision/session. Reconcile
identities with the loaded graph, wait for actual readiness rather than a fixed
delay, and only then mark the selected slot active. Report missing destinations.
Recall must never write back or overwrite a musical patch.

Paired saving stages both exports before publishing the new association; existing
committed pairs remain usable if either save fails. Track mismatched generations
and offer a deliberate resave. Do not claim a filesystem transaction across Oram
and MBMF without implementing recovery for interrupted saves.

While loading, coalesce requests to the most recent requested patch; a repeated
request for the same target does not restart loading. Suppress recursive Program
Changes emitted by restoration. Surface loading/error state in Web and Zynthian.
On failure, attempt validated recovery of the prior rig and report its outcome;
never claim rollback succeeded if chain restoration remains incomplete. Full
instrument snapshots can interrupt sound and take time; seamless live switching
is not guaranteed. Retain the patch-only option for rigs with unchanged chains.

## Required qualification before enabling

Test disabled mode, all 16 input channels, raw PC 0/1/4/127 boundaries, unavailable
slots and controller display offsets. Exercise master-channel conflicts and verify
no synth preset/ZS3 side effects or duplicate recalls. Verify safety with active
phrases, movements, hold, sustained notes, rapid PC bursts and repeated requests.

Exercise missing/corrupt patch and snapshot, renamed or moved snapshot, stale
control endpoints, processor-ID changes, partial host restoration, failed paired
save and interrupted recovery. Validate two genuinely different instrument rigs,
new engine sessions, chain identity relinking and the selected-slot indicator.
Measure transition duration and XRUNs on the Pi; preserve saved patch contents and
unrelated snapshots. Do not publish musical patches, snapshots, credentials or
tokens with test evidence.
