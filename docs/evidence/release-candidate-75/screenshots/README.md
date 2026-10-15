# Actual screenshot evidence

The final five-viewport workflow exits 0: 184 real PNGs, zero automated layout failures. All 15 contact sheets (every view) and all eight full-size native recovery captures were inspected. The accepted PNGs and source/dirty/build metadata are in `docs/screenshots/manifest.json`. Source/build is 3f79687; uncommitted differences at capture were this helper, documentation and output, not the musical engine or editor.

The `REJECTED` PNG is negative evidence: continuous observation produced incomplete paint despite valid DOM. Resize and CDP recapture did not reliably resolve it. Static recovery captures now temporarily suspend only the browser observation handler, restore it in finally, and assert native sampleClock advanced. No musical state, DOM values or native responses are fabricated. These images do not qualify continuous live rendering, which remains an open risk. Ordinary browser interaction gates retain live observation.

Command: `source /tmp/mbmf-b-env.sh; SCREENSHOT_PYTHON="$TEST_PYTHON" scripts/screenshots.sh`. Dependencies are documented in AGENTS.md.
