# download-original-name

## Goal

- Save downloaded files with the original upload filename.
- Preserve the uploaded file bytes, Dataset path, and original filename metadata.

## Implementation

- Set the frontend anchor `download` attribute to `originalName`.
- Keep the backend `Content-Disposition` filename sourced only from `originalName`; `displayName` remains UI-only.
- Do not rename or rewrite the stored Dataset object.

## Verification

- Backend test verifies an asset with a smart display name still emits its original name in `Content-Disposition`, while the source path and exact original bytes remain untouched.
- Backend test verifies legacy assets also use `originalName`.
- `.venv/bin/python -W ignore::DeprecationWarning -W error::RuntimeWarning -m unittest space/test_app.py -v` passed with 24 tests.
- `npm run lint` passed.
- Production frontend build passed with the configured Space API and 200 MB upload limit.
- `git diff --check` passed.

## Production

- Pushed implementation commit `bee6b75` to `main`.
- GitHub Pages workflow `29384823740` completed successfully.
- Verified the public page loads the new `index--ozlxqME.js` bundle and that it contains the dynamic download filename property.
- Superseded: the Space download endpoint must emit `originalName` through `Content-Disposition`; `displayName` is UI-only.
- A real authenticated download was not performed because production invite values remain intentionally absent from the repository and local environment.
