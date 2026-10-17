# Codex implementation brief: illustrated module tiles

## Goal
Bring the ANONYMALZ/MBMF punk-animal art direction into the **real** MBMF UI, using the **two 4×4 contact sheets attached to the originating ChatGPT conversation** (32 rectangular illustrations). This is NOT a new mockup. Preserve existing engine APIs, events, IDs, MIDI behavior and edit interactions.

## Art asset preparation
1. Obtain the two source contact sheets from the user-provided attachments. They are **not yet committed to this branch**; do not silently substitute AI images or unrelated artwork. If unavailable in the Codex environment, leave an explicit asset dependency and stop before claiming visual completion.
2. Slice each 4-column × 4-row sheet into 16 separate thumbnails, crop precisely at the internal tile borders and exclude gutters. Keep aspect ratios, artwork and palette; do not regenerate or modify the drawings. Export optimized WebP/PNG assets into `headless/web/assets/tiles/`, plus a machine-readable manifest with descriptive, stable IDs, source sheet and source row/column. Confirm 32 assets, dimensions, sizes, no black gutter artifacts.
3. Choose semantically appropriate sets: **PHRASE** = music/performance/recording; **INSTRUMENT** = keyboards, guitar, bass, synth and instrument-playing animals; **TRANSFORMER** = cables, effects, machines and modular synthesis; **CONTROLLER** = switches, knobs, patch bays; **MOVEMENT** = motion, electricity, explosive gestures, sound-wave energy; **SMART SWITCH** = buttons, paws, triggers and expressive animals. Allow reuse across categories, but vary thumbnails across adjacent cards.

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

## Acceptance / verification
- All supported card types have appropriately themed thumbnails with requested opacity; 90% ADD SMART SWITCH stands out.
- 32 source images sliced correctly and referenced by manifest, no missing files.
- Cards remain readable and clickable; controller and movement grids adapt to desktop/tablet/mobile.
- Deterministic selection persists across refresh and model rerenders.
- No new fake buttons or broken existing actions.
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
