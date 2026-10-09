# First Zynthian test: issue #18, runnable P0

This branch starts from merged main after #17. It hosts the existing schema-7
JSFX with ysfx, without `@gfx`, and uses **native JACK MIDI ports**. Stock ysfx does
not provide LV2. Standalone JACK is the shortest test route; chain/service integration
and an LV2 adapter remain later work. No SSH, actual Pi access or automatic deployment
is assumed. Run these commands in a local Linux terminal on the target machine.

## Build (Pi or Linux)

```sh
uname -m
getconf LONG_BIT
cat /etc/os-release
git clone https://github.com/petedevries666/midi_human_looper.git
cd midi_human_looper
git fetch origin feat/zynthian-runnable-mvp
git switch --track origin/feat/zynthian-runnable-mvp
scripts/headless-setup.sh
scripts/headless-test.sh
```

Setup installs build tools, Python 3 and JACK development headers, checks out ysfx
commit `8077347ccf4115567aed81400281dca57acbb0cc`, builds it with no plugin, then builds
the host. It reports the **actual** architecture; `aarch64`, `armv7l` and `x86_64`
are accepted build targets, not claims of completed ARM validation. Two build jobs
limit Pi memory use; use `BUILD_JOBS=1` on memory pressure. Python uses only stdlib.
On a locked-down/offline Zynthian image, install the listed packages and copy this
repository plus the pinned ysfx checkout via removable media instead. Do not upgrade
Zynthian's kernel/audio packages or start a second JACK server on the device.

## Start and connect MIDI

Zynthian normally supplies its existing JACK graph. First inspect it:

```sh
jack_lsp -t
scripts/headless-check.sh
DEMO_PATCH=1 scripts/headless-run.sh
```

If `jack_lsp` is unavailable, install `jack-tools` using the image's package manager.
The engine uses `JackNoStartServer`: it never launches or replaces Zynthian's server.
It registers `midi_human_looper:midi_in` and `midi_human_looper:midi_out`. In another
terminal, connect the **actual names reported by jack_lsp**, replacing these examples:

```sh
jack_connect 'a2j:Helix [24] (capture): Helix MIDI 1' 'midi_human_looper:midi_in'
jack_connect 'midi_human_looper:midi_out' 'ZynAddSubFX:midi_input'
```

Alternatively set `MIDI_INPUT='exact source port' MIDI_OUTPUT='exact destination port'`
when running. Connection failures are logged and may be repaired with `jack_connect`.
ALSA-only Helix devices may need Zynthian's existing MIDI bridge or `a2jmidid -e`;
inspect existing bridges first. Keep the graph one-way; do not feed engine output back
to its input. Zynthian routing/filter settings must allow the desired MIDI channels.
The synth output remains in Zynthian's audio graph; this engine produces MIDI only.

The optional demo fixture has VERSE Note 72, channel 1 → repeating phrase Note 60;
CHORUS Note 73, channel 1 → ONCE Note 64. These may differ from your Helix preset:
use browser TEST or simulated input first. Instrument 1 starts enabled, 2/3 disabled.
Enable Instrument 2 and select separate input/output channels to verify isolation.
Without `DEMO_PATCH=1`, the engine starts with the real blank default; use LOAD to
restore an existing patch or REC to create one. No automatic patch load is implied.

## Firefox from another computer

Loopback is the default: `http://127.0.0.1:8765`. For deliberate trusted-LAN access:

```sh
umask 077
python3 -c 'import secrets; print(secrets.token_urlsafe(32))' > /tmp/midi-editor-token
EDITOR_BIND=0.0.0.0 EDITOR_TOKEN_FILE=/tmp/midi-editor-token DEMO_PATCH=1 scripts/headless-run.sh
hostname -I
```

Open `http://ZYNTHIAN_LAN_IP:8765` in Firefox on the PC/tablet. Enter the token from
that file and click CONNECT. The token travels in an HTTP header or first WebSocket
frame, never a query string. This is trusted-LAN HTTP, not encrypted Internet hosting;
keep the service off public networks. Authentication, Host/Origin checks and bounded
commands are enforced. Commands include the authoritative random engine-session ID
and expected revision; both are checked to reject edits from a prior engine restart. Browser state is authoritative engine telemetry, pushed over
WebSocket with reconnect; HTTP remains the command and fallback snapshot transport.
Closing the browser leaves playback running. The independent web worker can restart
without restarting the engine; the launcher intentionally owns both processes, so
stopping the launcher stops both. For separate lifetimes run the executable and
`python3 headless/server.py --socket SOCKET --patch-dir DIRECTORY` in separate terminals.

## Patch files and safety

SAVE PATCH 1/2 writes atomically to
`${XDG_DATA_HOME:-$HOME/.local/share}/midi-human-looper/patch1.json` / `patch2.json`;
set `PATCH_DIR` to override. Back up existing files before copying REAPER patches.
Files use `MIDI_HUMAN_LOOPER_PATCH`, full-precision numeric JSON and schema 7;
legacy schemas 1–6 use the existing appended-tail migrations. Files remain readable
by the companion REAPER Lua script. The two files are independent; saving one does
not overwrite the other. SAVE captures current committed configuration and phrase
events, not Learn, drafts or playing runtime. SAVE briefly pauses engine access for
a bounded memory copy, then serializes/writes outside processing. LOAD parses and
validates first, releases notes, resets runtime, applies the committed patch while
callbacks remain responsive but MIDI processing is paused, then resumes stopped.
Do not LOAD while performing timing-critical MIDI. No disk/JSON/socket work runs in
the JACK processing callback. PANIC clears phrase playback, live ARP and owned notes.
Large Note Off bursts drain through a bounded output FIFO across JACK blocks.
Input processing is capped at 128 queued events per block. On FIFO overload the host
discards stale pending events, sends channel sustain-off/all-notes-off/all-sound-off,
and runs PANIC before resuming input. Overflow counters remain visible for diagnosis.
The existing JSFX receive loop is also corrected to process every event in a block;
previously its trailing constant stopped the loop after the first event. Same-block
chord and exclusive MIDI Learn regressions cover this minimal REAPER fix.

The current basic UI includes phrase PLAY, REC/OVERDUB and FINISH REC, Instrument
routing/enabled/volume, existing Transformer cards, switch TAP/DOUBLE/HOLD TEST,
simulated footswitches, PANIC and SAVE/LOAD. Full switch/curve/Learn configuration,
generic module transactions and global controller policies follow in separate PRs.
STOP all playback via PANIC; phrase-specific stop controls are not implemented yet.

## Tomorrow's checklist

1. Confirm reported Pi architecture and successful build; record OS/JACK version.
2. Connect input and output ports; enable the intended synth/Instrument channel.
3. Firefox shows CONNECTED, increasing sample clock and MIDI count.
4. TEST VERSE TAP and CHORUS TAP produce sound; test DOUBLE/HOLD and physical MIDI.
5. Enable two Instruments with separate channels and verify each input/output.
6. Record a short phrase; FINISH REC, PLAY, inspect event count and Note Offs.
7. PANIC produces silence; held ARP must not resume. Observe `outputOverflow == 0`.
8. SAVE both slots, change routing, LOAD each and confirm restoration stopped.
9. Close/reopen Firefox and restart only the web worker; playback continues.
10. Stop/restart engine, LOAD saved patch and repeat. Check overlapping notes,
    sustain/late releases, long sessions and callback overruns on the real kit.

## Desktop validation and troubleshooting

```sh
MOCK_MIDI=1 DEMO_PATCH=1 scripts/headless-run.sh
RUN_JACK_TESTS=1 scripts/headless-test.sh  # Desktop only: dedicated dummy JACK server
RUN_NATIVE_TESTS=1 YSFX_SOURCE="$PWD/.build/ysfx" scripts/headless-test.sh
```

Browser tests: install Playwright in a venv and its Firefox build, then run
`HEADLESS_BINARY="$PWD/.build/midi-headless-engine" python tests/test_headless_browser.py`.
They also accept `MIDI_BROWSER=chromium`. A stock Firefox alternative uses Selenium:

```sh
python3 -m venv /tmp/midi-browser-tests
/tmp/midi-browser-tests/bin/pip install selenium
# Install Firefox ESR and geckodriver through your OS/test environment.
HEADLESS_BINARY="$PWD/.build/midi-headless-engine" /tmp/midi-browser-tests/bin/python tests/test_headless_firefox.py
```

Production Firefox requires no extensions or Selenium. These are test-only dependencies.

Desktop evidence is recorded in the PR: actual ysfx, real JACK dummy graph and browser
checks. **Pi/Zynthian/Helix timing and sound require physical validation.** A desktop
non-realtime dummy server is not a latency benchmark. Watch sample clock, callback
maximum, late blocks and output overflow; turn off demo/testing loops before routing
physical outputs. The desktop graph test uses 512 frames. PANIC executes the existing bounded JSFX
release loop, which can exceed a 128-frame callback deadline even on desktop.
Measure it on the Pi; if it overruns, temporarily choose 512/1024 frames through
Zynthian's existing audio settings, then retest. The host does not change the server.

`JACK unavailable`: verify the same user/server environment as Zynthian; don't start
an unrelated server. `socket bind`: another engine may own the path; check processes
before deleting any stale socket. Compilation failure: verify pinned ysfx and full
submodules. Editor disconnected: inspect engine and Python stderr, token and port.
Patch LOAD rejected: retain original, inspect schema/array lengths; resave through
current REAPER if needed. No sound: inspect graph/channel filters and downstream synth.
Launcher logs go to the terminal; capture with your preferred supervisor/journal.

Rollback: PANIC, Ctrl-C, verify owned ports disappear, remove graph connections and
return to the prior REAPER/Zynthian setup. No service is installed/enabled, no system
configuration or REAPER JSFX source is modified. Do not remove saved patch files.

## Continuing issue #18 and combined regression

The runnable host remains #19; #20 adds the descriptor editor and #21 the policy
core. The first-demo hardening branch `fix/zynthian-first-demo` stacks on #21.
For that complete reviewed stack, fetch and switch explicitly:

```sh
git fetch origin fix/zynthian-first-demo
git switch --track origin/fix/zynthian-first-demo
scripts/headless-setup.sh
scripts/headless-check.sh
# Use the LAN token and MIDI_INPUT/MIDI_OUTPUT commands above.
EDITOR_BIND=0.0.0.0 EDITOR_TOKEN_FILE=/tmp/midi-editor-token DEMO_PATCH=1 scripts/headless-run.sh
```

Preflight never starts JACK or changes the graph. Run it as the same user and in
the same JACK session as Zynthian. `MOCK_MIDI=1` permits an offline desktop preflight.
MIDI port names are checked when supplied.

On desktop Linux, install the optional Python test packages in a virtual environment
(`lupa playwright selenium`) and select its Python for the combined runner:

```sh
HEADLESS_BINARY="$PWD/.build/midi-headless-engine" YSFX_SOURCE="$PWD/.build/ysfx" \
  NATIVE_PATCH_FIXTURE=/tmp/midi-native-patch.json \
  python3 scripts/combined-test.py --native --jack --browser chromium
# Stock Firefox ESR + geckodriver, with the same test virtual environment:
HEADLESS_BINARY="$PWD/.build/midi-headless-engine" \
  python3 scripts/combined-test.py --browser stock-firefox --timeout 90
```

`--jack` starts a separate named dummy desktop server: do not use it on Zynthian.
Production Firefox needs neither Selenium nor Playwright. The runner reports failures
and kills its subprocess group on timeout, including browser drivers and test hosts.
Chromium is desktop evidence only. Stock Firefox initialization still times out in
this restricted container; Playwright's Firefox download is blocked by the network
domain filter. Actual Firefox/Pi acceptance remains required on the device.

## Controller-enabled first demo

The Controller integration branch stacks on `fix/zynthian-first-demo`:

```sh
git fetch origin feat/controller-host-integration
git switch --track origin/feat/controller-host-integration
scripts/headless-setup.sh
scripts/headless-check.sh
EDITOR_BIND=0.0.0.0 EDITOR_TOKEN_FILE=/tmp/midi-editor-token DEMO_PATCH=1 scripts/headless-run.sh
```

In Firefox, CONNECT with the token, TEST a Smart Switch and verify downstream notes.
ADD CONTROLLER SOURCE → MIDI LEARN → move an unused Helix CC/pedal. Verify exact
channel/type/number, then ADD MAPPING to Instrument VOLUME or a phrase decay target.
Set TAKEOVER=2 (GLIDE), BACK TO STATE=1 (IDLE), GLIDE=0.2 s, IDLE WAIT=1 s and
RETURN RAMP=0.5 s. DONE; move the pedal and observe the ramp/return and audible change.
SAVE PATCH, PANIC, LOAD PATCH; verify committed bases and assignments return. Close
and reopen Firefox; the engine must continue without a browser. Perform PANIC before
stopping the launcher. Use EXPORT REAPER BASE only when transferring to REAPER.

See [Controller integration](controller-engine-integration.md) for exact limits and
the explicit REAPER extension boundary. No claim of completed Pi/Firefox acceptance
is made from desktop Chromium tests.
