# PR A differential audit: conditional GO for PR B development

Compared **clean PR50 `25fcb1e458ffdce7286ff4c60cd4546d586e19a4`** with
**PR56 `706f90ca7f22d0ee5d8dcdcac361861143ef5519`** on the same Cloud machine.
No merge, hardware access or deployment. Issue54 remains unchanged.

Current contract: PR55 **`73cdee5604992ca3bd68e4c6c3b97c545333b127`**, all 878
lines reread. Q1/Q2/Q4 are resolved; Q3 numerical limits still require measurement.
Q2 restarts a non-loop phrase at time zero when JOIN exceeds its duration.
Q4 releases owned sounding notes on PAUSE, preserves position, and RESUMEs future
attacks only, filtering historical orphan Offs and protecting independent owners.

## Controlled comparison

All **27 tracked production files** (JSFX, native/API/web, descriptors, Zynthian
adapter) are byte-identical. One binary built from the clean PR50 checkout,
one JACK probe, pinned ysfx, Python/Chromium, 48 kHz, timing v2, 8192-frame private
dummy JACK were shared. Fresh private engines/HTTP workers/browser instances per
trial; serialized order **base → A → A → base**, two repetitions per version.
Do not use a shared binary for future PR B when production code differs.

| Test | Clean PR50 | PR56 | Interpretation |
|---|---|---|---|
| Existing three-chain JACK workflow, including Chromium editors | 2/2 PASS | 2/2 PASS | Earlier spontaneous XRUN not reproduced in these trials |
| Same original Chromium workflow + passive command diagnostics | 2/2 PASS | 2/2 PASS | No difference demonstrated |
| Same A Chromium workflow + passive diagnostics | 2/2 PASS | 1/2 PASS | One VELOCITY-editor timeout, before A's added LOOP precondition |
| Each checkout's **unaltered** Chromium workflow | 2/2 PASS | 2/2 PASS | Single trials cannot establish absence of races |
| Controlled pending PANIC reply, then enabled mode selection | 2/2 FAIL, mechanism reproduced | 2/2 FAIL, mechanism reproduced | Pre-existing dropped command; idle positive control succeeds |
| Actual parameter telemetry between EDIT pointer-down/up | 2/2 FAIL, mechanism reproduced | 2/2 FAIL, mechanism reproduced | Pre-existing detached-target/lost click; idle positive control succeeds |
| Controlled interruption of fixture-owned JACK process | 2/2 PASS safety response | 2/2 PASS safety response | Existing guard aborts capture, zero active notes/overflow |

The final three cases were rerun using the permanent diagnostic helpers, also
with two repetitions per version, with identical outcomes. The negative browser
cases **exit 1**; they are not successful features or artificially green tests.
The original three ownership XFAILs remain unchanged and strict execution still
exits 1. Compatibility fixtures still pass all five tests.

## Classification and actual causes

**No runtime regression introduced by PR A identified.** Production bytes are
identical and the sporadic editor timeout occurs before its additional test
logic. The stricter LOOP precondition exposes a missing application; it does not
change browser/native execution.

**Confirmed pre-existing UI defects:**

1. `app.js` `command()` returns false immediately while `pending` is true, but
   the mode selector stays enabled. Hold only the real private PANIC HTTP reply
   for 750 ms: LOOP selection sends **zero parameter POSTs**, native mode remains
   ONCE, and no error is displayed. Once idle, the identical edit sends its POST
   and native mode becomes LOOP. CSP stays enabled; no engine/API response mocked.
2. Native parameter telemetry rebuilds module DOM. Change real transpose while
   EDIT is pressed: the original button becomes detached, pointer-up does not
   open VELOCITY. The same click when idle succeeds. No mocked MIDI renderer.

**Intermittence and residual unknowns:** the spontaneous historical JACK XRUN
trigger remains unknown. Controlled SIGSTOP/SIGCONT of only a private fixture
process reproduces its error class on both versions: `chainError=1`, recording
and playback stopped, no active notes, no output overflow. This validates the
existing guard, not the cause of the historical XRUN or Pi latency. Likewise,
the exact antecedent of every historical editor timeout was not captured; a
matching UI loss mechanism is demonstrated, not claimed as proof of every event.

Four initial pending-edit diagnostic trials were invalid because a Playwright
string predicate hit CSP's unsafe-eval restriction. They are explicitly excluded
from product results. Function predicates fixed the helper without changing CSP.
Recorded initial statuses/hashes remain in `followup.json`; those old temporary
raw files were overwritten by the corrected trials and are not misrepresented
as available. Corrected trial logs/hashes are in `pending-corrected.json`.

## Precise gate to start PR B

**GO for scoped musical-core development, not GO for integration/release.**

- B changes note/instance ownership and bounded admission only. Keep UI, installer,
  security and schema changes outside B. Retain legacy trigger compatibility;
  implement/test the independent admission context explicitly.
- Build and test **B's own binary**. Require ordinary PASS for affected real-EEL
  MIDI tests, new routed owner/generation/pairing/overload cases, existing free
  recording/overdub/SMF/portable fixtures and Controller normal/ASAN tests.
  Baseline XFAILs stay visible; promote a case only with real corrected output,
  retaining the separate legacy-policy test where relevant.
- Run the unchanged positive JACK workflow at least twice, independently of
  browser workloads, with unchanged clock/overflow assertions. Run controlled
  callback interruption: require capture stop, correct error, zero owned notes,
  unchanged source guarantees and bounded cleanup. New output/ownership failures
  are **NO-GO**. Repeated spontaneous XRUNs require recorded diagnosis, not retries
  until one green run or larger buffers to hide them.
- Continue running and publishing the complete combined suite and Chromium
  workflow. Keep the two confirmed browser counterexamples as FAIL. They may be
  nonblocking **only for B's no-UI scope**, with the matching diagnostic signature
  and unchanged production UI. Any different browser/API failure, source loss,
  new causal link to B or new regression is NO-GO and must be investigated.

Do not delete tests, disable assertions, waive arbitrary browser failures, lower
safety thresholds or call the full suite green. These outstanding UI defects
remain blockers for a usable integrated release. Physical REAPER/V4/Helix and
playable-buffer qualification are still pending.

## Evidence and reproduction

[Summary/provenance](evidence/conductor-comparison/summary.json),
[unaltered/callback trial records](evidence/conductor-comparison/followup.json),
[permanent helper results](evidence/conductor-comparison/permanent-results.json)
and their adjacent logs retain every valid comparative outcome. Original PR A
submission failures remain in `conductor-a-validation.txt`.

The reusable comparison driver never installs, deploys or changes JACK services:

```sh
# Both checkouts must have identical production files for this PR A audit.
# Build the common binary from clean PR50 with the existing headless-build.sh.
export JACKD=/workspace/scratch/midi-deps/root/usr/bin/jackd
export JACK_DRIVER_DIR=/workspace/scratch/midi-deps/root/usr/lib/x86_64-linux-gnu/jack
export CHROMIUM_PATH=/usr/bin/chromium
/workspace/setup-tools/venv/bin/python scripts/conductor-compare.py \
  --base /workspace/mbmf-conductor-base --candidate /workspace/mbmf-conductor-a \
  --binary /workspace/mbmf-conductor-base/.build/midi-headless-engine \
  --probe /tmp/mbmf-compare-chain-probe --output .build/conductor-comparison \
  --repetitions 2
```

Build the probe with the existing recipe from `headless-test.sh`:
`c++ -std=c++11 -O2 tests/zynthian_chain_jack.cpp -I"$JACK_INCLUDE" -l:libjack.so.0 -lpthread -o /tmp/mbmf-compare-chain-probe`.
The driver returns nonzero when a real or reproduced contract failure is present;
JSON distinguishes completed PASS, reproduced unmet contract and fixture error.
This is a diagnostic audit, not a replacement for the combined regression runner.
