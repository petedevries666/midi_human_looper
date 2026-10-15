#!/usr/bin/env bash
# Install only reviewed Webconf helpers from the existing checkout. No restart.
set -euo pipefail
ref='';mode=();operation=--hub
while (($#));do
    case "$1" in
        --ref) ref=${2:?Missing reviewed Git reference};shift 2;;
        --trusted-local) mode=(--auth none);shift;;
        --check) operation=check;shift;;
        --rollback) operation=--hub-rollback;shift;;
        *) echo "Usage: --ref REVIEWED_SHA [--trusted-local] [--check | --rollback]" >&2;exit 2;;
    esac
done
[[ -n "$ref" ]] || { echo 'An explicit reviewed Git reference is required' >&2;exit 2; }
cd "$(git rev-parse --show-toplevel)"
sha=$(git rev-parse --verify --end-of-options "$ref^{commit}")
stage=$(mktemp -d /tmp/az-hub-install.XXXXXXXX)
trap 'rm -rf "$stage"' EXIT
# This ephemeral staging directory is not a clone or another runtime. The live
# checkout/JSFX, processor installation and musical project data are untouched.
git archive "$sha" zynthian/web_access zynthian/install.py | tar -x -C "$stage"
args=("${mode[@]}" --hub)
if [[ "$operation" == --hub-rollback ]];then args=(--hub-rollback);fi
/usr/bin/python3 "$stage/zynthian/web_access/provision.py" "${args[@]}" --check
if [[ "$operation" != check ]];then
    /usr/bin/python3 "$stage/zynthian/web_access/provision.py" "${args[@]}"
fi
printf 'AZ helpers: %s\nNo service restarted. Reload only zynthian-webconf when ready.\n' "$sha"
