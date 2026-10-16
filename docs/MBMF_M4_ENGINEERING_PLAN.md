# M4 — execution checkpoint

Source: #85 `13ed0961c839cd79b3391b14f0bc77b1cfdf268c`, comment
https://github.com/petedevries666/midi_human_looper/pull/85#issuecomment-6203741796
and the user's complete M4 mission, read on 2026-10-16. Native + Web remain the
active targets; REAPER is frozen. No changes to the deployed Zynthian, routing
activation, live hardware REC, merges, or issue-54's 25 protected files.

## Recovery / dependencies

The existing checkout and caches were recovered, not cloned or reset. Interrupted
independent M2 work is preserved and pushed as `2a62570` + `3a5d357` on
`fix/reveal-midi-safety`; it is **not** silently included in M4. M4 branch
`fix/m4-routing-diagnostics` starts exactly at #85, retaining #82's musical stack.
No other M4 implementation PR was open at inspection.

## Increment 1 — routing and diagnostic boundaries

Confirmed before/after: six new assertions expose five transient-admission
failures plus a missing refresh quarantine. #85 would invoke virtual route
`enabled=1` even with no opt-in, malformed config, absent keyboard or failed
native readback. A later quarantine did not undo the transient risk.

Implementation: snapshot old matrix, remove desired JACK fanout, quarantine and
verify **all** virtual routes (continue closing after an individual failure),
then isolate physical/internal inputs, verify MULTI and all exclusions, then
admit allowed synth destinations. A late setter failure closes virtual routes
before restoring owned physical inputs. No synth names or new routing shortcuts.
Tests record every native setter call in `evidence/m4/native-setter-calls.jsonl`.

The source `midiCount` remains unchanged. Add cumulative, single-processing-thread
counters, copied through the existing bounded status queue:

| Status field | Exact boundary |
|---|---|
| `midiReceived` | Events reported in the JACK input buffer, including intentionally rejected input |
| `midiInputAccepted` | Successfully copied from JACK to the host ingress queue |
| `midiGenerated` | Public MIDI output packets produced for host output, plus emergency CC attempts; no private control markers |
| `midiQueued` | Normal packets admitted to the host JACK output queue |
| `midiWritten` | Successful `jack_midi_event_write` calls, including emergency CCs |
| `midiDropped` | Known host ingress/output rejection or queue cancellation; a failed write retained for retry is not a drop |
| `midiWriteFailures` | Failed JACK write attempts, including retryable attempts |
| `midiRecoveries` | Host emergency cleanup passes (including commanded chain cleanup) |
| `outputOverflow` | Existing aggregate overflow/fault notification count, not recording overflow |

These are stage counters, not an end-to-end conservation equation. Internal DSP
admission failures remain separately visible as `instanceRejected`/`instanceError`.
`midiGenerated` is not a synth-delivery claim; neither are successful JACK writes.
The smoke tool reports boundary deltas, retains the generation/XRUN guard and
also rejects receive/write storms. Old runtimes are labelled legacy generation.

Executed on native x86_64 Cloud, using production EEL and private dummy JACK:

- New routing tests on #85: exit 1, 5 failures + 1 error, recorded unchanged.
- After fix: exclusive input 22, firewall 7, native-source 4, installer 30,
  adapter 7, legacy routing 5 tests: all exit 0 (75 tests).
- Smoke tool: 3 tests, exit 0. Actual native/HTTP: 16 tests, exit 0.
- Real JACK: 3 input events -> 3 accepted -> 3 generated -> 3 queued -> 3
  successful writes -> 3 receiver events, at offsets 16/32/64; no drops or overflow.
- Initial JACK run failed with an empty receiver trace during multiple logged
  client XRUNs; retained as `midi-jack.log`, not relabelled PASS. An isolated rerun
  passed (`midi-jack-rerun.log`, `midi-boundaries.json`). No deadline assertion was
  weakened. This is functional evidence, **not** real-time or ARM64 qualification.

## Feedback paths and remaining isolation risks

The helper checks MB self-routes, MIDI-only destinations, native chain `midi_out`
return paths and the desired JACK graph. Explicit keyboard isolation blocks direct
bypass to synths and internal seq/step/CV input return to MB. DIN/ttymidi and other
unselected physical sources remain unchanged. User observation: MPKmini2 became
exclusive to MB, whereas DIN-5 remained on both chains. This does not prove that
ZynMidiRouter's internal matrix or the *actual* live JACK graph has no return path.

The desired graph is not an inventory of every live JACK connection or client
internal forwarding behavior. Arbitrary external hardware loops, recorder returns,
manual JACK edges and native UI changes need a real graph/matrix audit. The
helper stays default-off without explicit exclusive input policy. Reconfiguration
quarantines routes and is not claimed to be a seamless live-note operation.
**No hardware activation is authorized or performed by this PR.**

## Next increment — free-time clocks / capture diagnostics

A production ChainMode/EEL test reproduces the transport STOP incorrectly ending
FREE TIME capture (`clock-before.log`). This is a distinct defect; no evidence yet
links it causally to the hardware storm. Next: continuous audio-cycle clock for
capture-gap detection, transport independent source timing, precise error codes,
bounded validation and previous-phrase rollback; preserve optional grid capture.

## Safest hardware next step (NOT RUN)

Review immutable SHAs and offline evidence first. Leave MB output disconnected;
inspect current JACK edges, native input matrix, snapshot and install configuration
read-only. Do **not** install, enable exclusive/native routing, run REC or use the
smoke tool to justify automatic activation. Hardware testing requires separate
user approval and an emergency disconnect plan. No code here changes OS/JACK,
LUMAZ, tokens, installer or updater.
