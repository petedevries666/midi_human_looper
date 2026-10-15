# Integrated candidate: prepared LIVE qualification

**Latest measured rerun:** [final native-source 3acebd5 table and raw evidence](evidence/release-candidate-75/final-source-3acebd5/README.md). The earlier measurements below remain preserved, not overwritten. The new matrix also exits1: LIGHT/256 peaks228.221 ms CPU and STRESS/256 fails receiver chronology. NORMAL is clean in two short12-second windows; that does not erase the earlier failure.

Private dummy JACK at 48 kHz; 12 seconds per case; no browser/edit/SAVE/LOAD in measured windows. Build `fb81761719ff76a477cd8cf09ea0316fb126e3ff`. Native/Controller/JSFX sources are identical to the final candidate (later changes are Web UI/tests/docs/evidence; native execution sources are unchanged). Thread CPU and wall time are separate. No physical hardware qualification. Three old standalone Cloud fixture processes were left untouched; see environment.json. No other test/build jobs overlapped these windows.

**Exit 1. NOT a passing qualification.** The 256/NORMAL capture has a chronological regression. XRUNs occur in every profile. No assertions were relaxed.

| Frames / deadline ms | Profile | Active PHRASE sources max / MOVEMENTS min–max | Notes / CC per second | CPU p95/p99/max ms | Wall p95/p99/max ms | CPU / wall overruns | XRUN | Overflow / rejected |
|---|---|---|---|---|---|---|---|---|
| 512 / 10.667 | LIVE_LIGHT | 1 / 1–1 | 2.00 / 24.00 | 0.113/0.567/2.412 | 0.114/0.568/2.458 | 0 / 0 | 20 | 0 / 0 |
| 512 / 10.667 | LIVE_NORMAL | 3 / 1–2 | 12.00 / 44.48 | 0.153/0.782/2.405 | 0.170/0.852/3.263 | 0 / 0 | 8 | 0 / 0 |
| 512 / 10.667 | STRESS | 12 / 7–8 | 719.90 / 742.39 | 0.541/1.222/2.814 | 0.556/1.242/2.815 | 0 / 0 | 1 | 0 / 0 |
| 256 / 5.333 | LIVE_LIGHT | 1 / 0–1 | 2.00 / 24.66 | 0.097/0.233/99.753 | 0.105/0.288/99.788 | 2 / 2 | 20 | 0 / 0 |
| 256 / 5.333 | LIVE_NORMAL | 3 / 1–2 | 12.00 / 44.74 | 0.122/0.749/5.149 | 0.145/0.920/51.210 | 0 / 1 | 65 | 0 / 0 |
| 256 / 5.333 | STRESS | 12 / 7–8 | 711.58 / 730.49 | 0.586/1.181/6.052 | 0.593/1.189/6.286 | 1 / 1 | 6 | 0 / 0 |

LIGHT: 1 PHRASE, 1 MOVEMENT at 25 Hz; NORMAL: 3 PHRASES, 2 MOVEMENTS at 25 Hz, STEP changes and unmapped expression CC takeover; STRESS: 12 PHRASE sources, 8 MOVEMENTS at 100 Hz plus note bursts. Actual active counts/rates, every action, timestamps, raw MIDI, callback CSV and stage summaries are committed per case. LOOP/ONCE duty and integer deduplication mean nominal source density is not emitted events/second. STOP/PANIC and cleanup assertions are retained.

The 99.753 ms CPU / 99.788 ms wall LIGHT/256 callback is not attributable merely to off-CPU scheduling: user+system time agrees. It has zero input events, zero commands and zero pending output. 99.680 ms CPU is bracketed in `input_recovery`, while EEL takes 52.429 µs and MOVEMENT parameter work 4.189 µs. That bracket includes JACK buffer acquisition/input/recovery operations; individual library function attribution remains unknown. No reasoned engine algorithm change can be made from this bracket alone.

NORMAL/256 has a captured regression: frame 358656 offset 144 CC21/127 precedes frame 358656 offset 16 CC20/15. Native per-callback order-error count is zero and overflow/rejection is zero. This does not prove that the capture is harmless or identify the emitting vs receiving cycle: the existing five-field sink lacks a callback ordinal to distinguish repeated JACK frame time after XRUN. Keep the chronological assertion failing. Next diagnostic: add a bounded sink callback ordinal and split the ingress bracket around JACK buffer acquisition, then reproduce; do not sort the captured data or weaken the assertion.

NORMAL/256 measured CPU maximum 5.149 ms differs from the 6.549 ms setup callback outside the measured musical window. Reports/tables use the measured window only. 51.210 ms wall maximum and 77.919 ms maximum entry gap demonstrate substantial scheduling/timing problems, but not all peaks are off-CPU. No claim that the native engine or Cloud environment alone explains them.

GO: code review and further controlled diagnostic work. NO-GO: release/concert timing claim or automatic main merge while this qualification is failing. Physical V4 is a separate controlled acceptance gate, not an inferred PASS.
