# M5 Smart Switch panel

MIDI LEARN is directly below the name, outside collapsed timing controls. Its existing commit-then-learn behavior and exclusive native mapping stay unchanged. APPLY & OPEN CONDUCTOR remains the step/layer entry point.

The legacy sequence editor is shown in a collapsed compatibility section only when a nonempty legacy sequence exists and no native Conductor steps are active. This avoids competing ADD STEP controls for native Conductors, while retaining access to meaningful old configurations. No implicit legacy-to-native gesture migration occurs. Single-action and legacy execution unification remains separate unfinished work.

Validation: JavaScript syntax check passed. Visual viewport qualification and interaction tests remain outstanding; no live deployment or screenshot claim. The current Windows environment has no native build toolchain or working WSL distribution. Do not mark this draft ready before actual native-editor screenshots and keyboard/mobile checks.