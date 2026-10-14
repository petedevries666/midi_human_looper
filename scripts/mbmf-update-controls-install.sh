#!/usr/bin/env bash
# Explicit bootstrap only. Never restart JACK, Zynthian or LUMAZ.
set -euo pipefail
cd "$(dirname "$0")/.."
[[ $EUID == 0 ]] || { echo 'Run as root.' >&2; exit 1; }
root=$PWD
[[ "$root" != *$'\n'* && "$root" != *' '* ]] || { echo 'Checkout path cannot contain whitespace.' >&2; exit 1; }
for file in scripts/mbmf-update-control.py scripts/zynthian-update.py zynthian/update/backend.py; do
  [[ $(stat -c %u "$file") == 0 ]] || { echo 'Root-owned updater source required.' >&2; exit 1; }
  mode=$(stat -c %a "$file")
  (( (8#$mode & 0022) == 0 )) || { echo 'Updater source cannot be writable by other users.' >&2; exit 1; }
done
python3 scripts/mbmf-update-control.py --configure
unit=/etc/systemd/system/mbmf-update-control.service
if [[ -e "$unit" ]] && ! grep -q '^# MBMF-owned update worker$' "$unit"; then
  echo 'Refusing to replace an unrelated service.' >&2; exit 1
fi
staged=$(mktemp /etc/systemd/system/.mbmf-update-control.XXXXXX)
trap 'rm -f "$staged"' EXIT
cat > "$staged" <<EOF
# MBMF-owned update worker
[Unit]
Description=MBMF reviewed update control worker
After=network.target
[Service]
Type=simple
ExecStart=/usr/bin/python3 $root/scripts/mbmf-update-control.py
Restart=on-failure
RestartSec=3
RuntimeDirectory=mbmf-update-control
ExecStartPre=/usr/bin/rm -f /run/mbmf-update.sock
[Install]
WantedBy=multi-user.target
EOF
chmod 644 "$staged"
mv "$staged" "$unit"
systemctl daemon-reload
systemctl enable --now mbmf-update-control
printf 'Update worker enabled. No musical service restarted.\n'
