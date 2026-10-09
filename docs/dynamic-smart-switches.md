# Dynamic Smart Switch collection

v1.26 replaces the fixed four-switch panel with a sparse collection of up to
sixteen actual engine records. Cards show name, type, exact MIDI assignment,
current step, stable ID and enable state. ADD SMART SWITCH opens a fresh draft;
EDIT opens only that card's complete configuration. A full collection reports the
practical sixteen-switch capacity rather than creating unsaved GUI-only cards.

DONE atomically commits the draft on DSP and closes the editor. CANCEL, ×, Escape,
or either outside mouse button discards it and cancels unfinished Learn. Successful
Learn captures also remain uncommitted until DONE. MIDI conflict confirmation
stages deliberate reassignment; other assignments are removed only on DONE.
Cancelling a new card leaves no switch. Cancelling an edit retains the previous
assignment, name, sequence and gestures. Name-only commits retain the live cursor.

TEST TAP/DOUBLE/HOLD explicitly previews the draft through the same dispatcher as
hardware, without changing Learn assignments. TEST is a performance action: any
phrase actually played/stopped during a test cannot be undone by cancelling the
configuration editor. Runtime counters/cursors reflect those explicit actions.

A card's × opens a deletion confirmation. Delete cancels pending gestures and
quarantines a held input's release. It leaves recorded phrases intact. Sparse
storage avoids changing any other switch's slot or ID. A replacement gets a fresh
ID. Special reset actions referencing a deleted switch are disabled so they cannot
accidentally target a replacement occupying the same storage slot.

Schema 6 appends twelve further records and a next-ID counter after the entire
schema-5 payload. Original four records and all old banks/addresses remain frozen.
The engine's runtime cursors, shuffle bags, undo storage and held-release quarantine
also grow. Both patch banks and the external DSP SAVE snapshot retain all sixteen
slots, IDs, sequences and settings. Legacy schemas 1–5 load with four cards; legacy
ALL SWITCHES reset targets migrate from the old sentinel to the expanded capacity.

The first four legacy records also contain controller-channel, phrase-trigger
channel and TIME DECAY metadata. Deleting a switch, committing its draft and undoing
its sequence preserve those unrelated fields. Drafts and runtime Learn listeners
are not patch configuration and are never saved.

Native tests create and operate five switches with isolated MIDI input, edit/cancel
and commit/reassign Learn, exercise popup lifecycle, deletion and slot reuse,
preserve legacy metadata, fill sixteen actual records and round-trip both banks
and JSON. Existing Phrase Switch traversal, re-entry reset, gestures, STOP/PANIC,
TEST, expression and phrase-trigger tests remain active. The native GUI SAVE fixture
contains a fifth switch and independent CC configuration, and the Lua test checks
its complete round trip. Hardware REAPER/Helix acceptance is still required.
