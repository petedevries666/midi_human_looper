# Native boot recovery and persistent patch library

A failed physical startup left processor 2's UNIX control socket on disk. The
adapter refused it before launching a native engine; Oram then aborted snapshot
loading, leaving a partial chain graph. Recreating MBMF as processor 4 also
selected another patch directory, making the earlier saved slots appear absent.
The source files were still intact.

Before starting a native processor the adapter now checks both its control and
host-chain endpoints. Only a real socket owned by the current user, absent from
Linux's kernel UNIX socket inventory and unchanged during inspection, can be
removed. A bound socket is protected even before listen(), as are ordinary files
and symlinks. An unavailable ownership inventory causes refusal, not guessing.

Musical library storage is independent of processor IDs. The default is
`midi-human-looper/patch-library`; install configuration may pin `patch_library`
to an existing directory. A first migration copies the current legacy slots,
names, switch presets and portable projects, leaving originals intact. Existing
shared libraries win and are never merged over by later processor IDs. Pending
legacy preset transactions must be recovered before migration. Tokens, sockets
and engine logs are excluded. Runtime sockets and snapshot restoration remain
processor-specific.

The editor restores its persisted selected patch slot after preset-journal
recovery, so reloading the editor does not present slot 1 for a resident slot 2.
It does not automatically save or replace a musical patch.

Linux fixtures reproduce abandoned versus live/bound UNIX sockets, refuse unsafe
paths, preserve slot 1 and slot 2 across processor recreation, protect against
partial migration and restore the selected slot. Snapshot-key hook regressions
also run against the changed adapter. No REAPER source, native audio binary,
JACK configuration or LUMAZ code changes.

Physical recovery preserved the newer saved processor-2 FEAR & LOATHING in slot 1
and processor-4 road in slot 2. Original processor libraries and a targeted
recovery backup remain local; musical patches and snapshot files are not public
repository artifacts.

For the existing physical installation, `patch_library` pins the recovered
processor-4 directory in place: the running editor keeps writing the same files,
and subsequent processor IDs reuse them. This avoids a split library while the
current UI stays running. Six storage/socket/selection tests and five snapshot
hook tests pass. The adapter and configuration were installed without restarting
services because the live UI did not confirm a new last-state snapshot save;
The user subsequently saved an instrument snapshot. A physical-device Zynthian UI
restart restored both amsynth and Sfizz after deliberately abandoning both UNIX
socket endpoints. Native patch source and Conductor matched the pre-restart state
(except host-controlled instrument names); saved slots, names and the original
snapshot were byte-identical. JACK retained its process at 44100 Hz / 512 frames /
3 periods. This qualifies a UI restart, not a power-cycle or arbitrary failed boot.
