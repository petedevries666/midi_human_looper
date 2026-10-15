# UPDATE qualification — Cloud, no physical deployment

Code: `feat/reviewed-update-controls`, based on #68 `d155cbca608b33fde00ce02421272fcf9fdcb7e1`.
Actual native binary built at `e060877fb19f84e1464b3d6324e80959d00dca65`.
The delivered `headless/engine.cpp` and JSFX are byte-identical to that build's
sources. Later commits change only administration, tests and evidence. Screenshot
manifest honestly records `sourceDirty: true`: updater-only edits were made during
capture; Web UI source did not change. No engine timing qualification is inferred.

Prepared environment: `/tmp/mbmf-b-env.sh`, pinned ysfx
`8077347ccf4115567aed81400281dca57acbb0cc`, Python test venv, `/usr/bin/chromium`.

Executed, all exit **0**:

| Command | Result | Evidence |
|---|---|---|
| `scripts/headless-build.sh` | Actual native build, bounded FIFO PASS | build.log |
| `$TEST_PYTHON tests/test_update_controls.py` | 8 tests | backend-tests.log |
| `$TEST_PYTHON tests/test_update_native.py` | 4 tests | native-menu-tests.log |
| `$TEST_PYTHON tests/test_zynthian_update.py` | 12 tests, actual candidate engine/Web preflight and health | updater-tests.log |
| `$TEST_PYTHON tests/test_update_controls_browser.py` | Real native editor → HTTP → Unix worker, credentials/CHECK/cancel/reload | chromium-tests.log |
| `scripts/headless-test.sh` | 64 baseline tests + bounded FIFO; native API, registry, installer and routing fixtures | headless-tests.log |
| `SCREENSHOT_PYTHON=$TEST_PYTHON scripts/screenshots.sh` | 184 PNG view captures, five sizes, zero layout audit failures; recovery workflow passes | screenshots.log |

Inspected every manifest view via 17 labeled contact sheets (all five sizes), and
the release-check screenshot at original resolution. UPDATE wraps long revisions,
keeps disabled INSTALL/ROLLBACK when unavailable, and reports missing worker
explicitly. Existing tiny-screen dialogs scroll vertically; existing visual design
was not redesigned. PNG dimensions validated by the runner.

`docs/screenshots/update-controls-release-fixture-800x480.png` uses the **actual
native editor and administration worker**, with external GitHub release metadata
and kernel root identity fixtures. It demonstrates interaction, not an available
real release. Standard `update-unavailable-*` captures have no release mock or
installed administration worker; that is a truthful development setup state.
The GitHub latest-release API actually returned 404: routine updates are correctly
unavailable until review/merge/publication. No release was published by this task.

The 25 issue #54 files in the original checkout were verified SHA256-identical
against `/tmp/mbmf-issue54-preserved.json`. No protected file was modified.

Not run: physical V4/ARM64 build, real Oram confirm screen/systemd restart,
installation, actual GitHub-release activation, hardware rollback, JACK graph
qualification. Root peer identity/display/service operations are fixtures. No
full combined JACK/ASAN suite claimed: there are no MIDI engine changes here.

Known limitations and initial enablement/recovery: `docs/mbmf-update-controls.md`.
GO for code/security review; NO-GO for routine physical update until an eligible
reviewed release and controlled device restart/rollback acceptance.
