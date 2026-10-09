# JACK timestamp delivery correction

ysfx keeps the order in which JSFX calls `midisend`. A JSFX may produce a later
sample-offset event before an earlier one, especially across independent voices and
generators. JACK requires ascending offsets within each output buffer. The previous
FIFO attempted writes in production order; after a later event, the earlier write
failed and was deferred to the next block at offset zero. Notes were retained, but
their timing was changed.

A real JACK regression demonstrates the failure: generated pitches/times
`90@400, 91@16, 92@220, 94-On@120, 94-Off@120` arrived as `90@400` in one block
and the remaining events at offset zero in the next. With the correction they arrive
in the same block at `16, 120, 120, 220, 400`, with the equal-time Note On before its
Note Off. The fixture uses the actual JSFX model and a temporary gated `@block` tail,
triggered by real JACK MIDI; no production JSFX or patch schema is changed.

The host allocates an 8,192-packet batch and index array at startup. It copies output
into the batch, detects already ordered blocks, otherwise sorts only indices by
(timestamp, original ordinal), then appends message bytes to the existing FIFO.
Sorting requires no dynamic allocation or GUI/shared scratch. Already ordered
bursts, including normal PANIC, skip the sort. Capacity/oversized-event overflow still
uses the existing emergency-release recovery. Deferred older bursts remain ahead of
the new block and retain the documented zero-offset draining behavior.

Run the actual desktop graph with the existing dependency setup:

```sh
HEADLESS_BINARY="$PWD/.build/midi-headless-engine" RUN_JACK_TESTS=1 scripts/headless-test.sh
```

This starts a named dummy desktop JACK server; do not run it on a live Zynthian server.
All three graph cases are required: normal routing/PANIC, deliberate FIFO saturation,
and nonmonotonic/equal-time output. Pi callback timing and Firefox remain separate
physical acceptance tasks. `midiCount`/`lastEvent` describe engine production; the
pending-output metric indicates queued physical delivery.
