# MBMF: Live pedal controls, MIDI diagnostics and safe updates

Status: **requirements only**. This document does not implement, merge, install or deploy anything. Independent documentation branch from `main`. Implementation should be delivered in **two separate focused draft PRs** against the current reviewed implementation stack, without modifying protected issue #54 work.

## A. Live pedal controls and MIDI log (implementation PR A)

### Native Zynthian MBMF controller
- Expose **BYPASS ON/OFF** with clearly visible state and **RESTART SERVICE**.
- RESTART SERVICE means restarting only the MBMF runtime/processor, **not** restarting all Zynthian UI, JACK, synths, Webconf or unrelated chains. Audit whether per-processor restart is actually supported. If not, do not disguise a global restart as MBMF-only; implement a safe MBMF-specific lifecycle operation or report the blocker. Explicit confirmation when interruption is expected.
- A restart may interrupt MBMF playback. Release owned notes safely, retain user project/configuration, and restore correct stopped/bypass state. No restart while performance is in progress without explicit action.

### BYPASS = transparent MIDI THRU, **not mute**
- MBMF is an intelligent MIDI pedal. When bypass is **ON**, pass incoming MIDI through **unchanged**: original channel, pitch, velocity, CC, sustain, pitch bend and other relevant MIDI events; do not run PHRASE, MOVEMENT, ARP or other internal generators/transformations.
- When bypass is **OFF**, resume the configured MBMF processing.
- Preserve the **native filtered Zynthian routing** from #67; never connect directly to named synth JACK ports or bypass the router.
- Native Zynthian BYPASS and Web toolbar BYPASS must control **one shared runtime state**, with visible synchronized feedback, including after browser reconnect and processor recreation.
- At transitions, release only MBMF-owned generated notes/held controls without silencing physical MIDI notes or other synth chains; preserve correct Note On/Off ownership and sustain behavior. No duplicates if the original physical input already has an independent route into the same synth. Validate this case explicitly and explain how the native input graph avoids double delivery.
- Define treatment of real-time/system MIDI events from existing implementation; preserve original data where supported. No MIDI processing/discovery on the audio thread beyond bounded real-time-safe work.

### Web toolbar and collapsible MIDI LOG
- Prominent **BYPASS** toggle in Web editor header.
- Compact **collapsible live MIDI LOG** that can remain open while testing PHRASES and MOVEMENTS; does not cover the working editor. Display actual **emitted** MIDI events *after* output channel remapping, not merely scheduled events. Include timestamp, event type, channel, note/velocity, CC number/value, pitch bend as relevant, and source where safely available (physical THRU / phrase / movement / arp).
- PAUSE and CLEAR controls, bounded ring buffer, opt-in streaming/low-cost sampling if needed, no unbounded memory growth or blocking/logging on real-time MIDI thread; no extra dependency on browser for live operation.
- Test CH2 note/CC emission, phrase override from #68, MOVEMENT's **explicit channel** (do not introduce inheritance), BYPASS THRU, rapid toggles with held notes and sustain, Web disconnect/reconnect and processor recreation. Keep #67 filtered routing and #68 phrase overrides intact.

## B. In-place UPDATE from Web and Zynthian device (implementation PR B)

- First audit existing updater/install/rollback and exactly what can be updated independently: MBMF native engine, Zynthian adapter/router integration, Web editor, Webconf access.
- Expose **CHECK FOR UPDATES / UPDATE** in both the MBMF Web editor and Zynthian native MBMF menu. Both use **one common verified updater**, not two divergent implementations.
- Display installed version/commit and available version; provide release/approved SHA selection or a safe release channel, change summary, affected components, preflight status, and explicit confirmation. Never silently update to a moving branch head.
- Preserve existing checkout, projects, snapshots, tokens/auth configuration, Zynthian settings and unrelated services. No second clone, no broad system upgrade, no overwriting user modifications. Update only owned components, with validated backup, atomicity where possible, idempotence, version compatibility checks and **ROLLBACK**.
- Detect dependency ordering across #64/#66/#67/#68 and refuse incompatible combinations instead of deploying partial breakage. If the reviewed code is still draft/unmerged, do not offer it as an automatic update.
- Update requires network for fetching, but **live performance must never require network or a browser**. Never perform updates/restarts automatically during playback; preflight and confirm downtime, then restart only the necessary components.
- Authenticated/authorized UPDATE endpoints even if trusted-local editor uses tokenless access. Do not let any unauthenticated LAN visitor remotely update executable code. Protect against CSRF and arbitrary SHA/path injection; restrict to trusted signed/approved release artifacts or explicitly authorized local admin action. Keep Web and device confirmation appropriate to each UI.
- Include clear failure recovery, offline fallback via existing in-place CLI, concise Zynthian V4 deployment/rollback instructions and a few targeted tests.

## Delivery discipline
- Two separate **draft implementation PRs**, each with short summary, tests, known limits, hardware validation checklist, and exact reversible deployment steps.
- **No merge, no deploy, no unnecessary networking changes.** Do not touch issue #54 working files. Do not change Instrument OUT ALL, MOVEMENT channel semantics or native #67 routing.
- Keep scope focused: implement the working behavior, not a prolonged architectural exploration.
