#!/usr/bin/env bash
# Known failures are explicit; --strict exits nonzero until PR B fixes them.
set -euo pipefail
cd "$(dirname "$0")/.."
: "${YSFX_SOURCE:?Set YSFX_SOURCE to the pinned ysfx checkout}"
: "${YSFX_BUILD:=$YSFX_SOURCE/build}"
: "${CONDUCTOR_BASELINE_REPORT:=$PWD/.build/conductor-baseline.json}"
[[ "$(git -C "$YSFX_SOURCE" rev-parse HEAD)" == 8077347ccf4115567aed81400281dca57acbb0cc ]]
mkdir -p "$(dirname "$CONDUCTOR_BASELINE_REPORT")"
build_dir=$(mktemp -d)
trap 'rm -rf "$build_dir"' EXIT
c++ -std=c++11 -O2 -fsigned-char -DSWELL_LICE_GDI \
  -I"$YSFX_SOURCE/include" -I"$YSFX_SOURCE/sources" \
  -I"$YSFX_SOURCE/thirdparty/WDL/source" tests/expression_host.cpp \
  "$YSFX_BUILD/libysfx.a" -ldl -lpthread -o "$build_dir/expression_host"
export CONDUCTOR_BASELINE_REPORT
report_output=$CONDUCTOR_BASELINE_REPORT
export CONDUCTOR_BASELINE_REPORT="$build_dir/report.json"
set +e
"$build_dir/expression_host" midi_human_looper.jsfx --conductor-baseline "$@"
result=$?
set -e
if [[ -f "$CONDUCTOR_BASELINE_REPORT" ]]; then
  "${TEST_PYTHON:-python3}" - "$CONDUCTOR_BASELINE_REPORT" <<'PY'
import datetime, hashlib, json, platform, subprocess, sys
from pathlib import Path
path=Path(sys.argv[1]);report=json.loads(path.read_text())
report['provenance']={
    'recordedAtUTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'checkoutCommit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
    'engineBaseCommit':'25fcb1e458ffdce7286ff4c60cd4546d586e19a4',
    'specCommit':'73cdee5604992ca3bd68e4c6c3b97c545333b127',
    'machine':platform.machine(),
    'sourceHashes':{name:hashlib.sha256(Path(name).read_bytes()).hexdigest() for name in (
        'midi_human_looper.jsfx','tests/conductor_baseline_cases.hpp','tests/expression_host.cpp')},
}
path.write_text(json.dumps(report,indent=2)+'\n')
PY
  mv "$CONDUCTOR_BASELINE_REPORT" "$report_output"
fi
exit "$result"
