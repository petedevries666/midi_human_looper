# INSTRUMENT links to native Zynthian chains

This beta synchronizes an existing MBMF INSTRUMENT's name and fixed MIDI output
channel with an explicitly selected Zynthian instrument chain. It does not create
instruments, synth chains, JACK connections or native input-matrix routes.

On Zynthian, open the MBMF controller pages **Instrument links 1**, etc. The
**I1 Zynthian** selector links INSTRUMENT 1. Destinations include the chain number,
title and channel. Select **UNLINKED** to stop synchronization; the last musical
name/output channel is retained. Native chain names are converted to printable
ASCII and limited to 16 characters in the engine; the API retains the full title.

Linked names and channels follow Zynthian at rest. During playback, armed capture,
recording, held notes, active instances, movements or snapshot morphs, changes are
deferred. A destination using ALL must be given a fixed channel before binding.
Input channel, level, transformers and enabled state are not synchronized.
Manual edits of a linked name/output channel are replaced by the host values on
the next idle refresh. Unlink first to use independent musical values.

Chain objects receive UUIDs. Deletion/recreation, including reuse of the same
chain and processor numbers, does not silently redirect an existing link. Missing
destinations are reported as `destination-unavailable`; the native selector shows
**DESTINATION MISSING**. Musical settings are retained. This is metadata and
channel synchronization, not an output-muting or audio-routing guarantee.

Host links and UUID/signature records are saved in native Zynthian engine
snapshots, outside portable musical projects. The opt-in owned installer hook
resolves Oram's `MB/N` snapshot keys against the processor ID when slots use `MB`.
Equivalent legacy aggregated snapshots are accepted; conflicting copies refuse
restoration. Importing a different portable project into the same processor keeps
host links for matching instrument IDs; unlink first if that is not desired.

Install only after checking the existing ownership manifest:

```sh
python3 -B zynthian/install.py --upgrade-adapter --host-chain-links --check
python3 -B zynthian/install.py --upgrade-adapter --host-chain-links
```

Use Zynthian's native save-state/restart actions. A direct systemd stop does not
save the current native snapshot. Never remove sockets with a live owner.

The optional authenticated `/api/v1/zynthian/chains` GET endpoint exposes inventory,
binding state and `routesManaged: false`. POST accepts only a bounded bind envelope
with instrument ID, destination UUID, inventory revision, engine revision and
engine session. The adapter endpoint is a per-processor mode-600 Unix socket.
Portable engines without this endpoint report the feature unavailable.

Tests:

```sh
python3 -B tests/test_zynthian_instrument_links.py
python3 -B tests/test_zynthian_snapshot_keys.py
python3 -B tests/test_zynthian_instrument_links_engine.py
python3 -B tests/test_zynthian_destinations.py
python3 -B tests/test_zynthian_install.py
```

The real-engine integration test is private and uses no JACK. Unit tests cover
two instruments/destinations, renames, channel changes, stale state, performance
deferral, recycled identities, snapshot keys and exact installer hook removal.
They do not qualify multi-synth hardware routing. No Web asset or JSFX is changed.
