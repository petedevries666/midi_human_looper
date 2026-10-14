# AZ Local Control Hub: one address for the live rig

**Status:** Product/architecture specification only. No implementation or deployment in this PR.

## Goal

Opening **`http://az.local`** on a laptop, tablet or phone connected to the same local network as the Zynthian/LUMAZ/MBMF rig should display a **very small, fast, legible control homepage**. The address should be the same on home Wi-Fi, wired LAN and a Zynthian-hosted hotspot, without remembering the current IP address or changing MBMF's processor port.

The homepage is a launcher and a handful of deliberate operations, **not** a replacement for the full LUMAZ, MBMF or Zynthian applications. It must not affect the audio/MIDI engine during a show.

## Desired homepage

### LUMAZ

- **Admin**: open the existing LUMAZ administration interface.
- **Restart LUMAZ**: explicitly restart the LUMAZ application/service; require clear confirmation and show success/failure, without rebooting the Raspberry Pi or restarting JACK/Zynthian. Implement with a narrow, authenticated/authorized backend operation, never arbitrary shell commands from the browser.
- **HDMI TEST**: launch/open the existing HDMI output diagnostic/test functionality, or a purpose-built bounded test if none exists. Do not change live HDMI output without confirmation.
- **VIDEO SETTINGS**: open the existing LUMAZ video settings.
- **AUDIO SETTINGS**: open the existing LUMAZ audio settings.
- **MIDI SETTINGS**: open the existing LUMAZ MIDI settings.

These are product requirements. Inspect LUMAZ's real current routes/APIs before implementing; do not invent endpoints or assume each setting has its own deep link. Where only one settings page exists, link there until a specific route is implemented.

### MIDI BAD MOTHERFUCKER

- **OPEN MBMF**: open the current MBMF Web app directly, without users knowing the active processor instance, changing port (e.g. 8766/8767), IP address, or manually copying a token.
- Find the actual active instance through the supported Zynthian/MBMF runtime state. If MBMF is absent, show a helpful *not running / not loaded* state instead of a dead link.
- Avoid exposing MBMF's unauthenticated write API to arbitrary untrusted networks. A trusted-local-network no-token mode may be explicitly configured; never assume that all hotspot or Wi-Fi clients are trusted.

### ZYNTHIAN

- **REMOTE SCREEN**: intended target currently `http://zynthian.local:6080/vnc.html`, **reported not working today**. Diagnose whether a remote desktop/VNC server, websockify/noVNC, correct display, and route actually exist before wiring a working link. Expose via the AZ homepage only once verified; otherwise show a clearly labeled unavailable/diagnostic state.
- **CONFIG / WEBCONF**: intended target currently `http://zynthian.local/`, **reported intermittently unreachable**. Distinguish name resolution failures from service failures, port/proxy conflicts, and Wi-Fi/hotspot interface binding. Use a verified local endpoint and retain Zynthian's normal configuration service.

The URLs above are **expected/desired** addresses, not verified working routes.

## Networking and architecture requirements

1. **One simple URL:** `http://az.local`. Resolve the same hostname when the user switches between home Wi-Fi, Ethernet, and the device hotspot, as long as the client and network support mDNS. Advertise using Avahi/mDNS or a supported equivalent; assess hostname/alias collisions and avoid breaking `zynthian.local`. Document that mDNS may not work on some client OS configurations or guest networks, and provide an IP fallback.
2. **One stable entry point:** Investigate who already owns TCP port 80 (Zynthian Webconf, LUMAZ, other service). Integrate with the existing HTTP server/reverse proxy or use a carefully planned virtual host/alias. **Do not blindly bind port 80, displace Webconf, or reconfigure the OS hostname.** Prefer same-origin paths such as `/lumaz/`, `/mbmf/`, `/zynthian/` where technically feasible. Handle WebSockets, absolute URLs, subpath assumptions, and reverse-proxy headers if needed.
3. **Dynamic MBMF:** Survive processor recreation, port changes, service restart, and chain/snapshot changes without hard-coded `mbh_1`, fixed port, or synth names. Never scan/modify the JACK graph on the audio thread.
4. **Reliable state:** Display simple availability indicators or a concise error only when a service cannot be reached. No endless browser spinner and no false *running* indicator. Diagnostics must not generate XRUNs or interfere with show-critical processes.
5. **Security:** Keep the homepage LAN-only, not publicly exposed. Read-only navigation can be frictionless. Destructive/interruptive operations such as LUMAZ restart or HDMI test need explicit confirmation and a constrained authorized endpoint. Do not put raw shell access, static admin credentials or tokens into HTML/JS. Preserve optional authentication for untrusted networks.
6. **Presentation:** Extremely basic, attractive, responsive, touch-friendly; a few clear groups and buttons, no dashboard clutter. Should remain useful even when one of the three applications is down.
7. **Deployment:** In-place update on the existing Zynthian installation, no second clone or duplicate runtime. Idempotent setup and clean rollback. No merge or hardware deployment without user approval.

## Discovery before implementation

- Inspect `petedevries666/lumaz` and identify the actual admin/settings/HDMI test/restart interfaces and service names.
- Inspect MBMF's headless server and native Zynthian integration for dynamic discovery and authentication.
- Inspect Oram's existing Webconf, mDNS/Avahi, hotspot, noVNC and port bindings **on the target system**, not by assuming the sample URLs are functional.
- Decide whether the AZ homepage belongs in a small shared launcher/service rather than embedding cross-project LUMAZ/Zynthian functionality inside the MBMF engine. MBMF repo holds this cross-project specification initially; implementation location is an explicit architecture decision.

## Acceptance criteria

- [ ] `http://az.local` opens the homepage from home Wi-Fi, Ethernet and the rig's hotspot on supported mDNS clients; fallback documented.
- [ ] LUMAZ Admin, Restart, HDMI Test, Video Settings, Audio Settings and MIDI Settings are accessible through verified routes/actions.
- [ ] LUMAZ restart has confirmation and reports actual completion/failure, without rebooting Zynthian or JACK.
- [ ] MBMF opens directly when its processor is loaded, despite instance/port changes, with an understandable unavailable state otherwise.
- [ ] Zynthian Remote Screen is **actually functional**, not merely linked to the currently broken `:6080/vnc.html` URL.
- [ ] Zynthian Config opens reliably, including after switching network modes; diagnose and fix intermittent reachability rather than masking it.
- [ ] Existing Zynthian Webconf, LUMAZ video/audio/MIDI playback, and MBMF JACK routing are not regressed.
- [ ] No dependency on a browser connection during live performance; no measurable audio/MIDI disruption.
- [ ] Document tested client/network combinations, security tradeoffs, recovery path and minimal deployment steps.

## Delivery plan

**Phase A: Audit and route matrix.** Confirm real services, current paths, port ownership, hostname and hotspot behavior, and why Zynthian's remote screen/Webconf currently fail.

**Phase B: Minimal AZ homepage and name resolution.** Deliver `az.local` with stable launcher links, honest service status, and MBMF dynamic routing.

**Phase C: Integrated operations.** Wire LUMAZ restart/HDMI test/settings and repair/enable the Zynthian remote screen and stable Webconf access.

Do not claim these phases are complete merely because the specification is merged. Keep separate implementation PRs reviewable. This work is independent of PR #64's Oram MIDI OUT routing and the future per-PHRASE output-channel feature.
