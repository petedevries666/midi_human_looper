# Reviewed UPDATE controls — Web and physical Oram menu

Draft implementation of the UPDATE half of #70, based on #68 → #67. LIVE
CONTROLS is independent: this PR changes no MIDI engine, BYPASS, MIDI LOG,
MOVEMENT routing, phrase routing, project schema or native router hooks.

## What works

Expand **UPDATE** in the editor: installed JSFX header version and actual running
build SHA, CHECK, release changes, explicit INSTALL confirmation, progress/error,
ROLLBACK and interrupted-activation RECOVER. The physical MBMF **Update** controller
page offers CHECK UPDATE, INSTALL UPDATE, ROLLBACK and UPDATE STATUS. Install and
rollback use Oram's real confirm screen. STATUS shows installed/available revision,
changes and progress; use INSTALL/ROLLBACK to recover a pending activation. No
controller update actions are replayed from a snapshot or MIDI-learned by default.

Both interfaces use `/run/mbmf-update.sock`, owned mode 600, served by one independent
root worker. Physical root peer plus on-device confirmation is authorization.
Web CHECK/INSTALL/ROLLBACK/RECOVER require a **separate administrator password**,
PBKDF2-SHA256 (300,000 iterations, random salt), never the editor token. HTTP accepts
only same-origin JSON and a strict field allowlist; callers cannot request native
privilege, a repository/path or an arbitrary SHA. Credentials are not persisted in
the browser or logged. Status is read-only and available to editor users.

Use an isolated trusted LAN, or HTTPS on an already configured trusted reverse
proxy: ordinary HTTP does not encrypt the administrator password. This PR does
not expose new public network listeners or alter networking services.

## Release authority (intentional gate)

CHECK reads the latest **published stable GitHub release** in this repository.
It must carry `mbmf-update.json`:

```json
{"version":1,"revision":"FULL_LOWERCASE_40_CHARACTER_SHA","components":{"engine":1,"adapter":1,"editor":1}}
```

The full SHA must equal the release tag and be a merged ancestor of `main`.
Draft/prerelease, unmerged commits, missing manifest, incompatible component
contracts or changed release between CHECK and INSTALL are refused. Release body
is the change summary. **No eligible stable release currently exists** (GitHub
latest-release API returned 404 during development). This draft cannot install
itself or other draft PRs. Publish a reviewed merged release and manifest before
routine updates become available; do not loosen this gate for hardware testing.

## Reuse, activation and recovery

The worker reuses `scripts/zynthian-update.py`: stopped-project checkpoint,
actual candidate native preflight, free-time downgrade guard, durable journal,
atomic config replacement, exact project fingerprint/build/API health validation
and compensating rollback. Added candidate Web/API preflight runs privately with
the candidate Python editor and actual engine, without JACK. Active PHRASES,
recording/arming, held notes, MOVEMENTS and snapshot morphs refuse updating before
build; all are checked again before activation. Finish and STOP performance first.

Source is fetched into the **existing checkout's Git object store**, archived to
`releases/<sha>` for atomic switching/rollback, not cloned into another checkout.
The existing checkout is not switched or reset. Pinned ysfx is a single shared
build cache; ARM builds retain `-fsigned-char` for WDL and the host. Archive source
and binary hashes are recorded and verified before cache reuse. Incomplete inactive
builds may be retried; modified or incomplete active/rollback releases are refused.

The owned Python adapter and its installer ownership manifest are journaled and
switched with the runtime; failure restores their exact bytes/modes as well as
`install.json`. Native catalog/router helper identity must match the installed
ownership manifest. Changes needing different registration/routing policy are
refused and require a separately reviewed integration upgrade. Original installer
backups and protected source files are retained. Musical projects are never rolled
back to old backup content: current stopped data must validate in the candidate.

**Restart limitation:** the existing adapter's children are owned by the Zynthian
UI, not an MBMF service. This slice reuses its proven `systemctl stop/start zynthian`
activation: it reloads the installed adapter and recreates its children. This can
interrupt every UI-owned instrument and audio playback. JACK and LUMAZ services
are never restarted. Save the Zynthian snapshot first. Seamless, MBMF-only hot
activation is not claimed; do not use UPDATE during a concert. A later smaller
host-lifecycle hook would be needed to avoid the UI restart when only the editor
or binary changes.

The updater worker itself is separate from the UI/editor and survives their
restart. Journal phase `pending` makes INSTALL refuse; Web RECOVER or physical
INSTALL/ROLLBACK confirmation restores the previous components/config, starts UI
and verifies old project fingerprints. Failed rollback stays pending and visible.
Never delete trees referenced by config or journal.

## One-time in-place enablement (after review, while stopped)

No command below has been executed on a physical device. From your existing
`/root/midi_human_looper`, first bring in the **reviewed implementation SHA** using
your normal in-place update procedure; never deploy the unreviewed draft. Then:

```sh
cd /root/midi_human_looper
python3 zynthian/install.py --upgrade-adapter --check
python3 zynthian/install.py --upgrade-adapter
sudo scripts/mbmf-update-controls-install.sh
```

The installer must already know the #67 native routing ownership. It preserves
that configuration. The opt-in worker setup asks twice for its separate password,
retains the checkout identity, installs only `mbmf-update-control.service`, and
starts **only this new administration worker**. It does not restart the musical
runtime. Reload the reviewed adapter/editor during your next planned stopped
runtime restart. After that, routine CHECK/INSTALL/ROLLBACK requires no SSH.

Reset a forgotten UPDATE password with the same setup command locally. To disable
administration without stopping music:

```sh
sudo systemctl disable --now mbmf-update-control
```

If the interface is unavailable during recovery, emergency fallback remains:

```sh
sudo python3 scripts/mbmf-update-control.py --configure
sudo systemctl restart mbmf-update-control
```

Then reopen UPDATE and use RECOVER. If UI startup still fails, inspect
`runtime-update.json`, `systemctl status zynthian`, and processor `engine.log`.
Keep saved projects and installer manifests; do not re-register JACK or reinstall
Zynthian. The existing CLI `scripts/zynthian-update.py --rollback` remains usable
for **legacy runtime-only** journals. Component journals created here must be
recovered through this worker so adapter and config roll back together.

## Qualification

Cloud tests exercise real HTTP/Unix sockets, password verification, filesystem
journals, candidate native/Web preflight and Chromium against the native editor.
Kernel root identity, release API and systemd/physical display are explicitly
fixtures. No ARM64 build, actual Oram UI restart, real release deployment or
Zynthian/Helix validation has occurred. Do not interpret a green fixture as safe
live hot-update qualification.

Physical controlled checks: save snapshot; finish/STOP all sources; CHECK eligible
reviewed release; verify password refusal and physical confirmation; install;
verify all processor fingerprints, settings/token/ports and #67 filtering; open
editor and play phrases/MOVEMENTS; STOP and rollback; verify same project data.
Try rejected install while recording, playing or a MOVEMENT runs. In a disposable
stopped setup, interrupt activation and confirm RECOVER restores adapter/config.
Never deliberately kill a performance or alter JACK routing to test recovery.
