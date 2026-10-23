# MBMF V2 DICKINSON - release candidate

This candidate combines the native M5 lineage through PR #103 with the later
recall, Zynthian SOLO, Smart Switch panel and mapped-slider fixes from PR #107.
The REAPER JSFX remains frozen. ECHOCITY stays at the existing Harris 1.0
feature set; Freeze/Reverse and subsequent effect proposals are outside this RC.
The exact source revision on the musician's Pi has not been read from this
workspace, so audible equivalence requires a hardware acceptance pass.

## Controlled installation

**Do not run these commands until the musician explicitly authorizes installation.**
Use the final reviewed 40-character commit SHA, never a moving branch name.
The checkout containing the script must be this RC and its working tree must be
clean. On the Zynthian, with playback/recording stopped and notes released:

```sh
cd /root/midi_human_looper
git fetch https://github.com/petedevries666/midi_human_looper.git <RC_SHA>
git rev-parse FETCH_HEAD   # must equal <RC_SHA>
git show <RC_SHA>:scripts/v2-dickinson-rc.py > /tmp/v2-dickinson-rc.py
python3 /tmp/v2-dickinson-rc.py preflight
python3 /tmp/v2-dickinson-rc.py install --revision <RC_SHA>
```

The script checks the Pi architecture, installed MBMF config, checkout,
binary, rollback-capable updater, snapshot tree, Zynthian service and disk
headroom before installation. `preflight` is read-only. `install` first makes
a private source/config/snapshot archive with a SHA-256 manifest; it then
calls the existing transactional updater with its mandatory `--backup` flag.
That updater copies processor data, patches, config and token, validates the
candidate in isolated processes, checkpoints stopped projects, activates the
new runtime and verifies restored fingerprints. An activation failure triggers
its existing rollback. A failed preflight or backup never stops Zynthian.

The backup is under
`/zynthian/zynthian-my-data/midi-human-looper/backups/v2-dickinson/`.
The update journal and previous release are retained by the existing updater.
No patch slot, chain, routing edge or Zynthian snapshot is rewritten by this
RC preparation procedure. Source/snapshot archives and updater backups can
contain private musical data and tokens; keep them on the Pi.

## Rollback

If the candidate starts but fails musical acceptance, stop playback and run:

```sh
python3 /tmp/v2-dickinson-rc.py rollback
```

The existing updater restores the previous runtime config and validates the
processor fingerprints. It also backs up the current processor state before
rolling back. The Zynthian snapshot archive remains available separately;
do not overwrite newer snapshots automatically. If automatic rollback reports
that it needs recovery, leave the Pi as-is and inspect
`runtime-update.json`, the `before.tar.gz` archive and its manifest before
touching live services. The installer deliberately does not attempt to
reconfigure JACK or Zynthian chains.

## Musical acceptance on the Pi

1. Confirm the expected Zynthian chains and Surge/padthv1/Sfizz presets are
   present; inspect MBMF instrument links and MIDI outputs before playing.
2. Load FEAR & LOATHING and ROAD without changing their saved data. Confirm
   patch/snapshot selection, then send the same Program Change twice and
   verify the second call does not interrupt the running patch.
3. Play a phrase in ONCE, LOOP and HOLD; test layered output, STOP and PANIC,
   then release the switch and confirm no stuck notes.
4. Test Smart Switch TAP, HOLD, LONG HOLD and RELEASE through the real pedal;
   double tap is reserved for Smart Switch actions, not Conductor advancement.
5. Test a five-step Conductor with group 0 and a HOLD first step; verify one
   step admission per press and no blocked wrap.
6. Try ARP DOWN, STEP MAX/ONCE and random climb modes; verify selected modes
   survive saving and loading without an unexpected pattern change.
7. Test HUMANIZER and VELOCITY CURVES opt-in, then ECHOCITY Harris dry/wet
   repeats. Check note release, output ownership and audible timing. Watch
   JACK XRUNs and callback load under a realistic musical sequence.
8. Open an assigned velocity/volume slider, move its base value, and confirm
   its modulation curve and live controller marker remain attached.
9. Restart only as part of an authorized installation test; verify patch,
   chains, snapshot references and routing return together.

## Deliberate limits

PAUSE/RESUME, cursor-only release advancement, recursive/recall Conductor
actions, MASTER redesign, PR #106's entry/exit model and additional
ECHOCITY effects are not implemented by this RC. The exact current Pi source,
physical MIDI routing and long-duration audio performance must be verified
before declaring this candidate releasable. Five-size browser captures from
the integrated source were reviewed and their real PNG artifacts and manifest
were committed as evidence. See
`v2-dickinson-rc-ledger.md` for commit-level evidence and exact CI runs.
