# REAPER legacy development freeze

Effective 14 October 2026, by product decision: **native Zynthian engine and Web
editor are the exclusive targets for new feature development**.

REAPER JSFX is frozen legacy. Do not add REAPER-only features, `@gfx` expansion,
CONDUCTOR/MOVEMENT execution, new modules or automatic parity ports. Do not remove
or rewrite the JSFX. Preserve existing RPP projects, patches and functioning
studio/live source-MIDI interchange; the latter remains an available future
concept, not a current requirement to delay native development.

Reuse current shared EEL/native behavior when useful. Relevant regression tests,
serialization compatibility and historical behavior remain protected. Freezing
a platform does not mean disabling its tests or renaming compatibility failures.
Native architecture must not wait for new REAPER engine/UI equivalence. Any
necessary shared-core correction should be scoped and tested as such, not an
excuse to expand the legacy product.

Audit baseline (unmodified):

- File: `midi_human_looper.jsfx`
- Header on both current main and active stack: `desc:MIDI Human Looper v1.27.1`
- Active baseline commit: `74c72d8db495f9c08a6e2c7ba4eed3aeaf7547a0`
- Active file Git blob: `4101e989cb6104864fdd251e2378d04774c046de`
- SHA256: `89684314f0889afcb94cd3c4c832ff35fda197bf739043ffd42f2d10244bd5d1`

The version header alone cannot identify features: the main/active files have
substantially different ancestry despite the same version string. Use build SHA
and capability gates, not “v1.27.1” as a deployment or parity certificate.

`modules/catalog.json` and generated shared conversions currently couple native
and EEL definitions. A later native-only extension must respect this freeze; do
not automatically regenerate a new legacy UI/feature merely to satisfy a parity
assumption. This audit does not redesign that generator or change the JSFX.
