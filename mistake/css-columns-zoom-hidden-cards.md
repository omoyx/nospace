# CSS columns can hide cards under zoom

## Symptom

At wide window sizes or browser zoom levels, the upload tile stayed visible but existing file cards appeared to disappear from the canvas.

## Cause

The canvas used CSS multi-column layout (`column-count`) plus visual `transform` offsets for cards. Multi-column balancing is fragile for interactive card grids, especially when the viewport, zoom level, or item heights change. Visual transforms also do not reserve layout space, so cards can be clipped or pushed into surprising positions.

## Fix

Use a real responsive grid for this app's card canvas:

- `display: grid`
- `grid-template-columns: repeat(auto-fill, minmax(min(100%, var(--tile-min)), 1fr))`
- normal block cards with no transform-based staggering
- visible board overflow when the content grows

## Check

For future layout changes, verify at least:

- wide desktop around `2048x962`
- zoom-like viewport around `1365x641`
- narrow mobile around `559x918`
