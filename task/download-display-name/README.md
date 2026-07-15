# download-display-name

## Goal

- Save downloaded files with the smart display name shown in the UI.
- Preserve the uploaded file bytes, Dataset path, and original filename metadata.

## Implementation

- Set the frontend anchor `download` attribute to the asset display name.
- Keep the backend `Content-Disposition` filename sourced from `displayName`, with `originalName` only as a legacy fallback.
- Do not rename or rewrite the stored Dataset object.

## Verification

- Backend test verifies a Unicode smart name is emitted in `Content-Disposition` while the same source path and exact original bytes remain untouched.
- Backend test verifies legacy assets without `displayName` fall back to `originalName`.
- `.venv/bin/python -W ignore::DeprecationWarning -W error::RuntimeWarning -m unittest space/test_app.py -v` passed with 24 tests.
- `npm run lint` passed.
- Production frontend build passed with the configured Space API and 200 MB upload limit.
- `git diff --check` passed.

## Production

- Pushed implementation commit `bee6b75` to `main`.
- GitHub Pages workflow `29384823740` completed successfully.
- Verified the public page loads the new `index--ozlxqME.js` bundle and that it contains the dynamic download filename property.
- The Space download endpoint already emits `displayName` through `Content-Disposition`; no Dataset object, stored path, or original bytes were changed or redeployed.
- A real authenticated download was not performed because production invite values remain intentionally absent from the repository and local environment.
