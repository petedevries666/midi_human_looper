# MIDI Human Looper: release history

v1.22.1:
- OPTIONS close button, outside dismissal and Escape; cancel Learn on close.
- Exclusive Learn target across switches/controllers/phrases, exact channel/type
  capture, silent learning events and deliberate reassignment of conflicts.
- Per-assignment FORGET; separate TEST TAP/DOUBLE/HOLD work for disabled switches.
- SAVE snapshots after queued edits on the DSP thread and updates the internal bank.
- Regression coverage for two-switch isolation, popup lifecycle, TEST and real JSON I/O.

v1.22.0:
- Four independent Smart Switches: exact-channel note/CC learning, silent commands,
  instant/exclusive TAP/DOUBLE/HOLD and manual momentary assignment.
- 64-position phrase-reference lists, forward/back/ping-pong/shuffle traversal,
  independent RESUME/RESTART re-entry and step-position highlighting.
- STOP/RESET/PANIC and stable instrument/type module targets with deferred bypass.
- Compact switch editor, schema-3 appended configuration and schema-1/2 migration.
- Native MIDI/GUI/gesture/persistence regressions; existing ci/eti isolation retained.

Historical notes extracted from the JSFX source on v1.18.9. Most recent versions first.

Free-time MIDI phrase instrument prototype for REAPER JSFX.
v1.18.8: ONCE/HOLD overdub uses independent one-shot timing, never LOOP wrap.
v1.18.7: exclusive REC/OVERDUB arm, neutral recorded phrase dots, safe switch.
v1.18.6 CRITICAL: eliminate destructive overdub wrap path and guard existing phrases.
v1.18.5:
- default phrase mode ONCE; textual ONCE/LOOP/HOLD mode selector
- shorten phrase label field; stopped ONCE/HOLD overdub rewinds and waits for note/trigger
v1.18.4:
- minimalist phrase rows: full-width name, borderless controls, empty phrase suppression
- numbered button combines REC and non-destructive OVERDUB; context menu for CLEAR
- fix name character spacing with sequential gfx drawing
- redraw LOOP icon as a proper circular arrow
v1.18.3:
- native drawn phrase icons and single cycling play-mode button
v1.18.2:
- replace invalid if() function syntax with EEL2 ternary conditional in MIDI trigger handling
v1.18.1:
- define record-finish helpers after infer_tempo to satisfy EEL2 function resolution
v1.18.0:
- compact icon-based phrase controls, armed numbered dot, three direct play modes
- per-phrase MIDI note learn with persistent trigger mapping
- click armed phrase to finish recording; click another to finish and immediately arm it
- learned trigger notes are consumed and do not enter the recording
v1.17.7:
- extend scrollable content height after the top-layout reflow
- reserve enough bottom canvas for the full expression curve editor and preset strip
- scrollbar can now reach the complete curve editor again
v1.17.6:
- properly reflow the whole top area instead of moving isolated labels
- transport row y=68, patch/file row y=108, PHRASES browser starts y=154, phrase rows y=186
- instrument section derives from the new phrase-row base so everything below follows cleanly
v1.17.5:
- title header is now acid yellow
- move transport state (IDLE/READY/RECORDING/LOOPING) out of the header onto the transport row
- push patch row and PHRASES browser down to eliminate top-section overlaps
- fix CLEAR ALL hit box to match its compact 92px button
v1.17.4:
- add hard square header: MIDI BAD MOTHERFUCKER V.1.18.8 / ANONYMALZ LIVE ENGINE
- compact READY / ABORT / CLEAR ALL to the same 92x30 format as OPTIONS
- move transport / patch rows below the new header
v1.17.3:
- hide REAPER's native parameter sliders: the plugin is now driven from its custom UI
- keep legacy/internal slider variables available to the engine without exposing the old control strip
- quantize remains internal/dormant until its dedicated UI is designed
v1.17.2:
- remove duplicate EXP A/B TEST faders from the GUI
- the four named CONTROLLERS meters are directly draggable for mouse testing
- dragging EXP 1/2 CODIE or EXP 1/2 PIERRE directly changes that controller source value
v1.17.1:
- restore the two draggable EXP TEST sliders as manual controller-source simulators
- EXP A TEST drives EXP 1 CODIE, EXP B TEST drives EXP 2 CODIE for mouse-only testing
- harden GUI transient-state initialization so controller/OPTIONS popups cannot flash on plugin launch
v1.17.0:
- add OPTIONS > CONTROLLERS with four named pedal sources and MIDI CC LEARN
- EXP 1 CODIE / EXP 2 CODIE / EXP 1 PIERRE / EXP 2 PIERRE each learn the next incoming CC
- right-click assignable sliders now opens NONE + named controller list
- curve badges/editor follow the selected named controller
v1.16.8:
- restore EXP1 / EXP2 assignment on the base instrument VOLUME slider
- volume keeps its direct slider behavior when unassigned
- right-click cycles NONE / EXP1 / EXP2 and assigned volume reuses the existing curve editor + mini curve overlay
v1.16.7:
- separate the instrument header and transformer lane vertically
- lower header controls slightly and lower transformer lane enough to clear all labels/controls
- modestly increase card height while keeping the compact layout
v1.16.6:
- give transformer blocks a little more vertical breathing room inside each instrument card
- slightly increase card height / row spacing without returning to the oversized layout
v1.16.5:
- modalize transformer chooser hit-testing: while a chooser is open, controls behind it cannot receive clicks
- ADD TRANSFORMER buttons on other instruments are visually drawn but input-blocked until the menu closes
- fixes menu choices accidentally triggering the ADD button of the instrument underneath
v1.16.4:
- give instrument header controls a dedicated internal label margin
- labels now sit above MIDI IN / MIDI OUT / VOLUME instead of overlapping their controls
- align ON/name with the labeled routing controls
- raise transformer signal line and reduce each instrument card height / row spacing
v1.16.3:
- transformer chooser is now rendered at the very end of @gfx for true top-most visual stacking
- move MIDI IN / MIDI OUT / VOLUME labels fully inside instrument cards
- add a small X in every transformer block to remove it from the chain
- NOTE RANGE note values are now editable: left click +1 semitone, right click -1
- NOTE RANGE mode remains separately clickable without stealing clicks from its note controls
v1.16.2:
- draw ADD TRANSFORMER chooser in a final overlay pass so it always stays above following instruments
- keep chooser hit-testing in that overlay pass as well
- tighten instrument cards and vertical spacing
- keep transformer blocks and labels inside the instrument card bounds
v1.16.1:
- restore the rich controls inside modular VELOCITY and CC/MOD transformers
- VELOCITY is a real slider again with EXP1/EXP2 assignment and miniature curve overlay
- CC/MOD exposes the modulation slider with EXP1/EXP2 assignment and miniature curve overlay
- clicking an EXP-assigned transformer slider reopens the existing full curve editor
- right-click on VELOCITY or MOD cycles NONE / EXP1 / EXP2 exactly like the pre-transformer UI
v1.16.0:
- instruments now start visually clean with no transformer blocks
- add per-instrument ADD TRANSFORMER button and compact chooser
- chosen transformers are appended to the visible Helix-style signal chain
- transformer presence/order is persisted separately from each transformer's settings
- existing DSP behavior is preserved for now; this release establishes the modular UI/data model
v1.15.0:
- first TRANSFORMER-chain UI: stripped-back Helix-style instrument base + connected processing blocks
- instrument base is now NAME / ON / MIDI IN / MIDI OUT / VOLUME
- add real per-instrument TRANSPOSE transformer (-48..+48 semitones)
- existing RANGE / POLYPHONY / VELOCITY / ARP / CC-MOD features are presented as transformer blocks
- signal wire visually connects the transformer blocks; inactive/default blocks remain deliberately quiet
- transpose is applied before RANGE and POLYPHONY in this first modular-engine step
v1.14.0:
- add per-instrument note RANGE filter: FULL / DOWN / UP / BOTH
- DOWN sets the lowest accepted note; UP sets the highest accepted note
- BOTH creates a bounded keyboard zone; limits display as musical note names
- range filtering happens before POLY/BASS/LAST/LEGATO and before the post-ARP
v1.13.0:
- add per-instrument NOTE MODE: POLY / BASS / LAST / LEGATO
- BASS always outputs the lowest currently held source note
- LAST uses last-note priority; LEGATO uses last-note priority with note-on-before-note-off transitions
- mono filtering happens before the existing post-ARP, so extracted bass/lead notes can still be arpeggiated
v1.12.0:
- phrase modes are now LOOP / ONCE / HOLD
- HOLD preserves the recorded attack/strum timing but suppresses recorded Note Offs
- HOLD remains sounding after phrase end; its button becomes STOP while held
- triggering another ONCE/HOLD phrase chokes the previous held phrase cleanly
v1.11.2:
- LOOP control always reads TRIG; remove confusing STOP label/state
- empty phrases keep TRIG visible but dimmed to communicate unavailable action
v1.11.1:
- tighten phrase OVERDUB / CLEAR / LOOP / TRIG-STOP buttons around their labels
- shorten phrase VELOCITY and DECAY sliders; DECAY remains shorter than VELOCITY
- give DECAY the same 18px height as VELOCITY for a balanced row
v1.11.0:
- wide unified UI grid for PHRASES / INSTRUMENTS
- persistent editable phrase and instrument names with automatic default fallback
- LOOP phrases get TRIG/STOP gating; OVERDUB/CLEAR/EVENTS labels are explicit
- instrument ARP moved to the right; details hidden while ARP is OFF
- centered IN/OUT text via measured text helper
v1.10.1:
- move curve preset palette to the right of the graph
- clearer editor identity block: instrument, parameter, MAPPED TO, expression pedal
v1.10.0:
- curve editor preset palette: FLAT 50, STEP UP, STEP DOWN, RISE, FALL
- four persistent custom curve preset slots
- SAVE CUSTOM arms a slot; click C1..C4 to store, normal click loads
- preset thumbnails show the actual curve shape
v1.9.0:
- curve endpoints are permanent and locked to X=0 / X=1; they can only move vertically
- Shift-drag a curve segment moves both endpoint nodes together; interior segments move X+Y, edge segments Y only
- Alt-drag a curve segment bends it; curvature is persistent and used by the engine and mini curve previews
v1.8.5:
- EXP badge overlay is less opaque so the underlying slider remains visually present
- miniature curve now spans the full slider width; EXP1/EXP2 label overlays it
v1.8.4:
- unified EXP assignment display inside every assignable slider/control
- assigned controls show EXP1/EXP2 plus a tiny preview of their own multipoint curve
v1.8.3:
- repair accidental token corruption in v1.8.2 curve editor isolation
- dedicated curve_ti / curve_gi / curve_kind globals keep GUI indexes separate from @block
v1.8.2:
- fix frantic curve-editor switching caused by shared EEL2 globals between @block and @gfx
- editor now uses dedicated gfx-only target/instrument/kind variables, never the runtime et/eti indexes
v1.8.1:
- stabilize curve-editor target selection: assigned controls select only on fresh left-click
- prevents held mouse state from repeatedly rewriting the active target while @gfx redraws
v1.8.0:
- generic per-parameter EXP curve engine for instrument controls
- assignable targets: VELOCITY, VOLUME, MODULATION, ARP ON/OFF, ARP MODE, RATE, GATE
- every target/instrument pair owns its own independent multipoint curve
- boolean ARP ON threshold: curve value >= 64 = ON
- enum ARP MODE maps 0..127 across RANDOM / UP / DOWN
- ARP MODE is now separate from ARP ON/OFF; UP and DOWN playback implemented
v1.7.7:
- UI cleanup: IN / OUT / CC boxes display only their actual numeric value
- remove duplicated tiny channel/CC values beside boxes
- unify instrument-panel typography; mockup hierarchy kept without oversized numerals
v1.7.6:
- redesign INSTRUMENTS section after Pierre's mockup
- yellow column headers and yellow ARP labels / active mode labels
- clearer IN / OUT numeric boxes, VELOCITY, CC, VOLUME and MODULATION columns
- compact ARP second line with OFF/RANDOM, RELEASE/HOLD, RATE and GATE
v1.7.5:
- curve editor follows the selected LEVEL assignment, not merely the last right-click
- each instrument LEVEL keeps its own independent EXP curve even when several use the same EXP source
- left-click an assigned LEVEL to select/highlight it and display its own curve
- selected LEVEL gets a visible outline; right-click assignment also selects that LEVEL
v1.7.4:
- EXP GUI movement now feeds the exact same proven LEVEL dirty-CC path as the manual LEVEL slider
- curve evaluation happens immediately when EXP1/EXP2 is dragged, updating assigned LEVEL values visibly
- @block remains the MIDI sender, exactly like manual LEVEL edits
v1.7.3:
- fix EXP curve engine runtime memory overlap
- EXP last-value cache now lives after the full ARP source-count table
- EXP1/EXP2 curves can now actually drive LEVEL and emit its selected CC
v1.7.2:
- fix vertical scrolling: render UI to an offscreen buffer and blit the scrolled viewport
- mouse hit-testing remains in content coordinates; scrollbar stays fixed on screen
v1.7.1:
- vertical GUI scrolling for small REAPER FX windows
- mouse wheel scrolls the whole interface; right-side scrollbar can also be dragged
v1.7.0:
- first multipoint expression mapper, inspired by MIDI Curver / Helix controller assignment
- right-click an instrument LEVEL slider to assign/open EXP1 or EXP2 curve editor
- curve: left-click empty space adds a point, drag a point moves it, right-click removes it
- up to 6 points, linear interpolation; curve drives the instrument LEVEL CC in real time
v1.6.2:
- fix stuck POST-ARP after repeated/overlapping ONE SHOT triggers
- ARP source pools are now flushed when ONE SHOT voices are choked/recycled
- when the last ONE SHOT voice ends, non-HOLD arps release any orphaned source notes
v1.6.1:
- POST ARP now has explicit MODE ON/OFF and HOLD ON/OFF per instrument
- HOLD OFF follows source Note Offs and stops when no source notes remain
- HOLD ON latches the current note pool; switching HOLD off clears the latch safely
v1.6.0:
- first POST instrument arpeggiator prototype: RANDOM mode only
- independent ARP ON/OFF, RATE (x BPM) and GATE per instrument
- arp sits after phrase routing/velocity and before the destination synth
- non-note MIDI (CC, sustain, etc.) remains transparent
v1.5.2:
- LEVEL CC selector: left click +1, right click -1, Shift+left resets to CC0
- new/default LEVEL CC is CC11; existing loaded JSON keeps its saved CC
v1.5.1:
- LEVEL MIDI CC is configurable per instrument, default CC39 for Arturia test
- LEVEL CC number is stored in external JSON patch memory
- click each row's CC button to cycle 0..127
v1.5.0:
- external JSON patch persistence via companion Lua ReaScript + named gmem bridge
- PATCH 1/2 select external slots; SAVE writes patch1/patch2.json; LOAD FILE reloads selected slot
- @serialize no longer stores patch banks in the .RPP
- JSON contains complete working memory plus global loop/transport parameters
v1.4.21:
- RESTORE click now only queues a request; actual bank restore runs safely in @block
- state label moved away from RESTORE button
- visible RESTORE REQUESTED feedback confirms the click
v1.4.20:
- temporary RESTORE button force-loads the selected serialized patch bank
- useful for update/recall diagnostics; does not autosave or change patch layout
v1.4.19:
- LEVEL test now sends MIDI CC7 (Channel Volume); MOD remains CC1
- GUI sliders only set dirty flags; actual MIDI CC transmission happens safely in @block
- ORIGINAL output follows a fixed instrument IN channel when available
- patch memory layout unchanged, preserving v1.4.18 recall compatibility
v1.4.18:
- critical Cockos serialization fix: @init no longer clears serialized patch_valid/current_patch
- handles BOTH host orders: @serialize->@init and @init->@serialize
- if @init follows a load, saved bank is rehydrated again at end of @init
v1.4.17:
- recall v2: detect @serialize READ with file_avail(0)>=0 and hydrate immediately
- avoids fragile restore_pending flag across REAPER's @serialize/@init ordering
- serialized byte layout remains unchanged for existing .RPP state
v1.4.16:
- recall fix: restore the serialized current patch bank into working memory once at @block startup
- bypasses load_patch() same-slot guard and does not autosave during recall
- serialized patch layout remains unchanged for existing .RPP compatibility
v1.4.15:
- diagnostic hard rename clear_all -> reset_all_phrases everywhere
- if REAPER still reports "clear_all undefined", it is provably compiling stale source
v1.4.14:
- remove obsolete transport/CLEAR execution from @slider
- custom GUI remains the transport controller; engine work stays in @block/@gfx
- compile baseline only; persistence unchanged
v1.4.13:
- JSFX scope fix per Cockos docs: shared functions live in @init
- @init functions are visible from @slider/@block/@gfx
- compile baseline only; persistence logic unchanged
v1.4.12:
- move ALL function declarations out of @init and before every executable section
- fixes REAPER section visibility: @slider/@block/@gfx can resolve reset_all_phrases(), clear_layer(), etc.
- no persistence redesign in this build
v1.4.11:
- rollback to exact known-good v1.4.4 codebase after persistence experiments broke compilation
- no persistence changes in this build; compile/runtime baseline only
v1.4.4:
- instrument controls now affect ONE SHOT playback too (previously that engine bypassed the router)
- route-aware note/sustain reference counting uses the final routed MIDI channel
- LEVEL and MOD sliders now transmit CC11/CC1 immediately while dragged
v1.4.3:
- REAL fix for instrument rows: JSFX user functions share undeclared variables with caller
- hit()/smallbtn() were clobbering GUI loop variables through x/y/w/h/label/active
- all GUI helper parameters are now explicitly local aliases before drawing/hit testing
v1.4.2:
- start with 3 INSTRUMENT slots instead of 8; future versions may add dynamic slots
- fix JSFX function-local scope in smallbtn/button: GUI row index no longer gets clobbered by drawing helpers
- each instrument row now edits its own independent memory slot
v1.4.1:
- compact phrase UI: 6 phrase rows visible at once
- 3 phrase pages: P1-6 / P7-12 / P13-16
- PAGE PREV/NEXT controls keep instruments + expressions reachable on normal screens
- phrase rows reduced from 48px to 38px
v1.4.0:
- 16 PHRASES in line-based UI (no grid)
- two mouse-testable expression sources EXP A / EXP B
- 8 INSTRUMENT routing rows: MIDI IN -> MIDI OUT, velocity multiplier, level CC, mod-wheel CC
- instrument routing duplicates/remaps phrase MIDI non-destructively; ORIGINAL global output still available
- quantize grid slider range fixed to expose all six divisions
- persistence layout remains explicit and documented while external-file patch I/O is designed
IMPORTANT: JSFX @serialize persists with REAPER project/preset state; arbitrary writable named patch files
are not exposed safely by stock JSFX, so v1.4 does NOT fake external SAVE/LOAD.
v1.3.3:
- cross-layer choke now releases only notes actually owned by active ONE SHOT voices
- no more 2048-note panic burst when switching phrase layers
- sustain-off is sent only on channels whose ONE SHOT group currently owns sustain
v1.3.2:
- overlapping same-layer ONE SHOT voices now use MIDI note reference counting
- an older voice Note Off cannot kill a note still held by a newer retrigger
- sustain pedal OFF is also reference-counted across overlapping voices
v1.3.1:
- fix ONE SHOT poly voice memory: JSFX memory is limited to ~1M slots and patch banks already occupy the high range
- voice pool now lives directly after patch banks instead of hardcoded address 700000
v1.3:
- same-layer ONE SHOT retriggers now overlap polyphonically instead of restarting/cutting
- switching to a different ONE SHOT layer soft-kills all voices from the previous phrase group
- velocity decay is applied per successive overlapping voice
v1.2.3:
- fix rapid ONE SHOT retrigger race: soft-kill is now sent immediately from the audio block
- GUI only queues trigger requests; MIDI Note Off / CC64 cleanup happens before the new phrase attack
v1.2.2:
- ONE SHOT layers are monophonic as a phrase group: triggering another ONCE soft-kills the previous one
- previous phrase receives graceful Note Offs + sustain-off, then the new phrase starts
v1.2.1:
- ONE SHOT retrigger now releases notes/sustain from the previous trigger before restarting
- ONE SHOT natural end also releases notes/sustain to prevent hanging notes
v1.2:
- per-layer retrigger velocity decay for ONE SHOT phrases
- consecutive TRIGs of the same layer progressively reduce Note On velocity
- triggering another layer resets the chain; returning starts at full velocity
- DECAY mini control per layer: 100% = no decay
v1.1:
- click L1/L2/L3/L4 to ARM that layer for fresh phrase recording
- armed layer is highlighted red and main transport returns to READY
- each layer now stores its own phrase length for independent ONE SHOT recording/playback
- recording another layer no longer destroys the other stored phrases
v1.0:
- per-layer playback mode: LOOP or ONCE
- per-layer TRIG button launches ONCE phrases independently
- ONE SHOT playback preserves captured expressive MIDI timing and full MIDI stream
- layer mode is part of patch memory automatically
v0.9.4:
- fix the actual GUI transport path: stored loop PLAY no longer clears/re-arms
- both GUI and hidden slider transport now obey the same non-destructive state machine
v0.9.3:
- stored-loop transport is now non-destructive: PLAY/STOP can never re-arm recording
- recording becomes available again only after CLEAR ALL (or an empty patch)
v0.9.2:
- READY becomes PLAY when a stored loop exists; PLAY restarts it without clearing
- SAVE gives visible confirmation for the selected patch
v0.9.1:
- patch buttons always switch slots; empty slots start as clean editable patches
- switching patches auto-saves current slot in RAM before loading the other slot
v0.9:
- two complete patch slots with LOAD + SAVE
- patch stores all four MIDI layers, loop timing, mute/solo/velocity and global playback parameters
- patch banks serialize with the REAPER project/preset, no external JSON required
v0.8.5:
- fix playback event count still reading gui_layer instead of current audio layer
- restore complete master-loop playback
v0.8.4:
- repair accidental v0.8.3 global replacement inside audio-engine functions
- GUI uses gui_layer only; audio engine uses layer only
v0.8.3:
- isolate GUI row index from @block playback globals to stop layer labels flickering
v0.8.2:
- fix GUI layer loop: layer index was never incremented, so all four rows were actually layer 1
- prevents OVR/CLR/mute/solo rows from all targeting layer 1
v0.8.1:
- fix JSFX function-variable scope corrupting the GUI layer index / wrong layer operations
- stabilize layer addressing before further overdub work
v0.8:
- 4 independent MIDI layers
- overdub records into the selected layer over exactly one loop cycle
- per-layer mute / solo / velocity trim
- quantize grid + amount (0..100%) applied non-destructively at playback
- full MIDI stream recorded: notes, sustain CC64, other CCs, pitch bend, aftertouch
- live MIDI thru remains active while looping

First loop:
READY -> first Note On starts free-time recording -> PLAY closes the master loop.
Overdub:
while PLAYING, arm OVR on a layer -> recording starts at next loop boundary,
records exactly one full loop into that layer, then returns to PLAY automatically.

## v1.18.9
- Shorter phrase name fields, restored per-phrase velocity and decay sliders for non-empty phrases.
- Dimmer empty rows and a thin enclosing border around the six phrase rows.
- Release history moved out of the JSFX source into this file.

## v1.21.0
- Isolate audio/GUI expression target and controller counters; historical concurrent rendering reproducer and cause-isolation tests.
- Stable per-instrument identities, assignments and independent multipoint curves for every transformer parameter; ARP HOLD is distinct from enable.
- Consume modal popup input, capture manual drags, open curves below the shared editor, and keep redraws out of persistent data.
- Queue GUI value changes to the audio block, defer note-transform changes through held source notes, and send modulation to its actual selected CC destination without flooding.
- Preserve every legacy memory/bank offset; import schema-1 JSON and save schema-2 appended expression data with independent bank extensions. Update the companion Lua ReaScript too.
- Add native WDL EEL2/LICE GUI/MIDI tests, Lua patch-bridge tests and a detailed regression/persistence audit in docs/expression-assignments.md.

## v1.21.1
- Open the assigned parameter's curve immediately after controller selection; NONE closes only that parameter's curve. Reset transient drag capture without passing popup clicks through.
- Match Transformer Editor rails to VOLUME's 18px height, with 34px row spacing and enlarged panel/hitboxes.
- Restore live inline multipoint and bend previews with GUI-local sampling; retain the v1.21.0 counter isolation and leave MIDI processing/schema unchanged.
- Add actual framebuffer, popup and geometry regressions, including independent previews across rows/instruments and concurrent MIDI rendering.
