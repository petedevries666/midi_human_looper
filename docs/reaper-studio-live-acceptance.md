# REAPER ↔ Zynthian musician acceptance

Use the same candidate checkout as [the V4 test](zynthian-v4-first-test.md).
Back up your REAPER project/effect and save the Zynthian snapshot first. This
procedure still requires actual REAPER, Firefox and hardware validation.

1. In REAPER choose **Options → Show REAPER resource path**. Copy the candidate
   `midi_human_looper.jsfx` into Effects and its companion patch Lua into the same
   location as your existing installation. Copy all `reaper/*.lua` together into
   a ReaScripts folder. In Actions load SEND, GET, PUSH and PULL scripts.
2. Create one track with the JSFX. Verify live input and output with a synth.
   Record a two-bar phrase, play it and overdub. Test STOP/PANIC with held notes
   and sustain. Save/reopen the RPP. Main controls must remain compact.
3. In the native Firefox phrase options, EXPORT MIDI from a recorded stopped
   phrase. Open the downloaded `.mid` in REAPER. Compare notes and timing.
   Export a two-bar note-only REAPER take as `.mid`, IMPORT it into a different
   native phrase and play it. Check channels, chord/repeated-note durations and
   velocities. Neither global tempo may change. Malformed/oversized input must
   refuse before replacement. The SMF browser workflow is native; do not assume
   the JSFX provides identical IMPORT/EXPORT controls.
4. Start the Python bridge worker on your REAPER computer using the exact command
   in [the bridge setup](studio-live-bridge.md), pointing to the intended processor
   and private token file. Its spool is the resource path's
   `Data/MIDI_Human_Looper/bridge`. Keep the worker terminal open for transfers.
5. Select the two-bar MIDI take and run SEND. Confirm the correct processor/phrase
   and replacement. STOP the destination first. Play it on Piano. Record or overdub
   a Bass phrase, STOP Bass, select a REAPER destination track, place the edit
   cursor and run GET using Bass's paired endpoint. Inspect the new item against
   the source. Notes-only bridge transfers reject real CC/SysEx, muted notes and
   notes crossing item boundaries; glue looping items first. Sustain is tested
   live, not advertised as a notes-only bridge payload capability.
6. For complete-project testing use one recognized JSFX across all open project
   tabs, stopped REAPER/native transport and no held notes or active morph. PUSH
   a compatible base project. Change native parameters, then try the stale PUSH:
   it must report a conflict without overwriting the live revision. PULL/adopt
   deliberately, save the RPP and PUSH again. Repeat after restarting the native
   processor: a stale engine session must reject activation.
7. Native Controller/Snapshot policies and A/B execution are not implemented in
   REAPER. A populated native extension must refuse incompatible whole-project
   transfer rather than silently erase it. Individual SEND/GET remains useful.
   Test native mappings/snapshot morph separately in Firefox; legacy expression
   mappings are a different ownership path, not proof of full Controller parity.
8. On native STOP, choose COMMIT RESTART STATE and inspect the saved revision.
   Close Firefox and the bridge, disconnect the studio network and continue live
   playback. Restart only the test processor: committed data restores stopped
   unless an explicit Zynthian snapshot overrides it. Start playback and verify
   phrases/routing. Slot SAVE alone does not select autonomous restart authority.
9. Return to the LAN, GET the modified source, and check that REAPER edits did not
   occur without an explicit transfer. Keep the RPP, native data backup, revision
   evidence and test results. Finally PANIC and verify silence on every synth.

No cloud test proves REAPER API behavior, RPP restoration, physical Helix response
or network/power-failure recovery. Mark each step passed/failed/not run on the
actual equipment and retain conflicts/errors rather than bypassing them.
