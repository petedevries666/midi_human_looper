#!/usr/bin/env bash
# Read-only preflight against the existing Zynthian JACK session.
set -euo pipefail
cd "$(dirname "$0")/.."
: "${HEADLESS_BINARY:=$PWD/.build/midi-headless-engine}"
printf 'Architecture: %s (%s bits)\n' "$(uname -m)" "$(getconf LONG_BIT)"
[[ -x "$HEADLESS_BINARY" ]] || { echo 'Engine missing: run scripts/headless-setup.sh first.' >&2;exit 1; }
"$HEADLESS_BINARY" --queue-test
python3 -c 'import socket, json, http.server; print("Python runtime ready")'
if [[ "${MOCK_MIDI:-0}" != 1 ]];then
  command -v jack_lsp >/dev/null || { echo 'Install jack-tools, then run this as the Zynthian JACK user.' >&2;exit 1; }
  ports=$(jack_lsp -t) || { echo 'Cannot reach existing JACK server; do not start a second server.' >&2;exit 1; }
  printf '%s\n' "$ports"
  for endpoint in MIDI_INPUT MIDI_OUTPUT;do
    port=${!endpoint:-}
    if [[ -n "$port" ]] && ! printf '%s\n' "$ports" | grep -Fxq -- "$port";then
      printf 'Missing %s port: %s\n' "$endpoint" "$port" >&2;exit 1
    fi
  done
fi
if [[ "${EDITOR_BIND:-127.0.0.1}" != 127.0.0.1 && "${EDITOR_BIND:-127.0.0.1}" != localhost ]];then
  [[ -n "${EDITOR_TOKEN_FILE:-}" && -s "$EDITOR_TOKEN_FILE" ]] || { echo 'LAN access needs a nonempty EDITOR_TOKEN_FILE.' >&2;exit 1; }
fi
printf 'Ready. Run scripts/headless-run.sh in this same user/session.\n'
