# Engineering audit — MBMF, 14 October 2026

Historical audit snapshot. For current integration, corrected A21 and new measured
release blockers see [issue #75 candidate](release-candidate-75.md). This report
does not claim that its old branch statuses or A21 status are still current.

Read-only baseline: main `ab37a75`; active #71 `74c72d8db495f9c08a6e2c7ba4eed3aeaf7547a0`.
All open/merged PR metadata through #71 fetched afresh; #69 head is now `a784aff`.
No merge, rebasing, hardware access, OS/service changes or LUMAZ modifications.

## Scope and architecture

Audit covers source/branch inventories, actual ancestry and dry merge analysis,
production EEL/native MIDI and control paths, schemas/SMF/project authority,
Oram router/adapter/installation, Webconf gateway/mDNS, #69 portal and #71 updater,
build/test gates, archived #63 measurements, isolated #25/#28 foundations and
REAPER/interchange adapters. This is a targeted engineering audit, not a formal
proof that every line or third-party dependency is defect-free. Hardware/API
fixtures and conclusions without dynamic reproduction are marked separately.

The native product is one ysfx/EEL musical core (`midi_human_looper.jsfx`) per
processor, hosted by `headless/engine.cpp`. Native Controller tokens arbitrate
snapshot, A/B and MOVEMENT targets. PHRASE ownership/generations live in the
shared runtime ledger. MOVEMENTS produce bounded CC/parameter automation; they
are not recorded-CC phrases. Python receives JSON/files outside processing;
bounded numeric commands and paused prepared plans cross into the engine. Web
state is authoritative native observation, not browser playback. Oram owns
JACK graph/channel filtering. Gateway `mbmf.local` uses process/socket identity
and dynamic ports; #69's separate `az.local` is a Webconf-hosted launcher.

This is not yet arbitrary ordered pedal processing: pitch/range can be ordered,
velocity/polyphony/ARP remain staged, independent mono/ARP admission is refused.
Those restrictions are safeguards, not dead code to delete. #25/#28 remain
unintegrated foundations. `experiments/headless` is an archived precursor with
no production imports, but still referenced by audit documentation; no speculative
removal is warranted. Multiple parameter/JSON validators are deliberate trust
boundaries, though equivalence tests must remain.

## Prioritized findings

Line references below are baseline #71 unless another PR is named. Reproduction
and classifications distinguish proven defects from limits / historical risks.

| ID | Priority / evidence | Location | Reproduction and impact | Treatment |
|---|---|---|---|---|
| A01 | P1, reproduced production API | `headless/server.py:34–36,562–589`; `controller_config.py:25` | Add unknown data under known-version `controllerEngine` or `globalSnapshots` to patch1, then SAVE: HTTP 200; bytes overwritten and extra data lost. LOAD also serializes only known wire data. | Isolated strict extension-envelope refusal + real native HTTP SAVE/LOAD and immutable-project staging tests. No schema or musical change. |
| A02 | P2, measured redundant work | `headless/server.py:48–54,136–140` | Several WebSocket consumers share the same observation object but each re-encodes JSON. Before benchmark captures actual 11,714-byte native state. | Cache serialized bytes within existing observation window; invalidate with commands/expiry. Separate worker-only benchmark; no RT claim. |
| A03 | P1, proven gate omission | `scripts/combined-test.py:31–54,67–91`; `tests/run_host_tests.sh:12` | Combined suite does not invoke #67 channel-source tests, #68 dedicated phrase-output suite or #71 new administrator tests/browser. A green combined run alone does not qualify those PRs. | Add targeted existing test entry points with correct native/JACK/browser gates. Never weaken existing gates. |
| A04 | P1, archived real dummy-JACK measurements, unresolved cause | #63 `docs/movement-realtime-qualification.md:13–110`, traces on `d6169f9` | LIGHT/NORMAL without browser have XRUNs/deadline excursions; Separate matrix peak: 26.849 ms wall / 2.437 ms CPU at 512, three MOVEMENTS at 100 Hz, no command in that callback. Other actual CPU spikes remain partly unattributed. | No benchmark-driven engine patch. Instrumentation not inherited in #71; controlled V4 measurement required. Concert qualification NO-GO. |
| A05 | P1, current metric limitation | `headless/engine.cpp:2090,2967–2971` | `maxCallbackUs` starts after input intake; excludes ingress and early flush. It is wall time, not thread CPU. It cannot locate old spikes or certify the whole callback. | Document; transplant #63 instrumentation selectively only after reconciling current output policy. No new parallel trace system. |
| A06 | P1, source and existing overload fixtures | `headless/engine.cpp:1973–1981,2860–2930`; `movement_engine.hpp:107–110` | JACK drains only 64 messages/block; MOVEMENT budget reserves CC cadence but not arbitrary phrase bursts. Backlog offsets collapse to 0 next callback; overload deliberately triggers emergency cleanup. | Preserve bounds/guards; large-buffer functional success is not low-latency throughput qualification. Measure density/receiver limits physically. |
| A07 | P1, documented restart scope | `scripts/zynthian-update.py:221–248,activate`; `zynthian/update/backend.py:104,176–181` | Installing compatible runtime recreates UI-owned children via stop/start `zynthian`, potentially interrupting other synths. Not MBMF-only hot activation. | Keep explicit confirmation and stopped gate; no deployment approval. Future host-lifecycle work must be separate. |
| A08 | P1, source/fixture gap | `zynthian/update/backend.py:153–178` | Final checkpoint precedes service stop, but physical MIDI can resume in that interval. Two stopped checks are not a host-wide atomic admission freeze. | Document TOCTOU risk; no invented musical lock. Controlled device test first; do not advertise "impossible during playback". |
| A09 | P1, security boundary limitation | `headless/web/update.js:19–22`; `scripts/mbmf-update-control.py`; `backend.py:111–130` | Administrator password travels over ordinary HTTP when using trusted-LAN URL. Same-origin/JSON/root socket/PBKDF2 prevent arbitrary unauthenticated install, not LAN sniffing or hostile co-resident root. | Isolated trusted network or existing HTTPS proxy. No new networking changes. Consider rate limiting after separate threat review. |
| A10 | P1, release eligibility unavailable | `backend.py:46–71`; GitHub stable-release API | Latest release endpoint actually returns 404. Draft #71 cannot offer itself or unmerged commits. | Intentional safety gate, not a login workaround. Require reviewed merged release + component manifest before routine update qualification. |
| A11 | P1, integration conflicts confirmed | #45 / #46 / #63 versus #71 | Classic three-way dry merge has conflict markers: #45 29, #46 56, #63 1 (marker count, not file count). Old gesture schemas / screenshots / current engine input-output paths overlap. | Do not wholesale merge. #45/#46 largely superseded; extract verified omissions only. Reconcile #63 trace regions with #68 remapping. |
| A12 | P2, ancestry debt confirmed | PR graph | #71 is 113 commits ahead and two merge commits behind main. Main implementations #27/#29 already occur in stack; merges themselves do not. #69 branches at #66, dry merge has no markers but is unqualified combined state. | Review #30-first ancestry in order, not a single giant blind merge; no merge this task. |
| A13 | P2, stale status confirmed | `docs/capabilities.md:68–77`; `docs/product-integration-status.md`; old checkpoints | Capability table still describes direct #64 fanout, generated phrase labels and older stack while #67 filters channels and names are editable. Same v1.27.1 header appears on main and active stack. | Refresh one authority matrix; use build SHA for deployment identity. Mark other checkpoints historical. |
| A14 | P2, incompatible interchange explicitly reproducible | `headless/phrase_midi.py:105–106,139–158` | Export may include recorded CC/program/bend/pressure; import deliberately rejects every non-note channel event. Such a file cannot round-trip back through current importer. | Document notes-only import; do not add unsupported CC capture semantics in an audit. Note-only roundtrip suites remain relevant to frozen REAPER. |
| A15 | P2, execution/storage caps inconsistent across interfaces | `headless/server.py:348,363`; `conductor_wire.hpp:10`; `controller_host.hpp:49,59`; `controller_engine.hpp:112` | Browser configuration request capped 32 KiB while conductor carrier allows larger documents; 16 sources/32 bindings/512 targets/12 ONCE and 2048 source events remain bounded. | List actual limits; no arbitrary Q3 changes. Need capacity proposals measured on Pi, not silent expansion. |
| A16 | P2, observation ambiguity | `headless/engine.cpp:2875–2894` | `activeNotes` is a bool per effective channel/pitch, not emitted-attack count or sustain-aware audio voice census. It is not proof that the receiving synth has no sustained sound. | Keep ownership tests and observe receiving MIDI/synth; do not infer hardware silence from telemetry alone. |
| A17 | P2, fixture reliability debt | `tests/test_conductor_execution_jack.py:11,16,48`; `tests/test_movement_jack.py:12,16,79`; #63 fixture fixes | Undrained stderr/stdout PIPEs in long running children can block when JACK is verbose. #63 moved some to files; current stack did not inherit those changes. | Preserve failed logs; selective fixture fix is safe if reproduced. Do not blame every XRUN on pipes. |
| A18 | P2, document/engine authority split | `project_sync.py:154–191`; adapter snapshot restore | PATCH SAVE is not the automatic restart checkpoint; explicit committed project is, and Zynthian snapshot overrides it. Filesystem locks are process-local, not cross-process CAS. | UI/procedure must distinguish authorities; deployment health fingerprint guards remain. Cross-process stress and power loss remain hardware gates. |
| A19 | P2, compatibility risk not dynamically proven | older runtime versus #68 channel policy | New phrase channel policy uses spare schema-7 cells; old binaries may retain bytes without executing the policy. Schema/fingerprint equivalence alone is not behavioral parity. | Audit downgrade capabilities with actual old/new binaries before authorizing rollback across #68; no silent truncation/retargeting. |
| A20 | P2, protected independent WIP | original checkout, issue #54 | 25 files differ independently of tracked stack; SHA manifest is the protection boundary. | Preserve byte-identically, never “consolidate” by reset or wholesale checkout. |


| A21 | P1, actual native runtime reproduced | `headless/controller_host.hpp:137–145,217–230`; `docs/evidence/mega-audit/source-learn-cancels-movement.json` | Start CH1/CC11 MOVEMENT (60 s), learn an unrelated source on CH2/CC21: active 1→0, cancelled +1. Existing-source `source()` invokes global Controller panic. This is authoritative native cancellation, not a claimed captured CC trace. | Leave musical policy unchanged in this audit; next ownership fix must scope source reconfiguration and demonstrate Controller/Snapshot/MOVEMENT isolation. Avoid Learn while auditioning automation meanwhile. |
| A22 | P1, activation function reproduced with service fixtures | `scripts/zynthian-update.py:247–254`; `backend.py:149–177` | Prepare update on port 8765, edit persisted config to 9000, activate old candidate: port returns to 8765, service stop/start called. Pending journal also carries outdated previous config. | Separate compare-before-activation fix: configuration mismatch refuses before journal/service/component mutation, with native-independent transaction tests. |
| A23 | P1, source audit / lifecycle gap | `headless/engine.cpp:1397–1407,2976–2997` | Host captures JACK sample rate/buffer size once; no size/rate-change callbacks are registered. Matrix tests launch separate clients at each buffer, not a live resize. Telemetry/deadline calculation may therefore retain startup values. | Treat runtime resize/restart as unqualified; verify Oram recreation/cleanup on V4. No callback reconfiguration/allocator changes in this audit. |
| A24 | P2, fixture/API mismatch | `tests/test_movement_persistence.py:27`; `controller_config.py:3–4` | Movement takeover fixture submits `returnPolicy=0`, whereas production wire uses `returnMode`; the unknown field is ignored and default OFF makes the test pass. That case does not validate explicit return-policy transfer. | Correct/extend fixture in a focused controller-ownership follow-up; existing policy-core return tests remain useful. Do not claim this test proves BACK TO STATE integration. |

No new universally reproducible P0 musical corruption is asserted. **P0 release
blocker** is making a concert-stability claim before resolving A04/A06 and actual
V4 validation. Confirmed A01 must be fixed before claiming lossless persistence.

## Safe implementation slices

#72 refuses unknown native extension envelopes and extends missing aggregate gates;
#73 shares already-observed immutable JSON bytes only. UPDATE configuration-CAS
refusal is a separately tested slice, not a musical ownership change. See the
final evidence README for executed outcomes and delivered PR heads. Confirmed A21
remains open: a green suite is not proof that source reconfiguration is isolated.

## Native safety and retained behavior

Ownership is instance/generation plus effective destinations; actual-emission
reservation and selective STOP are tested. Repeated pitch/chords/ALL outputs have
separate tests that must enter the aggregate gate. Sustain/physical ownership is
not a second browser scheduler. Independent mono/ARP restrictions must stay.
Legacy ONCE cross-source choke remains one intentional compatibility XFAIL; it
must not be renamed as a corrected independent-admission contract.

Code audit found no explicit heap growth, JSON, file/network I/O or lock introduced
inside MOVEMENT render. Curves/prepared plans allocate on paused worker; callback
uses fixed voices/packets/queues. This does not prove ysfx internals never allocate
or page fault; RAM-touch/configuration and third-party scheduling need trace/physical
measurement. Controller target lookup is linear up to 512 and snapshot dirty
comparison visits captured states when an observation is serviced; bounded does
not mean cheap. Do not optimize musical loops without attributed measurements.

Multiple Controller writers share tokens; stale MOVEMENTS lose ownership rather
than reacquire. New physical unmapped CC passes intact and cancels its target;
STOP ALL PHRASES leaves MOVEMENTS alive; PANIC cancels both. These are contract
gates, not opportunities for audit “simplification”. Note Ons at time zero and
free-time/SMF capture use authoritative storage, not export-only repair.

## Integration plan (review only)

1. Review #30 → #34 → #37 → #38 → #40 → #41 → #42 → #43 → #44.
   Main already has #27/#29 implementations. Preserve studio/interchange legacy;
   no new REAPER feature parity requirement.
2. #47 → #48 → #49 → #50, then #56 → #57 → #58 → #60 → #61 → #62.
   Keep ownership, schema and execution gates distinct; review unsupported modes.
3. #64 → #66 → #67 → #68, preserving #67 router filtering, not #64 direct synth
   fanout. #71 optional administration has separate review/physical gates.
4. #63 is not an ancestor of #64–#71. Reconcile its instrumentation and fixture
   fixes against current engine; do not overwrite #68 output behavior.
5. #69 is separate on #66 and mechanically merges without markers, but run
   Webconf/AZ/router/update coexistence tests before any eventual integration.
   #65/#70 are specs, not implementations. LIVE BYPASS/MIDI LOG remains unimplemented.
6. Do not merge #45 or #46 wholesale; current recovery incorporates newer gesture
   and screenshot behavior. Keep #25/#28 isolated until native continuation/ordering
   contracts exist. Superseded docs/design PRs are not runtime dependencies.

No measured DSP optimization claim is made. Worker serialization improvement is
measured separately, same state payload and timed method, CPU vs wall identified.
Build outputs are reused; no full-compiler or Pi build-time improvement is claimed.

## Freeze decision

REAPER-specific new features, @gfx expansion, new CONDUCTOR/MOVEMENT/modules or
parity ports are frozen. Preserve JSFX, old RPP/patch data and interchange source
compatibility tests. Native + Web are exclusive new-feature targets. Existing
shared EEL behavior may be reused; that does not authorize an automatic REAPER
port. Native work must not wait for frozen-platform execution/UI parity. Current
JSFX baseline blob/hash is recorded separately; no JSFX modification in this audit.

## Final delivery and qualification

Drafts: #72 (preservation/freeze/gates), #73 (shared observer bytes), #74 (stale
installation config refusal), stacked in that order above #71. No merge/deployment.
Complete corrected #73 combined suite exited 0, including actual EEL/JACK, Chromium,
Webconf, administrator tests, 704 phrase-output checks and both UI race tests.
Final #74 updater-only change passed all 15 updater + 8 backend + 4 native-menu
tests; preservation/observer suites were rerun too. No second final full combined
run is claimed for that updater-only change. Legacy ONCE XFAIL remains explicit.

Native/EEL/JSFX/UI source and #67 routing are unchanged by these audit fixes. The
25 issue #54 files were verified SHA256-identical. Four Webconf captures from both
combined runs were visually inspected; release-check PNG is explicitly an external
release-catalog fixture, not an available real update. The existing private native
binary reports #71 SHA `74c72d8`, whose native sources are byte-identical to delivered
code; Python control/activation fixes execute from the current checkout.

No ARM64 build, physical Oram activation/rollback, real receiver routing, Helix,
Firefox hardware, dynamic JACK resize or concert deadline qualification performed.
JACK loss can prevent final cleanup delivery altogether; receiver state after
port/server interruption must be measured, not inferred from an empty new process.
See [French executive summary](audit-executive-fr.md) for the first controlled
V4 test priorities and [evidence](evidence/mega-audit/README.md) for commands/logs.
