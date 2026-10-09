# Desktop headless feasibility proof (issue #7, M0)

This runs the **actual v1.27.1 JSFX engine**, compiled without `@gfx`, in an autonomous
Linux desktop process. A separate Python HTTP worker serves a browser monitor and
queues TEST TAP/DOUBLE/HOLD, simulated Note MIDI and PANIC commands through a Unix
socket. Closing Firefox or restarting the HTTP worker leaves the engine running.

The startup fixture provides VERSE (note 72 → a repeating phrase on note 60) and
CHORUS (note 73 → an ONCE phrase on note 64), sixteen phrase rows, the three existing
Instrument panels and four Smart Switch cards. It uses the existing action dispatcher
and phrase scheduler, not a Python/browser imitation. LOOP resumes its existing
sample position; it does not restart solely because the remote editor reconnects.

This is a diagnostic proof, **not** the remote production editor: no configuration
edits, Learn lease, patch files, real MIDI devices, LV2 bundle or Zynthian deployment.
There is no service installer and nothing runs automatically on REAPER startup.
Production migration requires the [architecture audit](../../docs/zynthian-headless-audit.md).

## Build and run

Use the existing ysfx checkout when available. This cloud workspace has the pinned
checkout and static library at `/workspace/setup-tools/ysfx`. Elsewhere, follow the
[existing native-host setup](../../docs/expression-assignments.md#automated-verification)
using commit `8077347ccf4115567aed81400281dca57acbb0cc`; build the library with
`-DYSFX_PLUGIN=OFF -DYSFX_TOOLS=ON -DCMAKE_BUILD_TYPE=Release`. The proof's internal
VM bridge deliberately pins that version. C++11, pthreads and Python 3 are required.

From the repository root:

```sh
YSFX_SOURCE=/workspace/setup-tools/ysfx experiments/headless/build.sh
/tmp/midi-headless-engine midi_human_looper.jsfx /tmp/midi-engine.sock
```

In a **separate terminal**, start the worker; it does not launch/stop the engine:

```sh
python3 experiments/headless/server.py --socket /tmp/midi-engine.sock --port 8765
```

Open `http://127.0.0.1:8765` in Firefox. Click VERSE TEST TAP or SIMULATE FOOTSWITCH.
Observe MIDI counts rising, stop/restart the web worker, then reconnect: sample clock
and output continue. PANIC stops playback and releases active notes. Stop the engine
explicitly with Ctrl-C when finished. Socket paths must be unused; an existing socket
is never deleted on startup. Output here is a diagnostic sink, **not** audible MIDI.

Loopback is the default. For a trusted-LAN experiment, pass an explicit bind and a
nonempty `--token-file`; the browser sends the token in a header, never a URL. The
worker rejects cross-origin requests. Do not treat this minimal HTTP proof as a
production authenticated/TLS service. No commands accept arbitrary code or addresses.

## Boundaries demonstrated

- EEL compilation, fixture setup, pointer caching and memory warmup happen at startup.
- Fixed 64-entry command/acknowledgement queues; at most eight commands per block.
- Only the scheduler thread reads engine state or runs EEL2. HTTP/socket/JSON work
  stays in the control thread or separate worker. Snapshot structs have fixed sizes.
- Command ID, immutable revision 1, stable switch ID and input-range checks; rejected
  commands do not trigger performance. TEST uses the existing switch dispatcher.
- Fixed-capacity MIDI buffers and bounded output diagnostics. A slow socket client
  blocks its control response, while engine scheduling continues.
- The engine session ID survives HTTP-worker restarts. Browser timers only poll status.

The desktop scheduler uses `sleep_until` at 128 frames / 48 kHz. Callback metrics and
late-block counts expose the software clock's limits; this is not a hard-RT callback
or a Pi latency benchmark. No maximum-latency guarantee is inferred from this proof.
A production host must use JACK/ALSA or LV2 callback timing and audit all allocations,
locks, sustained traffic and ownership at full collection capacity on the actual Pi.

## Regression commands and evidence

```sh
HEADLESS_BINARY=/tmp/midi-headless-engine python3 experiments/headless/test_headless.py
```

Seven actual-engine/HTTP tests cover bounded FIFO, independent note 72/73 routing,
TEST gestures, PANIC, worker restart, stale revisions/ranges/origin rejection,
malformed local input and a stalled client while playback continues.

Optional browser tests use Playwright (a separate test dependency, not required to
run the editor). Firefox is the default:

```sh
python3 -m venv /tmp/midi-browser-env
/tmp/midi-browser-env/bin/pip install playwright
PLAYWRIGHT_BROWSERS_PATH=/tmp/midi-browser-cache /tmp/midi-browser-env/bin/python -m playwright install firefox
PLAYWRIGHT_BROWSERS_PATH=/tmp/midi-browser-cache /tmp/midi-browser-env/bin/python experiments/headless/test_browser.py
```

In this cloud environment Firefox downloads returned HTTP 403 from the network
filter. The installed Chromium was used for the real-browser smoke instead:

```sh
MIDI_BROWSER=chromium /tmp/midi-browser-env/bin/python experiments/headless/test_browser.py
```

That checks sixteen phrases, visible Instrument panels, compact switches, disabled
unassigned TEST buttons, real TEST/simulated input/PANIC, mobile-width layout, web
restart/reconnect, and continued MIDI after closing the real browser. A screenshot
is written to `/tmp/midi-headless-browser.png`. Firefox on the user's PC and actual
Pi/Zynthian/Helix acceptance are still outstanding.

The unchanged REAPER engine also passes 2,289 native EEL2/GUI/MIDI checks (three
concurrent render cases retain one hash) plus four real Lua SAVE/LOAD tests. The
headless audit exposed and fixed committed-vs-draft cold-start initialization in
PR #13, with the fix propagated through #14/#15 and fresh-start regressions.
