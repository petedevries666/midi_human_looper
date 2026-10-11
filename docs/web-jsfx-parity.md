# Compact web editor and native one-shot playback

Dependency: PR #47 (`fix/oram-midi-fx-discovery`) on PR #44's
`integration/studio-live-rc`. Screenshot tooling is reused from PR #46. This branch
does not merge PR #45 or reinterpret its additional phrase modes.

## Implemented

Click a phrase or instrument name to edit inline. Enter commits; Escape or leaving
the field cancels. Keyboard users can focus the name button and press Enter. Names
use the same 16 printable ASCII character cells as the REAPER JSFX. Empty names
show the original numbered default. Names are engine-owned, validated, revision-
and session-guarded, isolated by stable instrument ID / phrase slot, and included
in PATCH SAVE/LOAD, portable projects and Zynthian snapshot patch data. No new name
schema or browser-only data is introduced. Unicode names are rejected explicitly,
matching the current JSFX editor. Existing nameless patches retain their defaults.

The black, rectangular, gray-lined editor preserves six-phrase pagination and all
existing controls. Yellow marks parameter values / module identity; PANIC remains
restrained orange. The signature uses a locally served 2 KB OFL-licensed Bungee
subset, renamed MBMF Block, without external requests or proprietary assets. Version
comes from the shipped JSFX description. Controllers and diagnostics remain folded
by default. Actual capabilities, fixed legacy processing stages and unsupported
CONDUCTOR remain explicit; the appearance does not claim arbitrary chain order.

## Playback capabilities

| Mode | Standalone shared JSFX | Native two-bar chain adapter |
| --- | --- | --- |
| LOOP | Existing loop semantics | Shared JACK two-bar phase, unchanged |
| ONCE | Existing polyphonic retrigger / decay semantics | Immediate one-shot using the same voice pool; ends naturally, can retrigger |
| HOLD | Legacy attack sustain until STOP / next phrase | Unavailable from web/API playback pending reliable held-release ownership |
| ONCE / NO RETRIGGER, PRESS / RELEASE | PR #45 work, not included here | Not included here |

The compact native transport strip displays PLAYING/RECORDING/ARMED/STOPPED and
provides a real STOP command using the existing opcode 40 dispatcher. It is hidden
for standalone hosts. Mode controls are enabled in native mode for LOOP and ONCE. Mode edits use the
existing deferred parameter mechanism: STOP the processor to apply safely; edits
queued during playback are identified in the UI. Recording still uses the existing
synchronized two-bar LOOP capture, and sets its recorded phrase to LOOP. Select
ONCE after recording/FINISH and STOP. ONCE's own clock starts on its trigger; it does
not reset the shared timeline or turn other looping phrases into one-shots.
STOP/PANIC retain existing ownership cleanup. Legacy JSFX ONCE changes phrase voice
ownership when selecting a different phrase; this work preserves that behavior.

HOLD is deliberately labeled unavailable for native web triggering. The adapter
rejects its PLAY action without starting transport. Legacy physical trigger paths
still execute the existing JSFX HOLD behavior (latched attacks, not loop-while-held);
they have not gained PRESS/RELEASE semantics. Use STOP/PANIC for those legacy held
notes. Completing native held release requires PR #45 lifecycle work; do not treat
this visual update as full HOLD parity or a four-track CONDUCTOR implementation.
Names and all source MIDI remain unchanged across this UI update; default export
still exports source phrases, not transformed or revealed MIDI.

## Upgrade a working V4 after review

This includes a new native opcode (36) for persistent names and a changed chain
PLAY bridge. Upgrade the native binary, JSFX, HTTP server and web assets together.
Do not copy only web files onto an older native binary. This is separate from PR
#47's catalog-only fix, which deliberately preserves an existing adapter/runtime.
No physical Zynthian has been modified by this development work.

1. Save a Zynthian snapshot and current patches, then STOP/PANIC all MB processors.
2. Keep the working runtime directory and `/zynthian/zynthian-my-data/midi-human-looper`
   backed up; record its Git revision and `install.json`. Build this reviewed branch
   in a separate checkout with the existing native build dependencies. Do not run
   the OS setup script on an already working device.
3. Build with `scripts/headless-build.sh`. On the V4, verify the resulting executable
   is built for that device's architecture. No JACK service/config changes are needed.
4. Run `python3 zynthian/install.py --check --binary "$new_checkout/.build/midi-headless-engine"`
   to verify registration compatibility. The installer preserves an existing
   `install.json`, so this alone does **not** switch runtime authority.
5. With the Zynthian UI stopped, atomically update **only** `repository` and `binary`
   in the backed-up `install.json` to the new checkout/binary; retain token, bind,
   ports, timing version and all other fields. Restart only the UI. This is a planned
   runtime switch, not a live mutation or automatic deployment. Verify the web
   diagnostics build revision and phrase playback before saving new work.
6. Hard-refresh Firefox (Ctrl+Shift+R) if old controls remain. Check renamed phrases,
   imported MIDI, ONCE completion/retrigger, LOOP phase and STOP/PANIC.

Rollback: STOP/PANIC, stop only the UI, atomically restore the previous `install.json`
and restart the UI. The old runtime directory and patches remain available. If
registration itself must be removed, follow PR #47's separate rollback guide; do
not uninstall discovery merely to change runtime. Restore backed-up patches if a
later unrelated feature changed their format. This update retains schema 7.

## Test evidence and remaining hardware gates

`tests/test_web_names.py` exercises actual native memory, save/load, portable memory
roundtrip, isolation, empty names, invalid inputs, stale revisions and deleted IDs.
`tests/test_web_parity_browser.py` exercises real Chromium Enter/Escape, persistence,
reconnect, enabled modes, signature and layout at 320/800/1366/1440 widths.
The actual JACK dedicated-chain test covers LOOP, ONCE completion/retrigger, rejected
native HOLD, transport and removal cleanup. Three-chain browser tests exercise mode
changes while stopped. Existing JSFX, native, portable, auth, MIDI import/export,
Controller/Snapshot and restart tests remain in the combined runner.

Screenshots are generated by `scripts/screenshots.sh`, with real PNG artifacts in
`docs/screenshots/`. The layout audit permits vertical scrolling and checks overflow,
clipping and access; every captured view must also be visually inspected. Hardware
V4/Helix/amsynth and stock Firefox, long performances/XRUNs, actual channel filtering,
and real REAPER UI acceptance remain physical validation gates. No hardware parity
claim follows from passing desktop dummy-JACK or Chromium tests.

### Reviewed-update commands (standard existing installation)

Run on the Pi only **after PR review**, with saved work and stopped/PANICed MB
processors. This assumes the working checkout retains its pinned `.build/ysfx`
cache; if the cache check fails, use the existing dependency location instead of
installing OS packages. Keep the printed backup path for rollback.

```sh
config=/zynthian/zynthian-my-data/midi-human-looper/install.json
old_repo=$(python3 -c 'import json; print(json.load(open("/zynthian/zynthian-my-data/midi-human-looper/install.json"))["repository"])')
backup_dir="/zynthian/zynthian-my-data/mbmf-before-web-ui-$(date -u +%Y%m%dT%H%M%SZ)"
cp -a /zynthian/zynthian-my-data/midi-human-looper "$backup_dir"
echo "$backup_dir"
git clone --single-branch --branch feat/web-jsfx-parity https://github.com/petedevries666/midi_human_looper.git /zynthian/zynthian-plugins/mbmf-web-ui
cd /zynthian/zynthian-plugins/mbmf-web-ui
export YSFX_SOURCE="$old_repo/.build/ysfx"
export YSFX_BUILD="$YSFX_SOURCE/build"
test -f "$YSFX_BUILD/libysfx.a" && scripts/headless-build.sh
python3 zynthian/install.py --check --binary "$PWD/.build/midi-headless-engine"
```

Stop if build or preflight fails. If they succeed, switch only the owned runtime
paths while the UI is stopped (verify the standard UI service name first):

```sh
systemctl stop zynthian
python3 - <<'PY'
import json, os, tempfile
from pathlib import Path
path=Path('/zynthian/zynthian-my-data/midi-human-looper/install.json')
root=Path('/zynthian/zynthian-plugins/mbmf-web-ui')
data=json.loads(path.read_text())
data.update(repository=str(root),binary=str(root/'.build/midi-headless-engine'))
fd,name=tempfile.mkstemp(dir=path.parent,prefix='install.json.')
try:
    with os.fdopen(fd,'w') as stream:
        json.dump(data,stream,indent=2);stream.flush();os.fsync(stream.fileno())
    os.chmod(name,path.stat().st_mode & 0o777);os.replace(name,path)
finally:
    if os.path.exists(name):os.unlink(name)
PY
systemctl start zynthian
journalctl -u zynthian -n 40 --no-pager
git rev-parse HEAD
```

Open the existing editor URL/token and Ctrl+Shift+R. Confirm diagnostics identifies
the newly built revision. Reinstalling registration is unnecessary when PR #47 is
already installed. Snapshot/patch/runtime paths and token/port settings are retained.
For an existing `mbmf-web-ui` checkout, back up first, then `git pull --ff-only` and
rebuild only while stopped. Retain the previous executable/checkout for rollback;
prefer a fresh reviewed checkout rather than overwriting a running binary.

Rollback: stop/PANIC, stop the UI, restore **only** `install.json` from the backup
path printed above, and start the UI. For example (set `backup_dir` to your actual
backup, not the example placeholder):

```sh
systemctl stop zynthian
python3 - "$backup_dir/install.json" <<'PY'
import os, sys, tempfile
from pathlib import Path
source=Path(sys.argv[1]);destination=Path('/zynthian/zynthian-my-data/midi-human-looper/install.json')
fd,name=tempfile.mkstemp(dir=destination.parent,prefix='install.json.rollback.')
try:
    with os.fdopen(fd,'wb') as stream:
        stream.write(source.read_bytes());stream.flush();os.fsync(stream.fileno())
    os.chmod(name,source.stat().st_mode & 0o777);os.replace(name,destination)
finally:
    if os.path.exists(name):os.unlink(name)
PY
systemctl start zynthian
```

Do not run the service-start step if a preceding restoration fails. Leave Zynthian
UI stopped, retain the backups, and inspect the error. No command here restarts JACK,
changes routing, upgrades the OS or touches LUMAZ.

### Executed cloud validation (2026-10-11)

- `scripts/combined-test.py --native --jack --browser chromium --timeout 240`: PASS,
  with the existing ysfx/JACK dependency paths configured. Includes 5,796 EEL2/GUI/
  MIDI checks, portable parity, real dummy-JACK three-chain operation and one-shot
  cleanup, timestamp ordering, bounded overflow, Controller sanitizer checks,
  snapshots, project authority/synchronization, import/export and browser suites.
- `tests/test_web_names.py`: three actual-engine tests PASS (patch-slot switching,
  portable memory roundtrip, stale/deleted IDs, isolation and sounding-note ownership).
- `tests/test_web_parity_browser.py`: PASS. Generic editor and Controller browser
  tests were rerun after the final narrow-dialog style correction and passed.
- `scripts/screenshots.sh`: 93 real PNG artifacts, all four viewports; PNG dimensions
  and overflow/clipping/access checks PASS. Every captured view was visually
  inspected, including scrolling dialog bottoms. No CONDUCTOR mockup supplied.
- `tests/test_screenshot_audit.py`: seven detector tests PASS.

Runtime and source build revisions are recorded separately in the screenshot
manifest. The captures use the real engine's mock clock (no JACK input or physical
hardware), while the separate JACK integration tests use a real private dummy
server and virtual receivers. Neither is a physical Raspberry Pi/Helix/amsynth test.
