# Audit evidence

Fresh read-only baseline: #71 `74c72d8db495f9c08a6e2c7ba4eed3aeaf7547a0`,
main `ab37a75`. Full combined baseline selected native/JACK/Chromium/Webconf and
exited 0 (`baseline-combined.exit`), including the explicitly retained legacy
ONCE compatibility XFAIL. Output artifacts from Webconf tests are archived here;
source files were not edited during that read-only phase.

The baseline run overlapped the private reproduction/worker benchmark briefly
while JACK tests were running. No RT stability claim is derived from this run;
it checks functional assertions only. #63 historical deadline data is referenced
from its original branch, not recomputed or attributed to this overlap.

`before.json` reproduces SAVE data loss in both native extension envelopes using
the actual native binary and HTTP editor: HTTP 200, original bytes not preserved,
future fields gone. `reproduce-before.py` uses a private native demo and disposable
patch directory, never user projects. Run it with the known baseline checkout and
its matching `HEADLESS_BINARY`; after the fix it reports refusal rather than loss.
The initial encoding benchmark uses CPU clock **with tracemalloc overhead**; it
is not raw callback or realistic wall latency. A separate before/after JSON-worker
benchmark will report untraced CPU and allocation measurements explicitly.

`preservation-tests.log`: 20 tests exit 0 (5 new preservation tests plus 15 existing
native API tests discovered by unittest). New cases cover SAVE/LOAD/export refusal,
known/legacy compatibility, source preservation and immutable-project stage
rejection without mutation. No schema, DSP, JSFX, UI or installer change.

PR metadata/ancestry snapshots and dry-merge marker extracts are included. Marker
counts are not conflicted-file counts. These are read-only merge-tree diagnostics,
not actual merges. Actual Oram/JACK services and LUMAZ were never operated.

The aggregate runner now includes #67 source filtering, #71 authorization/native
menu and the new preservation tests. Chromium runs update/phrase-channel UI;
Chromium+JACK runs #68's actual channel-voice/ownership/SMF suite. No existing test,
assertion, sanitizer gate or XFAIL was removed. Full corrected-code results are
recorded separately when executed; baseline success alone is not final validation.

## Final executed gates

Corrected #73 expanded combined command (same flags as baseline), exit 0:
`final-combined.log` / `.exit`. Includes 18,508 EEL checks, 704 dedicated phrase
output checks, real dummy-JACK captures, Controller ASAN gates, both UI race tests,
Chromium and real HTTP/Webconf fixtures. Intentional overload-counter assertions
and legacy ONCE XFAIL remain visible. No assertion was lowered.

Final #74 isolated updater change: 15 updater tests, 8 backend tests and 4 native
menu tests exit 0; full affected targeted suites in `update-cas/`. Also reran
20 preservation tests and 4 observer tests, exit 0. No unnecessary repeat of the
full JACK/browser suite after the updater-only guard. `update-cas/after.json`
shows correct settings refusal and the still-open unrelated Learn cancellation.

Matched warm-cache worker measurement: `worker-performance.json`, nine × 256
reads, median 144.648→0.360 µs CPU, traced transient allocation 23,542→256 bytes,
11,714 encoded bytes retained. Untraced CPU timing is not the earlier traced
`before.json` baseline and not a callback measurement. First encoding unchanged.

All baseline/final Webconf PNGs were visually inspected. The 25 protected issue
#54 files, JSFX SHA256, native engine, `headless/web/` sources and Oram router
were verified unchanged against #71. No OS, JACK, LUMAZ or hardware modifications.
