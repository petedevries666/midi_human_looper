# Codex implementation brief: illustrated module tiles

## Goal
Bring the ANONYMALZ/MBMF punk-animal art direction into the **real** MBMF UI, using the **two 4×4 contact sheets attached to the originating ChatGPT conversation** (32 rectangular illustrations). This is NOT a new mockup. Preserve existing engine APIs, events, IDs, MIDI behavior and edit interactions.

## Art asset preparation
1. Obtain the two source contact sheets from the user-provided attachments. They are **not yet committed to this branch**; do not silently substitute AI images or unrelated artwork. If unavailable in the Codex environment, leave an explicit asset dependency and stop before claiming visual completion.
2. Slice each 4-column × 4-row sheet into 16 separate thumbnails, crop precisely at the internal tile borders and exclude gutters. Keep aspect ratios, artwork and palette; do not regenerate or modify the drawings. Export optimized WebP/PNG assets into `headless/web/assets/tiles/`, plus a machine-readable manifest with descriptive, stable IDs, source sheet and source row/column. Confirm 32 assets, dimensions, sizes, no black gutter artifacts.
3. Choose semantically appropriate sets: **PHRASE** = music/performance/recording; **INSTRUMENT** = keyboards, guitar, bass, synth and instrument-playing animals; **TRANSFORMER** = cables, effects, machines and modular synthesis; **CONTROLLER** = switches, knobs, patch bays; **MOVEMENT** = motion, electricity, explosive gestures, sound-wave energy; **SMART SWITCH** = buttons, paws, triggers and expressive animals. Allow reuse across categories, but vary thumbnails across adjacent cards.

## Reuse the approved design-preview header and unify the entire UI design system
The existing **approved design reference is `index.html` on the `design-preview` branch**, plus the associated assets under `design/assets/images/`. Codex MUST inspect these files at implementation time and **port the actual header HTML/CSS visual treatment to the real running application**, not merely use them as inspiration. This supersedes the earlier warning against using the static preview as a source for *visuals*: the preview is the visual source of truth, but **never the source of real application behavior**.

- Reproduce the two-part Spunk X illustrated header, distressed image in the right-hand status/control cell, and `hori_separator_01.png` full-width separator with the carefully tuned join. Preserve Spunk's aspect ratio, full-width separator, and responsive layout; do not reintroduce the prior visible gap or distortion.
- Reproduce the compact **PATCH toolbar** styling from the preview beneath the separator, **but map every control to real existing handlers, IDs, state, and API endpoints** in the production UI. Do not port disabled demo buttons, simulated RUNNING labels, preview token values, or placeholder commands. Where an action does not exist, do not pretend it works; either omit it or document its missing implementation for a separate task.
- Carry the header's **visual vocabulary into all module groups and cards**: matte near-black backgrounds, thin gray borders, distressed thumbnail layers, sharp corners, compact industrial spacing, muted labels and deliberate yellow/purple/red highlights. The illustration remains secondary to readability and controls.
- **Unify typography** across the entire real UI: `Barlow Condensed` for section headers, PATCH/CLEAR/JSFX labels, action buttons, disclosure headers and prominent module titles; `IBM Plex Mono` for technical labels, numeric data, statuses, MIDI values, inputs and telemetry. Keep font sizes/weights and letter spacing consistent via shared CSS tokens. Watch for cascade specificity: a generic `button` selector previously overrode toolbar sizes in the preview.
- **Unify buttons** across PATCH, SMART SWITCH, MOVEMENT, PHRASE, INSTRUMENT, TRANSFORMER, CONTROLLER, EDITOR and TEST: consistent border, height, padding, hover, focus-visible, active, disabled and dangerous/PANIC variants. Preserve accessible focus contrast and avoid fading text via parent opacity.
- Extract reusable CSS variables/classes or a small stylesheet layer for typography, buttons, cards, layout, thumbnail opacity and section headings. Prefer progressive, scoped integration rather than a wholesale rewrite. No duplication of fake or disconnected HTML controls.
- Inspect `design-preview` and production `headless/web/index.html`, `style.css`, `app.js` before implementation; port visuals to the actual running UI while keeping every existing event handler, API contract and dynamic render intact.
- Add visual regression screenshots at desktop and mobile widths comparing the production result with the approved design-preview header. Explicitly verify the Spunk artwork ratio, separator width, PATCH typography, button consistency, and 20%/90% tile backgrounds.
- If the approved reference and the live app diverge, preserve live behavior and record the visual/functional mapping rather than silently adding inert controls.

## Visual specifications
- Existing **SMART SWITCH** tiles: illustrated background at **20% alpha**.
- **ADD SMART SWITCH** tile: illustrated background at **90% alpha**, with a contrasting text/overlay treatment so its action remains legible.
- **PHRASE** label/cards: illustrated backgrounds at 20% alpha.
- Every **INSTRUMENT** card: illustrated background at 20% alpha; **ADD INSTRUMENT** tile gets its own artwork (use 20% by default unless design system defines a deliberate contrasting add-card state).
- Every **TRANSFORMER** card, including any ADD TRANSFORMER tile: illustrated background at 20% alpha.
- **CONTROLLER** cards: compact width into discrete grid blocks/cards, instead of wide horizontal strips; background art at 20% alpha.
- **MOVEMENT** cards: true responsive CSS grid of compact tiles, each with a 20% alpha illustration.
- Avoid `opacity: .2` on the entire card because that fades text and controls. Put background artwork in `::before` or a separate layer with opacity, `pointer-events:none`; controls and labels remain fully opaque, keyboard accessible, high contrast.
- Keep industrial black/cream/yellow/purple/red palette, thin borders, sharp corners, responsive behavior and usable tap targets.
- Respect `prefers-reduced-motion` if any animation is added; decorative thumbnails need no alt text.

## Deterministic semi-random assignment
Use a seeded, stable hash based on **entity kind + persistent ID**, with category-specific curated image pools. Avoid `Math.random()` on render. The same saved patch should show the same thumbnails after refresh/reload; adding/removing another card must not reshuffle existing cards. Adjacent cards should avoid obvious repeats when feasible. Provide a fallback background if image fails.

## Integration
Inspect the real headless UI (`headless/web/index.html`, `headless/web/app.js`, `headless/web/style.css`) and the currently active UI branch before editing. Verify where the **MOVEMENT** and **ADD INSTRUMENT / ADD SMART SWITCH** UI are actually implemented; the current `main` headless page does not expose all of these names. Do not invent inert controls or pretend these modules already exist. If a target feature is on another development branch, document the target and implement there in a follow-up rather than silently creating fake UI.
Preserve all event handlers, routes, controller learn, patch state, active note status, command payloads and MIDI scheduling. CSS/presentation only except minimal stable tile-selection helper.


## Collapsible and reorderable TOP-LEVEL sections (corrected specification)
**Correction to earlier instructions:** The disclosure hierarchy is **NOT** nested inside MOVEMENT. The user wants **independent, top-level sections**, each collapsible as a whole, in a user-configurable order.

Illustrative layout (the user listed SNAPSHOTS twice; render **one SNAPSHOTS section** unless the real UI has two distinct, named features):

```text
▸ SNAPSHOTS
▸ SMART SWITCHES
▸ MOVEMENTS
▸ PHRASES
▸ INSTRUMENTS / TRANSFORMER CHAINS
▸ CONTROLLERS / EDITOR / TEST
▸ ... other real top-level sections
```

- Each row is a **top-level module group**, not a MOVEMENT child. Use a disclosure chevron on the group header to collapse/expand its **entire section content**. For example, `CONTROLLERS / EDITOR / TEST` is one top-level group label in this layout, **not** three nested disclosure sections.
- All actual top-level groups in the app should participate, including SNAPSHOTS where implemented. Do not fabricate missing modules. Keep existing card-level editors and controls functioning as they do today.
- **Drag and drop to reorder the top-level sections** using a visible drag handle distinct from the disclosure toggle. Preserve ordering across refresh/restarts via UI preferences/local storage or existing app persistence as appropriate. Do **not** rewrite the underlying engine module ordering or MIDI execution order.
- Provide an accessible keyboard alternative for reordering (e.g. Move up / Move down controls), and avoid drag interfering with buttons, sliders, text selection or module editing.
- Remember each group's collapsed/expanded state across telemetry rerenders and preferably page reload. Do not reset open editors or unsaved drafts.
- Collapsed group header retains title, useful count/status, and (if appropriate) a themed thumbnail. All controls and subcards remain in their real existing group when expanded.
- Group expansion/collapse/reordering must be presentation-only: **no changes to MIDI engine, scheduling, patch structure, playback or controller assignments**.
- Keep responsive grid layout **inside** the expanded groups for compact controller tiles and MOVEMENT tiles. This grid is not a nested disclosure hierarchy.
- Reuse actual existing DOM/action handlers and inspect current branches to find SNAPSHOTS/MOVEMENTS features before implementing. If a feature is absent on the PR base, record the limitation rather than introducing placeholder UI.
- Verify: every group can be toggled independently; reordered sequence survives refresh; all existing controls still work; keyboard reordering works; no duplicate SNAPSHOTS group.

## Acceptance / verification
- All supported card types have appropriately themed thumbnails with requested opacity; 90% ADD SMART SWITCH stands out.
- 32 source images sliced correctly and referenced by manifest, no missing files.
- Cards remain readable and clickable; controller and movement grids adapt to desktop/tablet/mobile.
- Deterministic selection persists across refresh and model rerenders.
- No new fake buttons or broken existing actions.
- Every **top-level group** can collapse/expand independently and can be reordered by drag and drop (with keyboard alternative); order and disclosure states persist without affecting MIDI or unsaved edits.
- Existing tests pass, plus tests for hash stability, image pool mapping and DOM class coverage where applicable.
- Before/after screenshots and short note identifying any unsupported targets or source-asset dependency.

## Work order for Codex
1. Inspect branch structure and actual implementation of each card type.
2. Retrieve/slice assets, prepare manifest.
3. Implement backgrounds and responsive grids on real components.
4. Add deterministic selection and fallback.
5. Test and attach screenshots.
6. Leave this PR as **draft** for design review; do not merge.

**Important:** The attached sheets are visual source of truth. Do not use the earlier GitHub Pages design preview as a replacement for real application logic.
