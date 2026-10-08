# Expression assignments: v1.21.0 audit and usage

## Confirmed regression cause

The audio and GUI sections execute independently but share ordinary EEL2 globals.
The regression reused two audio scratch variables in GUI loops:

- `eti`: v1.20.2 commit `7b439238`, shared-editor mapping at lines 2287–2297 and assignment/badge reads at 2307–2312, versus the audio expression loop at 1227–1234. A redraw could observe a different instrument/parameter halfway through a row; the GUI could also corrupt audio target addressing. The same collision persists at `4056c906` lines 2294–2331.
- `ci`: `4056c906` MIDI CC handling at line 1350, versus GUI meter iteration at 2342–2352, popup iteration at 2580–2584 and options at 2591–2596. Concurrent incoming CC messages could change controller names, positions, values and popup choices halfway through a frame.

These are confirmed causes, rather than conclusions inferred from the symptom. The
native WDL EEL2/LICE test loads the **complete historical scripts**, assigns all
legacy targets, fixes the controller position at 0.5, selects VELOCITY and opens
its curve. One thread renders 200 frames while another processes audio blocks
with an unmapped CC119 message. With no changing musical controls, the historical
versions yielded **31, 9 and 22 distinct framebuffer hashes** for v1.20.2,
v1.20.3 and v1.20.4 in the recorded run. The scheduling-dependent counts vary.
Changing **only GUI `ci` and `eti` names** in temporary copies yields one distinct
frame in all three versions. No colors, badge style, panel geometry, curve code
or `gfx_dest` behavior change in that isolation experiment.

The final implementation uses GUI-specific scratch names and function-local
variables. It also gives the GUI its own curve evaluator, so GUI curve sampling
does not reuse audio evaluator scratch. The latter is additional isolation;
the minimal regression experiment does not establish it as another independent
cause of the original flashing.

Other audited defects:

- The historical HOLD row was assigned to `EXP_T_ARP_ON`, writing the enable flag
  instead of `INST_ARP_HOLD_BASE`. HOLD now has its own identity and storage.
- `draw_exp_badge` in v1.20.2 leaked `ss`, `st` and `sx` into the GUI namespace and
  painted controller names/full graphs inside 11px rails. v1.20.3 localized those
  variables and reduced the badge, but left the confirmed `ci`/`eti` races.
- Assignment-driven curves were auto-opened without resetting drag state; popup
  input could reach underlying controls. Menus now own input for the entire
  frame, including dismissal. Curves open explicitly below the shared editor.
- The old curve renderer wrote endpoint X values on every redraw. Initialization,
  presets and constrained edits now establish invariants; redraw does not write
  musical memory.
- CC/MOD's CC-number row used the **volume** destination, while modulation still
  emitted CC1. The new modulation destination defaults to CC1 and actually
  controls the modulation output; the old volume destination remains intact.

## Interaction and identities

Right-click a transformer parameter or instrument VOLUME rail, then choose NONE
or one of the four named controllers. An assigned rail has a fixed yellow border
and marker; the transformer row also names its controller. Left-click an assigned
rail to open its own multipoint curve. CLOSE CURVE closes it. NONE retains the
last sounding value, cancels queued controller changes and restores manual drag.
Popups dismiss on outside click or Escape without activating controls behind them.

The compact ARP ON/OFF control in the existing editor header exposes the preserved
legacy enable parameter; it too supports right-click assignment and curve editing.
HOLD remains a separate row. A positive ARP block alone does not override a
controller-assigned enable value.

The model has 14 kinds per instrument (42 independent parameter identities): the
seven original kinds plus transpose, range mode/low/high, polyphony note mode,
ARP HOLD and modulation CC number. All twelve requested transformer rows and
instrument volume are supported; the original ARP enable target is retained.
`param_ti(instrument, kind)` preserves IDs 0–20 for old targets and assigns new
IDs from 21. Chain position, selection and screen coordinates never enter storage
identity. Duplicate transformer types remain forbidden, including bypassed ones.
Removing/readding a transformer retains its instrument/type parameter settings
and assignments. Selection changes only transient GUI state.

`param_editor_kind`, `param_addr`, `param_min/max/step`, `param_name`,
`param_scale` and `param_apply` centralize the editor-to-engine mapping. Enums and
toggles use equal-width bins with a clamped endpoint; MIDI CC/note numbers and
semitones round into valid integer ranges. Velocity and gate resolve to .01;
rate resolves to .25. Curve evaluation is continuous before parameter quantization,
rather than first reducing every controller to 128 steps. Existing saved curves
retain their normalized meaning; continuous targets can now have finer values.

## MIDI safety and limits

GUI manual edits are queued for `@block`; redraw never emits MIDI. Controller
values are evaluated independently of which editor is visible. Changes to
transpose, range mode/boundaries, polyphony mode and ARP enable **wait until all
source notes for that instrument release**. The most recent requested value wins;
NONE cancels a deferred controller write. Existing note-offs therefore pass
through the same transform as their note-ons, with no modulation-triggered panic
burst. Rejected notes are counted too, so changing a filter cannot invent a
corresponding output Note Off. Phrase-owned input counts are retired on choke;
manual and phrase input ownership remain distinct.

This deliberate policy delays those changes during sustained source notes or
very dense overlapping performances. It does not retune an already sounding
note. Sustain-pedal-held sound after physical/source release is left to the
receiving instrument, just as for ordinary MIDI note release.

ARP HOLD OFF removes latched notes that no longer have a source. Mode/rate/gate
changes use the existing running ARP timing engine; they do not reset the step
clock. Rate/gate updates affect subsequent scheduling and gates; an already
scheduled gate retains its scheduled duration. ARP disable releases its generated
note. Existing bypass and fixed processing order are retained; this work does
not turn the current fixed pipeline into arbitrary chain-order processing.

Modulation CC output is change-driven and respects CC/MOD bypass. Changing its
CC number sends the current modulation value once to the new destination. Leaving
CC64 sends a zero to the old sustain destination first. Other CCs retain their
last received value at the old destination; automatically zeroing arbitrary CCs
would cause unintended instrument changes. Choosing channel-mode or bank/program
related CC numbers deliberately retains standard MIDI semantics; destinations
are not silently remapped or excluded.

## Persistence and migration

Every pre-existing working-memory, bank and runtime offset stays unchanged.
`EXP_TARGETS=7`, `EXP_TOTAL=21`, `WORK_MEM_SIZE`, `PATCH1_BASE`, `PATCH2_BASE` and
legacy expression arrays remain frozen. New assignments/curves are allocated
after the final legacy runtime allocation, with separate extension copies for
bank 1 and bank 2. New runtime caches, queued writes and input counters follow
those copies and are never exported as patch data. Allocation remains below the
JSFX one-million-slot ceiling.

JSON schema **2** has the exact legacy working-memory prefix followed by a
424-value extension: version marker, 21 new assignment IDs, 21 point counts,
three sets of 21×6 curve coordinates/bends and three modulation CC destinations.
`payload_addr()` maps this contiguous wire representation to discontiguous RAM;
it never exports the intervening bank/runtime memory. Internal bank header field
9 now indicates whether the separate extension bank exists. Legacy banks without
that marker get unassigned new targets with linear curves and modulation CC1.

The Lua companion accepts schema 1 and 2, preserves the incoming schema when
saving, and rejects unsupported schemas, invalid lengths and non-finite array
values before modifying shared payload memory. The JSFX imports schema-1 prefixes
without altering their recorded events or old assignments/curves, initializing
only new fields. A schema-2 payload must have the full expected size. Bank caches
and pending changes reset on recall. Both banks save/load their extensions
independently.

Update **both files** and restart the companion ReaScript after upgrading. Old
JSFX/Lua versions reject schema-2 files; forward compatibility is intentionally
not promised. Keep copies of original patch JSON files. Contrary to the older
README's v1.4 historical project-serialization wording, the actual v1.20.1 baseline
has a trivial `@serialize` and uses external JSON; this change does not invent
project-file serialization or recover material absent from baseline project data.

## Automated verification

The native test requires a C++ compiler and a pinned ysfx source/build tree. It
runs the actual complete JSFX, not a Python translation of its parameter formulas.
It uses ysfx's internal VM API solely to drive/assert test state; the plugin has
no ysfx dependency.

```sh
# Use a tool checkout outside the project; existing cloud checkouts are isolated.
git clone https://github.com/jpcima/ysfx.git /workspace/setup-tools/ysfx
git -C /workspace/setup-tools/ysfx checkout 8077347ccf4115567aed81400281dca57acbb0cc
git -C /workspace/setup-tools/ysfx submodule update --init --depth 1
cmake -S /workspace/setup-tools/ysfx -B /workspace/setup-tools/ysfx/build \
  -DYSFX_PLUGIN=OFF -DYSFX_TOOLS=ON -DCMAKE_BUILD_TYPE=Release
cmake --build /workspace/setup-tools/ysfx/build -j 4
YSFX_SOURCE=/workspace/setup-tools/ysfx tests/run_host_tests.sh --historical
python3 -m venv /workspace/setup-tools/venv
/workspace/setup-tools/venv/bin/pip install lupa==2.6
/workspace/setup-tools/venv/bin/python tests/test_patch_io.py
```

Do not recreate a tool checkout if one already exists; use its pinned version.
Do not create a Git worktree unless requested. In this cloud machine, CMake is
available at `/workspace/setup-tools/venv/bin/cmake` (4.4.4). No signature, checksum
or TLS verification was disabled during the build.

The test runner builds in a temporary directory and preserves failure status. It
covers all four controllers on all 42 identities; endpoints, enum boundaries,
continuous resolution, independent curves, interpolation/bends, removal/manual
control, actual popup/selection/curve clicks, scrolling, rendering immutability,
old memory offsets, two banks, schema-1 import/schema-2 round trips and rejection,
held-note transpose/range safety, CC output/destination changes, running ARP/HOLD,
real MIDI recording, overdub and one-shot playback. Historical mode additionally
runs the three broken versions and minimal variable-isolation experiments.

LICE ran headlessly without font support, so framebuffer comparisons establish
stable drawing geometry, not typography. Native REAPER GUI/font rendering, real
MIDI hardware, listening, long-session timing and actual disk JSON integration
inside REAPER remain manual release checks. REAPER's download page was reachable,
but its binary download returned HTTP 403 here; no native REAPER run is claimed.
The Lua tests execute the real shipped daemon against simulated REAPER API calls
and real temporary files. The EEL2 tests separately exercise the actual host-side
shared-memory protocol and migration.
