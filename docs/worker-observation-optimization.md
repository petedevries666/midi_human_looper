# Worker-only WebSocket serialization reduction

Based on audit PR #72 over #71; no native/EEL/JSFX, UI, installer, schema or musical
ownership change. Every subscriber previously encoded the same cached observation
again. Now immutable JSON bytes share that same 250 ms observation window. Expiry
and every mutation, including failed requests, clear both caches. Direct command
responses remain fresh/uncached. No lock or allocation is added to the MIDI thread.

Production `Control.observation_payload()` is used by the real WebSocket handler.
Parallel tests count one query and one encoding for 64 subscribers, force expiry
while the provider returns the same object, and verify failed-mutation invalidation.
Actual native API/WebSocket reconnect tests pass. No per-client scheduling or new
state model is introduced.

## Measurement

`scripts/benchmark-observation.py --output /tmp/result.json` starts a private native
demo. The two paths consume the **same actual 11,714-byte observed state**; expiry
is held only for the benchmark and tested separately. Nine samples × 256 reads,
CPU clock without allocation tracing; separate warmed-cache tracemalloc pass:

| Quantity | Re-encode each read | Cached read |
|---|---:|---:|
| Median Python-worker CPU/read | 144.648 µs | 0.360 µs |
| Transient traced allocation peak | 23,542 bytes | 256 bytes |
| Retained encoded payload | none | 11,714 bytes |

Raw samples and conditions: `docs/evidence/mega-audit/worker-performance.json`.
The first encoding of a fresh snapshot still costs serialization; this is a warm
cache result, not a 400× engine speedup. State querying, network writes, normal
expiry and JACK callback/CPU/RSS are not measured by this microbenchmark. No Pi
latency, XRUN reduction or concert stability improvement is claimed. The earlier
`before.json` timing had tracemalloc overhead and is not the comparative CPU result.

Known unrelated audit findings remain open, including #63 real-time qualification
and learning a Controller source cancelling unrelated MOVEMENT ownership.
