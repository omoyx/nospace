# minimal-gray-visual

## Goal

Remove decorative background elements and green accents, while keeping the large rounded card style.
Record the release requirement so future key changes are verified online, not only locally.

## Verification

- `npm run lint` passed.
- `GITHUB_PAGES=true VITE_API_BASE_URL=https://mannycooper-nospace-storage.hf.space npm run build` passed.
- Verified the logged-in canvas with a local mock API and Playwright screenshots:
  - `/tmp/nospace-minimal-gray-desktop.png`
  - `/tmp/nospace-minimal-gray-mobile.png`
- `rg -n "mint|acid|cyan|0, 232|c7ff|radial-gradient|#effaf|#e7eb|#e8eb|green" src/styles.css` returned no matches.
- `git status --short` showed:
  - `M src/styles.css`
  - `M task/share-canvas/README.md`
  - `?? task/minimal-gray-visual/`
- Updated `AGENTS.md` to require publishing key changes to the official online environment and verifying the public URL.

## Mistakes

- No new recurring issue found; no new `mistake/` entry needed.
