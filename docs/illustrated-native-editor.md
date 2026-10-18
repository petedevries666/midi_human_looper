# Illustrated native editor

The real editor uses the approved design-preview header and the 32 original
illustrations from Pierre's two 4-by-4 sheets. Crops retain source coordinates
and SHA-256 hashes in assets/tiles/manifest.json. Fonts and their OFL licenses
are local; no external font or artwork requests occur in the product.

Stable module identity selects a semantic illustration pool. Existing modules
use 20% artwork opacity and Smart Switch add tiles 90%. Smart Switch cards use
the supplied compact layout: name/source/step, edit, snapshots, ACTION or
CONDUCTOR and one real press/release TEST. Add tiles all call the same native
capacity-checked action. An empty Action switch can enter the Conductor editor
through APPLY & OPEN CONDUCTOR after its current draft is committed.

Sections collapse independently and can be reordered using their drag handle
or keyboard-accessible up/down buttons. Browser-local preferences retain this
presentation order only; no MIDI, patch or Conductor order changes.

## Validation on the physical beta installation

Asset integrity and actual HTTP route/authentication tests pass; asset selection
identity checks and JavaScript syntax checks pass. The real live editor was
reviewed at 320x240, 800x480, 1366x768, 1440x900 and 1904x1032 without document
horizontal overflow. Actual add, TEST release, Action-to-Conductor editing,
keyboard reorder and persistence were exercised against the physical native
engine. Screenshots are real live views, not demo or mocked responses.

Pierre explicitly approved direct validation on his interface in place of the
AGENTS five-size screenshot-script workflow. scripts/screenshots.sh was not
run on the Windows workstation or the 2 GB performance Pi; these live captures
do not claim the full deterministic demo/recovery suite. Drag and keyboard
reordering both have interactive coverage on the installed physical editor.
The 320-pixel switch editor retains its bottom actions without horizontal
overflow. Installation verifies the complete resident source memory and
Conductor after restarting the Zynthian UI; JACK and LUMAZ stay untouched.
