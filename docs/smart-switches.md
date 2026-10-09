# Smart Switches and Phrase Conductor (v1.22.1)

Four independent switches conduct the existing phrase pool. Each holds up to 64
references, not copies of phrase data. No new recorder, overdub mechanism,
Conductor Looper or staircase editor is introduced.

## Configure a switch

Scroll below the expression editor to SMART SWITCHES / PHRASE CONDUCTOR.

1. Select SWITCH 1–4, click its name field and type a name (16 characters).
   Enter or Escape ends name editing. Choose PHRASE or SPECIAL.
2. Click MIDI LEARN, then press a momentary Helix switch. Learning captures the
   exact channel, note/CC number and message type. Learning itself is silent and
   does not execute an action. Click LISTENING again to cancel. Learn is exclusive across Smart Switches,
   expression controllers and phrase triggers; starting another target cancels the
   previous listener. An input owned elsewhere opens a REASSIGN / CANCEL warning.
   REASSIGN removes only conflicting MIDI mappings, preserving their musical settings.
3. Alternatively cycle INPUT through UNASSIGNED / NOTE / CC, adjust NUMBER and
   CHANNEL, then enable the switch. MIDI THRU defaults OFF: command press and
   release never reach instruments or the existing recorder. With THRU ON,
   command messages pass through instrument routing but still bypass recording.
4. For CC, set the exact PRESS and RELEASE values transmitted by your hardware.
   Learn captures the first CC value; release defaults to 0, or 127 for a learned
   zero press. Other release values require manual adjustment. Equal press and
   release values are rejected. Intermediate values do not execute actions.
5. Choose actions independently for TAP, DOUBLE and HOLD, then choose targets
   where applicable. TEST executes that configured action without MIDI input;
   it tests action routing, not physical gesture timing. TEST TAP / TEST DOUBLE /
   TEST HOLD use the hardware action dispatcher and work when a switch is disabled
   or unassigned; they do not enable it or modify its MIDI assignment.

FORGET MIDI removes only the selected switch's assignment. Its name, sequence,
actions, timings and traversal settings remain intact. In OPTIONS, each expression
controller has its own FORGET button and displays the learned channel, message type
and number. Close OPTIONS with ×, an outside click or Escape; closing cancels Learn
and preserves previous assignments. The closing click never activates an underlying
control. Older expression CC assignments retain their legacy ANY-channel behavior
until relearned, when they receive an exact channel/type identity.

Note On with any positive velocity is a press. Note Off or Note On velocity 0 is
a release. Repeated press messages while down do not execute another action.
Learn conflicts leave all assignments unchanged until explicitly confirmed.
Manual duplicate switch assignments remain rejected without replacing the existing owner. A missing release unlocks gesture detection after 10 seconds
and displays a warning; use a controller that supplies a reliable release.

## Phrase sequences

Click pool buttons to append references, including repeated and nonconsecutive
phrases. For example, `1, 2, 1, 3, 4, 5, 1, 7` is eight distinct positions.
Empty pool entries remain selectable; attempting to play an unavailable/deleted
reference advances the cursor, reports the problem and emits no phrase.

The editor displays 16 positions per page. Click a step to select it (`*`), then
MOVE left/right, REMOVE, CLEAR or UNDO. Undo stores one previous list edit;
pressing it again swaps back. List edits reset that switch's traversal cursor.
Only the last triggered position is lit, even when multiple positions reference
the same phrase. The highlight records the trigger, not whether a voice is still
sounding. The next tap follows the selected traversal mode.

| Mode | Traversal |
| --- | --- |
| FORWARD | First position to last, then wrap |
| BACKWARD | Last position to first, then wrap |
| PING-PONG | Forward/backward without repeated reversal endpoints |
| SHUFFLE BAG | Every position once per bag; duplicates retain their weight |

At shuffle bag boundaries the next phrase differs from the previous phrase when
an alternative exists. Consecutive duplicate phrase IDs *inside* a bag are allowed;
the no-repeat guarantee concerns positions, not deduplication of user weighting.
A single-position list is safe in every mode.

Each switch keeps an independent cursor, direction and bag. RESUME continues its
saved traversal after another Phrase Switch becomes active. RESTART begins at
position 1 on re-entry, including backward and shuffle modes; subsequent steps
follow the selected traversal. Repeated taps on the active switch do not restart
it. Special actions do not change the most recently active Phrase Switch.

NEXT PHRASE uses the existing ONCE/HOLD voice and choke behavior, or enables the
existing LOOP phrase on its shared transport. Existing mute/solo, decay,
transformers, routing and overdub orchestration still apply. LOOP needs an existing
nonzero loop duration. Smart Switches do not arm recording or copy phrase data.

## Gestures and latency

Default double window: **300 ms** after the first release. Default hold threshold:
**800 ms** from press. Controls support 50–2,000 ms double and 100–5,000 ms hold.

- **INSTANT:** TAP executes on each press. A recognized DOUBLE or HOLD may also
  execute its action. A double therefore consists of two immediate TAP actions
  plus its DOUBLE action.
- **EXCLUSIVE:** with DOUBLE enabled, a single tap waits for the double window.
  A second press within that window produces DOUBLE on its release. With only
  HOLD enabled, a short TAP executes on release. With both optional gestures
  disabled, TAP executes immediately on press.

HOLD executes once at its threshold and suppresses pending TAP/DOUBLE recognition
for that press. Timer dispatch is bounded by the host audio block. Changing gesture
settings cancels in-flight gesture actions. Releases from an input held across a
preset remap are consumed silently until released.

## Special actions and targets

| Action | Effect / target |
| --- | --- |
| NONE | Disabled gesture |
| NEXT PHRASE | Advance this Phrase Switch; unavailable for Special Switches |
| STOP PHRASES | Stop all existing phrase playback; preserve live input |
| RESET SWITCH | Reset the chosen switch cursor, or all switches |
| RESET ALL | Reset all switch cursors; keep playback running |
| STOP + RESET | STOP PHRASES plus reset chosen switch/all |
| PANIC ALL | Explicit global all-notes-off and stop phrase playback |
| TOGGLE / ENABLE / DISABLE MODULE | Chosen instrument and transformer type |

STOP releases playback-owned notes, mono sources, ARP sources/latches and sustain;
it preserves tracked live notes and live sustain on the same output channel/pitch.
RESET affects traversal only. Module targets are instrument + transformer type,
so chain reordering does not change their meaning. A target absent from the chain
reports an error; it does not insert a module. Changes wait until that instrument's
source notes release, preserving matching transformed note-offs. ARP disable
releases its generated note. This build has one module of each type per instrument;
future duplicate-type modules would require a stronger instance identity.

MIDI receivers share channel/pitch and CC state: notes from independent devices
routed to the same channel cannot be physically separated after transmission.
Use separate channels for independently sustained voices. Existing phrase-change
choke behavior is retained; STOP's live ownership protection does not replace the
older phrase engine's choke rules.

## Patch compatibility

Update **both** JSFX and `midi_human_looper_patch_io.lua`; restart the Lua daemon.
New external JSON patches use schema 3. Schema 1 and 2 remain readable and initialize
switches disabled/unassigned with empty lists. Existing phrase, bank and expression
RAM offsets are unchanged. The schema-2 expression marker remains 2; schema 3 adds
513 values after the old wire payload:

- One extension marker (3).
- Four 128-value switch configurations: fields 0–19, 16 name characters at 32,
  and 64 phrase references at 48. Fields 24/25 now store the corresponding expression
  controller's channel (0 legacy ANY, 1–16 exact) and type (0 legacy CC, 1 note,
  2 CC). Fields 27–30 store four phrase-trigger channels per record. These formerly
  reserved values keep the schema-3 payload length unchanged.

The plugin SAVE button takes its snapshot on the DSP thread after pending switch
edits are applied, then sends the complete schema-3 payload to the Lua daemon and
updates the internal bank. Wait for the file I/O SAVED indication before closing
REAPER. If the UI says UPDATE PATCH I/O SCRIPT, install and restart the shipped Lua
daemon. SAVE requires the FX to be processing MIDI/audio and the daemon to be running.

Both internal patch banks preserve switch configuration. Cursors, bags, gesture
state, learn mode, pending module actions and undo state are runtime-only and reset
on load. The existing preset-load panic behavior remains unchanged. Save/reopen
uses the existing external JSON daemon, not newly added project serialization.
Loaded switch fields are bounded and duplicate enabled inputs disabled safely.

## Automated validation

Run the existing native EEL2/LICE host harness and Lua daemon suite:

```sh
YSFX_SOURCE=/workspace/setup-tools/ysfx tests/run_host_tests.sh
/workspace/setup-tools/venv/bin/python tests/test_patch_io.py
```

`tests/smart_switch_cases.hpp` exercises actual MIDI consumption and phrase output,
exclusive/instant timing, CC learning, repeated/missing releases, all traversal
modes, duplicate weighting and highlight pixels, independent re-entry, list editing,
module targeting/deferred changes, targeted STOP, preset migration and GUI popup
isolation. Existing transformation, expression, recording/overdub, bank and
concurrent GUI/audio tests continue to run. No live REAPER/Helix test is claimed by
the headless host suite. `tests/learn_ui_cases.hpp` additionally exercises two-switch
Learn isolation, conflict cancellation/reassignment, OPTIONS lifecycle, FORGET,
all TEST actions and the actual GUI SAVE snapshot. To test that snapshot through
real Lua JSON file I/O:

```sh
NATIVE_PATCH_FIXTURE=/tmp/switch-save.json YSFX_SOURCE=/workspace/setup-tools/ysfx tests/run_host_tests.sh
NATIVE_PATCH_FIXTURE=/tmp/switch-save.json /workspace/setup-tools/venv/bin/python tests/test_patch_io.py
```

## Live acceptance checklist

In REAPER with the updated Lua daemon:

1. Record phrases P1–P7 using the existing recorder. Build the example eight-step
   sequence and learn a Helix momentary note. Verify one advance per normal tap,
   no command note through to instruments and only one duplicate position lit.
2. Test both policies with DOUBLE=RESET and HOLD=STOP. Verify timing, no extra
   delayed TAP in EXCLUSIVE, and no DOUBLE after a held press.
3. Build VERSE and CHORUS on separate switches. Check independent positions,
   RESUME/RESTART and each traversal mode, including multiple shuffle bags.
4. Hold a live keyboard note/sustain while phrases play. Test STOP, RESET and
   PANIC separately. Test module targets after reordering the transformer chain.
5. Save both patches, switch banks and reopen their JSON files. Verify names,
   input mappings, actions, lists and policies restore, with cursors reset.
6. Load old schema-1/2 patches, test unavailable phrases and duplicate learning,
   and change presets while a controller is held. Check releases remain silent
   and the confirmed expression-editor flashing fix stays intact during MIDI.

## PHRASES trigger Learn (v1.22.2)

The keyboard Learn icon immediately before M/S on each PHRASES row assigns an
exact-channel MIDI note to PLAY that phrase. The learning press/release is silent;
subsequent presses trigger ONCE/HOLD immediately or enable LOOP playback. Trigger
releases are consumed and neither edge is recorded. An empty phrase does nothing.
This control never arms recording/overdub. ONCE/HOLD playback also leaves an
already armed overdub waiting for its separate recording input.
Use the existing numbered phrase recording control to arm RECORD/OVERDUB separately.
Assignments remain phrase-specific and persist through the existing patch payload.
Smart Switch sequencing and re-entry are unchanged.
