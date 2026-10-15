# AZ local control hub — same Raspberry Pi MVP

Implementation of the [PR #65 contract](https://github.com/petedevries666/midi_human_looper/blob/da038bd68b2dc939be0b057fc32517846f59d8d5/docs/az-local-control-hub.md), stacked on #66.
LUMAZ and Zynthian share one Pi (confirmed by the user). This is a small launcher
inside the **existing Webconf server**, not an application clone or another daemon.
`az.local` is the portal; `mbmf.local` remains exclusively the MIDI editor.

## What works

- Three compact sections, desktop/mobile, keyboard/touch, honest checked status.
- MBMF discovery reuses #66's exact process/socket/generation validation and proxy.
  No fixed processor or port; multiple processors retain explicit selection.
  `/mbmf/` also works on the portal when a client cannot resolve `mbmf.local`.
- LUMAZ **Options**: confirmed Restart Service, Video Settings, Audio Settings,
  MIDI Settings. Full application editing stays on the physical touch screen.
- Video: original AUTO / FAST / QUALITY scaler profiles, persisted preference,
  HDMI output-lock display and confirmed five-second test. It stops the old video;
  it does **not** resume it. A newer native playback supersedes test cleanup.
- Audio: SAMPLER / EDITOR / SHOWCASE enabled states and detected named outputs,
  using device-installed `audio_playback.py` load/save and device interpretation.
  Preferences apply at the next playback; no global JACK/audio restart.
- MIDI: VIDEO COMMANDS IN, LIGHT CAPTURE IN, MIDI THROUGH IN and OUTPUT SETTINGS,
  using installed `midi_routing.py` discovery/load/save and the native
  `reload_midi_routes` datagram. It reconfigures **LUMAZ's own routes only when
  the operator saves**. A missing control socket restores prior file contents.
  The datagram has no acknowledgement: “reload requested” is not hardware proof.
- Restart affects only `video-jack-trigger.service`, with the audited
  `/usr/bin/python3 /root/video_jack_trigger.py` command. Requires JACK already
  active; never starts/restarts JACK, MPV, the Zynthian UI or MBMF. Video MIDI
  triggers pause during restart. It can recover an inactive helper.
- LUMAZ mutations reuse Webconf's signed `user=root` login, strict local/same-origin
  policy, CSRF and validated fixed actions. No new password/token to manage;
  MBMF trusted-local navigation remains token-free. Restart/test need confirmation.
- Webconf and noVNC links use the private interface actually reached by the client,
  avoiding a second dependency on `zynthian.local` resolution. Remote Screen is
  online only after both its HTML and WebSocket **RFB** greeting succeed on
  that same interface, detecting loopback-only bindings. Client firewall / AP
  isolation still requires physical verification.

## Intentionally not duplicated

Video Crop/Reframe, Safe Zone, HDMI re-adoption, proxy building; audio test tools;
MIDI Monitor and LUMAZ command-channel selection remain on the touch screen.
This is a functional subset of the three native menus, **not complete menu parity**.
No MBMF engine, routing, project schema or LUMAZ Python sources are patched.

The portal preserves unknown settings fields, refuses stale web revisions, and
uses atomic file replacement. Do not simultaneously edit the **same** LUMAZ
settings on the touch screen and Web: the native GUI does not share a transaction
lock, and its in-memory video preference may need reopening/reinitialization to
reflect an external change. Audio/MIDI menus already reread native settings.

## Source audit

Read-only upstream inspection, no device access:

- LUMAZ `e148b7f04c864b422c067b055d104b6fbd6e86ca`:
  `overrides/zyngui/zynthian_gui_lumaz.py` (`show_*_settings_menu`, scaler/audio
  callbacks); `src/audio_playback.py`, `src/midi_routing.py`;
  `scripts/deploy.sh` installs those helpers to `/root/*.py`;
  Admin's MPV socket `/tmp/mpvsocket`, existing lavfi test;
  `systemd/video-jack-trigger.service`. **No LUMAZ Web Admin routes exist there.**
- Oram `zynthian-sys/etc/systemd/novnc0.service`: noVNC/websockify port 6080,
  RFB target localhost:5900. Existing Webconf owns 80 and 443.
- The actual Pi's intermittent Webconf/VNC failures are **not diagnosed remotely**.
  The implementation distinguishes HTTP login, noVNC HTML, failed RFB and alias
  failures; it does not auto-enable/reconfigure these services.

## Installation/update after review — existing checkout only

Run manually on the Pi, **not during a show**. No native build, checkout switch,
clone, packages or OS/network configuration changes. Use a reviewed SHA in place
of `REVIEWED_SHA`, from the implementation PR. Fetching does not change the running
musical branch, including #67/#68 routing work.

```bash
cd /root/midi_human_looper
git fetch origin feat/az-local-control-hub
AZ_REF=REVIEWED_SHA
git show "$AZ_REF:scripts/az-hub-install.sh" | bash -s -- --ref "$AZ_REF" --trusted-local
```

On success only, reload the HTTP service:

```bash
systemctl restart zynthian-webconf
```

That reconnects Webconf/portal browsers and republishes aliases. It does **not**
restart the MBMF processor, Zynthian UI, audio or JACK. Omit `--trusted-local` to
preserve the existing editor auth mode; the flag explicitly selects #66's LAN-only
no-token mode, preserving the saved token file. Do not forward these ports to the
Internet or trust unknown hotspot clients. No authentication option is removed.

Installer preflight checks existing Tornado/D-Bus/ip dependencies, Webconf hook,
file ownership and hashes. Updates share #66's one manifest and content-addressed
original backups; installation is transactional. Refuses unrelated changes instead
of overwriting them. `--check` is read-only. Temporary staging is removed on exit.

Open **http://az.local**. Without mDNS: **http://PI_IP/az/**. Webconf must already
listen on port 80 for the port-free alias. A custom `ZYNTHIAN_WEBCONF_PORT` is
honored for probes/links; use its explicit port in the fallback URL.

Rollback only the hub, retaining MBMF entry/auth and all project data:

```bash
git show "$AZ_REF:scripts/az-hub-install.sh" | bash -s -- --ref "$AZ_REF" --rollback
systemctl restart zynthian-webconf
```

Full #66 `provision.py --rollback` remains supported separately; that removes **both**
Webconf additions. Do not downgrade to #66's old provisioner while hub files are
owned: its manifest check will deliberately refuse the extra files.

## Physical check / access recovery

Read-only diagnostics, no automatic repair:

```bash
systemctl is-active zynthian-webconf avahi-daemon novnc0 vncserver0 video-jack-trigger mpv-drm jack2
ss -ltnp | grep -E ':(80|443|5900|6080)\b'
curl -I http://127.0.0.1/login
curl -I http://127.0.0.1:6080/vnc.html
journalctl -u zynthian-webconf -n 30 --no-pager
```

If `/login` fails locally, inspect Webconf service/binding before blaming mDNS.
If the page works by IP but `az.local` does not, inspect the Avahi log for collision,
interface multicast, client mDNS support or AP isolation; use the IP fallback.
If noVNC HTML loads but the portal reports offline, check `vncserver0` / RFB and
WebSocket reachability. Enable Remote Screen through normal Zynthian settings if
wanted; **the installer never starts it**. Self-signed/TLS-only or custom noVNC
ports are currently reported unavailable, not guessed as working.

On home Wi-Fi, Ethernet and hotspot, manually verify the alias and IP fallback,
open the actual synth screen through noVNC, MBMF API/WS/recreation, restart LUMAZ,
video/audio/MIDI settings and their persistence, then confirm MBMF MIDI continues
with all browsers closed. Compare CPU/XRUN before/after on the real Pi. Cloud
fixtures cannot certify those hardware/network combinations.

## Cloud validation and screenshots

Prepared native/Chromium environment (AGENTS.md):

```bash
TEST_PYTHON=/path/to/venv/bin/python HEADLESS_BINARY=.build/midi-headless-engine scripts/az-hub-test.sh
```

Runs installer/alias fixtures, existing real native/editor gateway tests, and the
real Tornado hub/Chromium. LUMAZ settings use unmodified production helper fixtures;
MPV IPC, systemd, JACK physical-port listing, Webconf login and RFB are peripheral
fixtures. No Pi services are changed. Screenshots are actual browser PNGs under
`docs/screenshots/az-hub/`; provenance is in its manifest. Expected denied requests
(401/403/409/404) are asserted tests, not suppressed errors.

[Desktop](screenshots/az-hub/portal-1440.png) · [Mobile](screenshots/az-hub/portal-390.png)
· [LUMAZ options](screenshots/az-hub/options-390.png)
· [Video](screenshots/az-hub/video-390.png) · [Audio](screenshots/az-hub/audio-390.png)
· [MIDI](screenshots/az-hub/midi-390.png)

### Executed result

`scripts/az-hub-test.sh`: **exit 0**, 9 provision/alias tests, 9 existing native
HTTP/editor/WebSocket tests, 5 AZ integration/browser tests (**23 total**).
Native binary rebuilt from this branch's unchanged musical sources; bounded FIFO
build check passed. Python compilation, JavaScript syntax, shell syntax and
`git diff --check` passed. The final browser run exercises actual settings saves,
confirmed/cancelled restart, stale revisions, delayed real-response navigation,
processor recreation and token-free native editor access. All seven hub PNGs and
four regenerated gateway PNGs were inspected. See `docs/evidence/az-hub/`.

No JACK server or physical Pi was used. MPV/systemd/physical MIDI-port listing,
login and VNC are fixtures; no hardware performance or network qualification is
claimed. All 25 protected issue-54 files remained byte-identical.
