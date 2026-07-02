# share-canvas

## Goal

Build a minimal modern website for invite-gated upload and download across normal network and company intranet.

## Scope

- Static React frontend with a canvas-like masonry feed.
- Invite roles: `upload` can list, download, upload; `download` can list and download only.
- Hugging Face Space FastAPI backend for file storage.
- Hugging Face Space backend for the first public hosted version.
- Deployment notes for GitHub Pages plus Space backend.

## Verification

- `npm run lint` passed.
- `npm run build` passed.
- `python3 -m py_compile space/app.py` passed.
- UI simplification pass:
  - Removed decorative ghost cards and board summary footer.
  - Removed file-type label from card headers.
  - Moved filename and date into one small gray metadata row with ellipsis.
  - Changed cards to large rounded corners.
  - Changed text files to preview text content directly.
  - Captured desktop/mobile screenshots:
    - `/tmp/nospace-minimal-desktop.png`
    - `/tmp/nospace-minimal-mobile.png`
- Backend local API passed:
  - `POST /api/session` accepts upload and download invites.
  - `POST /api/assets` accepts `upload-demo`.
  - `GET /api/assets` works with `read-demo`.
  - `GET /files/{id}/download?invite=read-demo` returns uploaded content.
  - `POST /api/assets` rejects `read-demo` with 403.
- Hugging Face Space production backend:
  - Created `mannycooper/nospace-storage`.
  - Configured production `INVITES`, `ALLOWED_ORIGINS`, `APP_BASE_URL`, and `MAX_UPLOAD_MB`.
  - Uploaded Docker Space backend.
  - Verified Space health at `https://mannycooper-nospace-storage.hf.space/`.
  - Verified production upload with upload invite.
  - Verified production list and download with read-only invite.
  - Verified production read-only upload rejection returns 403.
- GitHub Pages frontend preparation:
  - Created and pushed `https://github.com/omoyx/nospace`.
  - Added GitHub Actions Pages workflow.
  - Built with `GITHUB_PAGES=true` and `VITE_API_BASE_URL=https://mannycooper-nospace-storage.hf.space`.
  - Removed Sites-only metadata and worker build path from the official release path.
  - Enabled GitHub Pages workflow deployment.
  - Verified public frontend at `https://omoyx.github.io/nospace/`.
  - Verified deployed HTML loads `/nospace/assets/...`.
  - Verified built frontend references `mannycooper-nospace-storage.hf.space`.
  - Verified CORS preflight from `https://omoyx.github.io` for session and upload endpoints.
  - Captured public frontend screenshot at `/tmp/nospace-github-pages-public.png`.
- GitHub Pages root redirect:
  - Created `https://github.com/omoyx/omoyx.github.io`.
  - Added root `index.html` and `404.html` redirecting to `/nospace/`.
  - Verified `https://omoyx.github.io/` returns 200.
- Source label rename:
  - Changed upload source display from `Anzi` to `IP`.
  - Updated production Hugging Face Space `INVITES` secret so new uploads use `IP`.
  - Added frontend compatibility so existing stored `Anzi` metadata displays as `IP`.
  - Verified `POST /api/session` returns `{"role":"upload","name":"IP"}` for the upload invite.
- Widescreen and persisted invite session:
  - Expanded the desktop shell from 1180px to a widescreen layout up to 1920px.
  - Increased masonry columns to 5 by default and 6 on very wide screens.
  - Stored the successful invite in `localStorage` under `nospace:invite`.
  - Revalidates the saved invite on page load so refresh keeps the login state.
  - Invalid saved invites are removed from local storage.
  - Captured wide and mobile screenshots:
    - `/tmp/nospace-wide.png`
    - `/tmp/nospace-mobile-persist.png`
  - `npm run lint` passed after the change.
  - `GITHUB_PAGES=true VITE_API_BASE_URL=https://mannycooper-nospace-storage.hf.space npm run build` passed after the change.
- Playwright screenshots captured for desktop and mobile:
  - `/tmp/nospace-desktop-v2.png`
  - `/tmp/nospace-mobile-v2.png`

## Mistakes

- See `mistake/pip-cache-json-truncation.md`.
- See `mistake/sites-public-publish-disabled.md`.
