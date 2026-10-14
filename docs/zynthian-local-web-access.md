# MBMF local Web access

## What is implemented

`http://mbmf.local/` opens the active existing MBMF editor. The sole live processor
is selected automatically. Recreating it or changing its ID/port needs no URL edit;
discovery refreshes at most once per second, only in the Webconf process. Multiple
live processors show a compact explicit chooser; selection uses process generation,
not just a reused processor number. UI focus never controls routing.

If multicast DNS is unavailable, use **`http://ZYNTHIAN_IP/mbmf/`** or
**`http://zynthian.local/mbmf/`**. This fallback is also processor/port independent.
Assets, API calls, uploads/downloads and WebSockets are routed through the same
entry point. No hosts-file edit or port-number lookup is needed.

The explicit local/trusted installer defaults to **`auth: none`**. The browser
opens directly; token fields are absent from the visible UI. Existing backend
tokens are retained and used internally on loopback, never inserted into browser
HTML/JavaScript, URLs, screenshots or logs. Backend ports keep their existing
authentication. This is optional **entry-point authentication**, not deletion of
backend protection. Token mode validates every API request and first WebSocket
frame before forwarding, including if the backend originally has no token.
Changing to token mode closes existing trusted telemetry streams.

None mode is for a deliberately trusted local network. Both modes reject public
Internet peers and foreign Origins; the gateway checks the TCP peer as well as
Tornado's client address. Do not publish this entry point through a public reverse
proxy or port forwarding. For an untrusted shared LAN, select token mode and use
Webconf's existing HTTPS with a properly trusted/hostname-valid certificate.
Token authentication over HTTP is not transport encryption. No firewall, router,
certificate, hostname, hotspot, JACK or LUMAZ configuration is changed.

## Native integration audit

| Existing component | Finding | Integration |
|---|---|---|
| Oram Webconf | Tornado `make_app()` already listens on HTTP 80 and HTTPS 443 | Add a specific `mbmf.local` host route and `/mbmf/` fallback; preserve ordinary Webconf/login routes |
| HTTP service | `zynthian-webconf.service` launches `zynthian_webconf.sh` | No second listener or service; reload only Webconf after explicit installation |
| Avahi | Existing `_http._tcp` Webconf service advertises port 80 under the Zynthian hostname | Add per-interface private IPv4 `mbmf.local` address records via existing Avahi D-Bus; no global hostname/daemon configuration edit |
| Home Wi-Fi/Ethernet/hotspot | Different interface addresses; multicast availability varies | Refresh interface records every 5 s in a separate Webconf thread, filtering public addresses and non-multicast interfaces |
| MBMF workers | Existing argv identifies control socket, port and token file | Inspect live `/proc` worker records outside MIDI; retain socket/session/engine implementation |

Audited public Oram source revisions: Webconf
`0e2c2556dd4db2aaddd42c8a6de8db9bd225d477`, zynthian-sys
`1ff98bebf5f73fdd8d992dc9ba7e7ddfceaee78e`. The complete Webconf source fixture
is retained for installer anchor/AST validation. Real hardware may use another
revision; preflight refuses unknown or modified anchors rather than guessing.

Only an owned startup hook, three small Python modules and private MBMF Web-access
configuration/manifest are installed. Existing root checkout, native executable,
install.json, token, patches, snapshots and other networking services remain unchanged.
The startup hook fails independently: ordinary Webconf remains available if MBMF
integration cannot load. Backup/ownership checks and caught-failure compensation
are retained. It is not a power-loss-proof multi-file transaction; preserve the
manifest/backups and inspect them after interrupted installation.

## Short in-place installation after review

As root in PuTTY, replace the SHA with the reviewed full revision. These commands
fetch into `/root/midi_human_looper` and stage installer files temporarily; they do
not switch its branch or create another clone/MBMF installation.

```sh
cd /root/midi_human_looper
MBMF_SHA=REVIEWED_40_CHARACTER_SHA
git fetch origin "$MBMF_SHA"
MBMF_STAGE=$(mktemp -d)
git archive "$MBMF_SHA" zynthian | tar -x -C "$MBMF_STAGE"
python3 "$MBMF_STAGE/zynthian/web_access/provision.py" --check --auth none &&
python3 "$MBMF_STAGE/zynthian/web_access/provision.py" --auth none &&
systemctl restart zynthian-webconf
```

Stop if preflight fails. Existing Tornado, Python D-Bus bindings, Avahi and `ip`
are required; no packages are installed by this command. Webconf must retain its
normal HTTP port 80 for the exact port-free URL; custom-port installations need
explicit review. Keep the staging path for rollback.

**Only Webconf restarts**, disconnecting Webconf/browser/terminal sessions. MBMF
workers, the Zynthian UI, synths and JACK are not restarted. There is no need to
stop MIDI performance for the software architecture, although initial physical
qualification should be done outside a concert. No new binary build is required.

To require the existing editor token instead:

```sh
python3 "$MBMF_STAGE/zynthian/web_access/provision.py" --auth token &&
systemctl restart zynthian-webconf
```

This requires an existing nonempty editor token; the installer never generates,
rotates or prints it. Repeat installation preserves the chosen mode unless an
explicit `--auth` is provided. Roll back only Web access:

```sh
python3 "$MBMF_STAGE/zynthian/web_access/provision.py" --rollback &&
systemctl restart zynthian-webconf
```

Remove the hook before upstream Webconf source updates, then reinstall the reviewed
compatible integration. Changed owned files are refused, never overwritten blindly.

## Physical V4 qualification

1. With the existing MBMF chain, open `http://mbmf.local/` in Firefox. No token
   prompt; Controller/Snapshot/PHRASE actions and PATCH SAVE/LOAD work.
2. Verify ordinary `http://zynthian.local/` Webconf is unchanged. Also test
   `http://ZYNTHIAN_IP/mbmf/` with mDNS blocked/unavailable.
3. Recreate the MBMF chain with a different processor ID/port. Reload the same
   URL: verify the new engine session and correct project; no stale editor target.
4. Move between home Wi-Fi, Ethernet and the hotspot. Allow network/mDNS caches
   to settle; test the fallback if AP client isolation blocks multicast.
5. Close Firefox and restart **only Webconf** while MIDI plays. Verify MBMF/synth
   PIDs, output, sustain and timing continue; reconnect without token entry.
6. Select token mode: unauthenticated APIs/WS fail, correct token succeeds. Then
   rollback and confirm original Webconf and editor behavior/data.

Only one `mbmf.local` alias can own a broadcast domain. An existing alias conflict
is reported; no other host is renamed. Use the IP `/mbmf/` fallback. IPv6-only
mDNS publication is not implemented; IPv4 home/Ethernet/hotspot is the initial
scope. Actual Avahi/interface changes, Firefox OS resolver behavior, hotspot
isolation, Webconf TLS/service reload and Pi audio/XRUN behavior remain physical
qualification gates. Cloud tests do not claim these passed.

## Cloud tests and coordination

Reuse the prepared environment and install only the pinned **test** dependency
into its existing virtualenv:

```sh
"$TEST_PYTHON" -m pip install -r tests/requirements-web-access.txt
scripts/web-access-test.sh
```

Fixtures use the actual native EEL engine, original HTTP worker, Tornado host
routing and Chromium. They exercise token-free POST/WS, secure auth, Origin
rejection, explicit multiple-processor selection, port/chain recreation, PATCH
SAVE and continued engine blocks after browser disconnection. Installer and
Avahi D-Bus/interface tests use explicit fixtures, not hardware validation.

Issue #54's 25 working files are unchanged. This feature adds no pairing/session
library, privileged update helper or Controller system. Separate ADMIN capability
checks must remain required. Review issue #54's future login/pairing UI together
with this entry-point policy before integration; it is not silently merged here.

Delivered Cloud results: final focused gate **exit 0**, 7 provisioning/policy/D-Bus
fixture tests and 8 production API/WS/Chromium tests; existing HTTP worker gate
15 tests **exit 0**. Selected combined command
`$TEST_PYTHON scripts/combined-test.py --web-access --timeout 240` returned **0**
(including Controller/MOVEMENT sanitizer gates and persistence/bridge tests).
`--native`, `--jack` and the general `--browser chromium` suites were not selected
in this repeat; those unchanged-source gates passed on parent #64 and are not
relabeled as rerun here. No core/server/web-source file was modified.

Actual PNGs and dimensions/hashes are in `docs/screenshots/web-access/manifest.json`;
320×240, 800×480 and 1440×900 browser viewports were captured and reviewed. The
PNGs include full-page vertical content; horizontal overflow checks passed. None
mode shows no login controls; token mode preserves its visible login controls.
Public-peer boundary checks are unit fixtures, not public-network packet tests.
