# Signature lettering

`mbmf-block.woff2` is a small uppercase-only subset of Bungee Regular by The Bungee
Project Authors, distributed under SIL OFL 1.1 (included in OFL.txt). The derived
font is renamed MBMF Block. No proprietary wallet lettering or texture is copied.
It is served locally; no CDN, external font request or runtime build is required.

Source: https://github.com/google/fonts/blob/main/ofl/bungee/Bungee-Regular.ttf
Source SHA-256: c4f5361ce120af3e6b9156d0bf379fa19cda2ea0cd18ac01fd99596c6bf66e3f

Reproduce using FontTools and Brotli in a development environment: subset the text
`MIDI BAD MOTHERFUCKER`, enable WOFF2 flavor/desubroutinization, and rename family,
full and PostScript names to MBMF Block / MBMFBlock-Regular. Keep the copyright and
license metadata. The subset is for the fixed signature only; application controls
use system fonts. These build tools are not application runtime dependencies.
