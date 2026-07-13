# CSS columns can hide cards under zoom

## Symptom

At wide window sizes or browser zoom levels, the upload tile stayed visible but existing file cards appeared to disappear from the canvas.

## Cause

The canvas used CSS multi-column layout (`column-count`) plus visual `transform` offsets for cards. Multi-column balancing is fragile for interactive card grids, especially when the viewport, zoom level, or item heights change. Visual transforms also do not reserve layout space, so cards can be clipped or pushed into surprising positions.

## Fix

Do not return to CSS multi-column layout. Use one of these real-layout approaches:

- For a regular aligned grid, use `display: grid` with responsive `auto-fill` columns.
- For a tightly packed masonry feed, measure each card and place it in the current shortest column.
- Recalculate the masonry positions with `ResizeObserver` when the container or a card changes size.
- Set the masonry container's explicit height to the tallest column so following content and board bounds remain correct.
- Keep positioned cards in normal DOM order for reading and keyboard navigation.

The earlier problem came from column balancing plus untracked decorative offsets. A measured masonry layout avoids column balancing and treats every visual position as part of a single explicit layout calculation.

## Check

For future layout changes, verify at least:

- wide desktop around `2048x962`
- zoom-like viewport around `1365x641`
- narrow mobile around `559x918`
- mixed short, text, and naturally sized image cards
- card insertion/removal and image-load reflow
