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
