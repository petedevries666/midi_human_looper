# Native Zynthian chain prototype: issue #26

This adds **MIDI Bad Mother Fucker** to Zynthian's **MIDI Tool** selection, before
an existing synth in each chain. Zynthian creates/stops the engine instances and
owns all MIDI connections, including restoration from snapshots. No standalone
launcher, LV2 adapter, extra JACK server, manual jack_connect or boot service is
needed. The optional Firefox editor is a control worker owned by each instance;
closing Firefox never stops the engine.

## Build and install on the Pi

Back up your working Zynthian snapshot first. Recommended first target: Pi 4/5,
ARM64, at least 2 GB RAM. Three existing JSFX hosts use roughly 300–400 MB before
synth/sample memory; actual Pi performance and ARMHF atomic support need checking.
Run the following in Zynthian's local/SSH terminal, under the same environment/user
as the UI/JACK service (normally root on standard Zynthian images):

```sh
cd /zynthian/zynthian-plugins
git clone https://github.com/petedevries666/midi_human_looper.git
cd midi_human_looper
git fetch origin main
git switch main
git pull --ff-only
scripts/headless-setup.sh
scripts/headless-check.sh
python3 zynthian/install.py --lan
```

The installer registers a native engine by adding four marked changes to
`/zynthian/zynthian-ui/zyngine/zynthian_chain_manager.py` and copies one adapter into
`zyngine`. It backs up the original manager, retains a hash manifest, validates
syntax/known API anchors and supports idempotent installation. Unknown UI layouts
are rejected before mutation. It does not alter `zynautoconnect`, the MIDI router,
Zynthian engine/plugin catalogs, system services, audio settings or the JSFX source.
Registration was checked against official zynthian-ui commit
`8a8a7473907ab25a8b995b54aa7180906fb279c3`; an image with a different API still needs
compatibility testing. This is a local prototype integration, not an upstream
Zynthian-supported plugin package. UI updates may remove the registration.

Configuration and backups live in
`/zynthian/zynthian-my-data/midi-human-looper`. Override `--ui-dir`, `--data-dir` and
`--binary` if needed. Set `MBH_CONFIG` in the UI environment for a nondefault install
configuration. `--lan` creates a private editor token; omit it for loopback-only use.
Existing configuration/token files are preserved on reinstall. Keep the cloned
repository at its installed path: the adapter uses its engine, JSFX and editor files.

Restart **only the UI**, after saving your previous setup:

```sh
systemctl restart zynthian
```

Check your image's UI unit name with `systemctl list-units 'zynthian*'` if it differs.
Do not restart JACK or invoke `scripts/headless-run.sh` for this chain workflow.

## Piano, Bass and Synthesizer

1. Set Zynthian's global tempo to **120 BPM**, **4/4**, before adding the loopers.
2. Create a Piano synth chain on MIDI channel **1** and choose your piano sound.
3. In its chain options choose **Add MIDI Tool**, then **MIDI Bad Mother Fucker**.
   Ensure it is before the synth. Rename the chain Piano.
4. Repeat for Bass on channel **2** and Synthesizer on channel **3**, each with its
   own MIDI Tool instance and synth sound.
5. Use the normal Zynthian MIDI-input/active-chain selection to direct your keyboard
   to the intended chain. Each chain's router input feeds only its own looper and
   synth. A multichannel controller may instead send channels 1/2/3 explicitly;
   configure Zynthian input/channel filtering accordingly.
6. Save a new Zynthian snapshot after the three chains are configured.

Each native processor ID owns a separate JSFX VM, exact JACK client (`mbh_ID`),
phrase data, instrument/Transformer parameters, Controller configuration, socket,
web editor and patch files. Raw engine and processor JACK names use an anchored
regex, preventing ID 1 from matching ID 10. Zynthian's standard autoconnect graph
connects router → looper → synth and restores those routes; no handwritten port
names are needed for normal operation.

## Record and overdub

Select the looper's native **Looper** control page. PHRASE selects 1…16.
**RECORD** arms a take at the next shared loop boundary and starts JACK transport
if needed. Play during the displayed RECORDING interval. It automatically finishes
after **two 4/4 bars**, then loops. RECORD on an existing phrase overdubs one cycle
without deleting its events. FINISH ends recording early but retains the two-bar
loop length; unfinished held notes receive recorded releases before the wrap.

Record Piano first; select Bass and arm RECORD while Piano continues; then do the
same for Synthesizer. All instances use the shared JACK transport frame, not their
process startup times. PLAY enables the selected recorded loop at the shared phase.
STOP stops only that chain's phrase playback and releases its owned notes; other
chains continue. Native trigger controls can use Zynthian's normal MIDI Learn.
The existing Controller editor/assignments are available independently in each web
editor; use unused note/CC sources to avoid conflicts with Zynthian input filtering.

The first prototype deliberately uses a fixed two-bar grid. Its period is rounded
to a whole JACK processing block, so all instances agree without splitting the
original EEL block. At 48 kHz/512 frames/120 BPM it is exactly 192,000 samples
(four seconds). At other tempos the rounding error is at most half a block per
period; it does not cause drift between these instances, but this is not yet
sample-exact BBT grid alignment to other Zynthian sequencers. Recording preserves
performed offsets within that grid. Live MIDI and recorded timestamps retain the
existing one-block JACK graph latency.

JACK BBT supplies tempo when available, otherwise 120 BPM is used. Keep 4/4 and
fixed tempo for this first test. A tempo change or transport seek stops playback and releases notes
rather than silently rescaling recorded offsets. Missed playback callbacks release
notes and resume at the shared phase; an interrupted recording stops with an error
instead of being accepted as a complete take. Set the desired tempo before
creating the instances; recreate them after changing tempo. Restarting transport
does not reinitialize or erase recorded phrases (`ext_noinit` is enabled only in
chain mode). External MIDI clock is managed by Zynthian's existing clock/transport
system, not a second clock master in this plugin. Dynamic tempo/time signatures,
free-length synchronized takes and general BBT/clock chase remain later work.

## Firefox and persistence

The editor for processor ID `N` is `http://ZYNTHIAN_IP:8765+N` (calculate the port,
for example ID 1 → 8766). Processor IDs are visible in a saved snapshot; each
instance's `engine.log` also records the socket/HTTP startup. Read the private token
locally from `.../midi-human-looper/editor.token` and enter it in Firefox, then CONNECT.
Keep this HTTP service on a trusted LAN. Three browser tabs edit three independent
chains. The metrics display PLAYING / WAITING FOR NEXT LOOP / RECORDING / STOPPED
and clock/capacity errors. Browser REC/PLAY/FINISH uses the same native chain actions;
PANIC acts as that chain's STOP.

The native **Patch** page SAVE/LOAD uses
`.../midi-human-looper/processor-N/patch1.json`; the browser additionally supports
slot 2. Existing schema-7 event storage and the version-1 Controller extension are
preserved. Zynthian snapshots capture all instances by stable processor ID and
restore stopped; the native controls and phrase assignments remain per instance.
**SAVE and snapshot capture stop the affected chains safely** before the memory
copy; do not capture a snapshot while recording a take you want to continue. LOAD
also stops its chain and validates before applying. Loop length must match the
current chain grid: incompatible free-time REAPER patches are rejected instead of
silently retimed. Keep originals and test them with the standalone/REAPER version.
Controller files still require EXPORT REAPER BASE for transfer to REAPER; no new
REAPER policy or HUMANIZER playback functionality is included.

## Physical acceptance protocol

1. Confirm all three MIDI Tools appear in the native chain screen, with automatic
   input/output routes after creation and after reboot/snapshot restore.
2. Check live keyboard sound and channel isolation on Piano/Bass/Synthesizer.
3. Record a two-bar Piano phrase, then Bass, then Synthesizer. Earlier loops must
   continue while later takes record; listen for stable common wraps over 10 minutes.
4. Overdub Piano; ensure Bass/Synthesizer events/parameters are unchanged.
5. STOP Bass alone; hold notes/sustain while stopping, then verify no stuck notes.
   Test global Zynthian transport STOP/PLAY, a seek and a deliberate tempo change.
6. Stop takes, SAVE each slot and save a Zynthian snapshot. Restart only the UI,
   restore the snapshot, PLAY each and verify notes, routing and Controller mapping.
7. Use three Firefox tabs; Learn a distinct Helix input in each, test mappings and
   CLOSE the tabs. Playback must continue. Reopen and confirm telemetry.
8. Delete one looper while playing; it must release notes and remove only its ports.
   Watch callback overruns/overflow and RAM use with the actual synth patches.

No actual Raspberry Pi, Helix, audio output or stock Firefox acceptance is claimed.
Desktop tests use a real named dummy JACK server and the real engine/adapter, with
only hardware-specific Zynthian base/UI controller objects stubbed. UI registration
and exact rollback are tested against official source. Native routing on a physical
image, MIDI input policy, trigger Learn, snapshot UI hooks, load/CPU and synth sound
still require the above device protocol.

## Troubleshooting and rollback

Per-instance diagnostics: `.../processor-N/engine.log`. Missing MIDI Tool: verify
registration and UI logs (`journalctl -u zynthian`), then restart only the UI. Engine
startup failure: check JACK user/session, executable, installed path and socket.
An occupied/stale socket is refused; check ownership/processes before deleting it.
Web failure: check `8765+N`, token and logs; stop any old standalone launcher. No
sound: inspect native chain order, input policy, channels and enabled synth. Clock
error: restore fixed 4/4 tempo and recreate the looper instance. Capacity error:
the 2,048-event phrase limit was reached with an unmatched note; the unsafe loop is
disabled. Reduce event density or choose another phrase. Do not mute this warning.

To revert: STOP each looper, save your test patch files, remove the MIDI Tools from
the chains, and run:

```sh
cd /zynthian/zynthian-plugins/midi_human_looper
python3 zynthian/install.py --rollback
systemctl restart zynthian
```

Rollback removes only the marked registration and unchanged adapter, retaining
patches/config/token/backups. If Zynthian's manager changed since installation it
refuses to overwrite it; inspect the backup and remove the four MBH-marked additions
manually. Load the earlier snapshot without MBH processors. No JACK, synth, MIDI
router or boot service configuration needs reverting.

## Automated validation and dependency review

PRs #22 (preflight/combined runner), #23 (native Controller integration), #24
(stable JACK timestamp ordering) were reviewed with their required #19–#21
ancestors. These six stable PRs were merged in dependency order after the combined
suite passed. #25's pure HUMANIZER algorithms pass normal and sanitizer checks, but
that unfinished feature remains an unmerged draft and is not in this integration.
The native-chain integration remains a separate PR against main.

Final combined suite: 2,355 actual EEL2/GUI/MIDI checks and three stable concurrent
render hashes; 14 baseline and nine Controller API tests; three registry tests;
five Lua persistence tests; Controller policy 160,381 checks and adapter 523 checks,
normal and ASan/UBSan; three installer tests; real three-chain JACK recording,
phase/Note Off/isolation/snapshot/Controller-persistence test and its three Chromium
editors; original JACK routing, overload recovery and exact timestamp/tie tests;
three existing Chromium browser suites. No failing checks are disabled.

```sh
# Desktop development only; --jack starts a named dummy server, not the Pi's server.
HEADLESS_BINARY="$PWD/.build/midi-headless-engine" YSFX_SOURCE="$PWD/.build/ysfx" \
  NATIVE_PATCH_FIXTURE=/tmp/midi-native-patch.json \
  python3 scripts/combined-test.py --native --jack --browser chromium
```

Use a test virtualenv with `lupa playwright selenium` and installed Chromium;
production native controls/editor require only Python stdlib. The official UI
registration/rollback audit passed against the source commit above. Hardware-specific
Zynthian dependencies/UI widgets are stubbed in the three-chain adapter test, and
its probe simulates Zynthian's managed graph. Actual autoconnect and native screen
operation are still part of physical acceptance.

## Cloud integration regression buffer

The three-processor desktop regression defaults to 48 kHz / 2,048 frames
(42.7 ms), with `CHAIN_JACK_BLOCK=4096` or `8192` available for throttled CI.
This cloud machine occasionally misses recording deadlines even at 2,048 frames;
those runs fail safely with `chainError=1`, not silent recording corruption.
The full cloud functional matrix uses `CHAIN_JACK_BLOCK=8192` (170.7 ms), with
its two-bar period rounded to 196,608 samples. This is not a low-latency or
Raspberry Pi performance qualification. The separate ordering/overflow JACK tests
continue using their existing smaller buffers. No Zynthian JACK settings change.
A missed recording callback cancels the take and now reports a clock error.
A missed playback callback releases channel state with 48 bounded MIDI channel
messages (CC64/123/120) on this processor's output, resets owned notes and resumes
at the common transport phase. It does not queue thousands of obsolete releases
in front of current attacks. Synths must respect those channel-mode messages.
Transport discontinuities and capture errors expose `chainFrameGap` and
`chainClockGap` diagnostics. Genuine seeks and tempo changes still stop playback.

## Optional integrated Snapshot editor test branch

The core native-chain prerequisite is merged into `main`. To test the integration
PR, after cloning use `git fetch origin feat/product-integration` and
`git switch --track origin/feat/product-integration`, then rebuild with
`scripts/headless-setup.sh`. Do not run an old native binary against the new server
or adapter: the integrated native action opcode is 40 and Snapshot capture remains
20. If already registered, STOP/remove processors and run installer rollback before
installing the updated adapter; the installer refuses conflicting old adapter files.

1. Run `scripts/headless-check.sh`, then `python3 zynthian/install.py --lan`.
2. Save existing Zynthian work and restart only the UI when ready. Add MBH as a
   MIDI Tool before Piano, Bass and Synth, with chain inputs 1, 2 and 3.
3. Set fixed 4/4 at 120 BPM before creating processors. Select Phrase 1 and RECORD
   Piano. It waits for the common boundary, records two bars and loops. Record Bass
   and Synth while Piano continues. RECORD again overdubs; FINISH closes held notes.
4. Open Firefox at `http://ZYNTHIAN_IP:8765+PROCESSOR_ID` (for ID 1: port 8766).
   Enter the token from `midi-human-looper/editor.token`. Each tab controls its own
   processor and patch. PANIC/STOP one processor must not affect the other two.
5. Set Instrument volume, CAPTURE Snapshot A, change volume/Transpose, CAPTURE B.
   EDIT B sets a two-second morph. Recall A, then MORPH B during looping. Learn a
   distinct Helix Controller source, map volume with GLIDE, and move it during morph.
   It must take over without automation fighting it. Existing Switch assignments
   can use OPTIONS → MORPH TO NEXT; full switch assignment popup is still pending.
6. CLOSE Firefox. Playback and an active morph must finish without the browser.
   SAVE each processor and a Zynthian snapshot, recreate/reload with the same IDs,
   and confirm phrases, modules, Controller mappings and Snapshots remain independent.
7. PANIC, remove each processor, and verify every synth releases its notes. Perform
   the rollback instructions above if retaining the prototype is not desired.

The regression probe has separate JACK source and sink clients, so the test graph
is acyclic and does not insert an implicit feedback-period delay into recording.
It exercises actual overdub on Piano while Bass/Synth remain playing, Snapshot
capture/recall and per-processor persistence/recreation. Three processor captures
must remain on the shared two-bar grid. This does not qualify physical latency.

Native chain STOP/PANIC and SAVE/LOAD cleanup now uses the same bounded channel
release path as missed playback. This prevents rapid SAVE → LOAD → PLAY from
filling the output FIFO with repeated 2,048-note sweeps at large buffers. The
separate REAPER/standalone paths retain their established explicit note sweeps.
Actual JACK capture validates chronological output and an empty final note ledger,
including channel-mode cleanup. Synth response to CC64/123/120 remains mandatory
for this native cleanup policy and must be verified on the physical image.
For the initial Helix expression test, use an unassigned CC such as 21 or 22;
legacy expression CCs remain protected and cannot be silently reassigned.
