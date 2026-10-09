#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
: "${YSFX_SOURCE:?Set YSFX_SOURCE to a ysfx source checkout (see docs/expression-assignments.md)}"
: "${YSFX_BUILD:=$YSFX_SOURCE/build}"
test -f "$YSFX_BUILD/libysfx.a"
build_dir=$(mktemp -d)
trap 'rm -rf "$build_dir"' EXIT
c++ -std=c++11 -O2 -DSWELL_LICE_GDI -I"$YSFX_SOURCE/include" -I"$YSFX_SOURCE/sources" -I"$YSFX_SOURCE/thirdparty/WDL/source" tests/expression_host.cpp "$YSFX_BUILD/libysfx.a" -ldl -lpthread -o "$build_dir/expression_host"
git show fa200857:midi_human_looper.jsfx > "$build_dir/baseline.jsfx"
# Exercise lifecycle calls inside the actual processing callback, never by
# pretending an external EEL evaluation is a DSP thread.
python3 - "$build_dir/scheduled.jsfx" <<'PY_SCHEDULE'
from pathlib import Path
import sys
source = Path('midi_human_looper.jsfx').read_text()
marker = 'scheduled_tick();scheduled_clock+=samplesblock;'
assert source.count(marker) == 1
fixture = """test_schedule_command==1 ? scheduled_cancel(0,0,0);
test_schedule_command==2 ? scheduled_finish_voice(0,0,1);
test_schedule_command==3 ? i_remove(test_gi,mem[I_IDS_BASE+test_gi]);
test_schedule_command==4 ? release_phrase_notes();
test_schedule_command=0;
"""
Path(sys.argv[1]).write_text(source.replace(marker, fixture + marker))
PY_SCHEDULE
"$build_dir/expression_host" midi_human_looper.jsfx "$build_dir/baseline.jsfx" "$build_dir/scheduled.jsfx"
if [[ ${1:-} == --historical ]]; then
  for revision in 7b439238 e82429d 4056c906; do
    git show "$revision:midi_human_looper.jsfx" > "$build_dir/$revision.jsfx"
    "$build_dir/expression_host" "$build_dir/$revision.jsfx" --historical
    # Isolate the cause without changing colors, panel layout or badge drawing.
    python3 - "$build_dir/$revision.jsfx" "$build_dir/$revision-isolated.jsfx" <<'PY2'
from pathlib import Path
import re
import sys
source = Path(sys.argv[1]).read_text()
start = source.index('\n@gfx ')
gfx = source[start:]
for name in ('ci', 'eti'):
    gfx = re.sub(r'\b' + name + r'\b', 'ui_' + name, gfx)
Path(sys.argv[2]).write_text(source[:start] + gfx)
PY2
    "$build_dir/expression_host" "$build_dir/$revision-isolated.jsfx" --isolated
  done
fi
