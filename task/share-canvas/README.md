# share-canvas

## Goal

Build a minimal modern website for invite-gated upload and download across normal network and company intranet.

## Scope

- Static React frontend with a canvas-like masonry feed.
- Invite roles: `upload` can list, download, upload; `download` can list and download only.
- Hugging Face Space FastAPI backend for file storage.
- Sites Worker backend for the first hosted version, using object storage and the same invite role model.
- Deployment notes for static host plus Space backend.

## Verification

- `npm run lint` passed.
- `npm run build` passed.
- `npm run build:sites` passed and produced:
  - `dist/server/index.js`
  - `dist/client/index.html`
  - `dist/.openai/hosting.json`
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
- Sites deployment preparation:
  - Created Sites project metadata in `.openai/hosting.json`.
  - Added same-origin Worker API for production upload/download.
  - Configured production `INVITES` and `MAX_UPLOAD_MB` through Sites runtime environment.
- Sites production deployment:
  - Deployed version 1 to `https://nospace-share-canvas.workspace-667865.chatgpt-team.site`.
  - Verified production `POST /api/session` for upload and download invites.
  - Verified production upload through `POST /api/assets`.
  - Verified production list and download with the read-only invite.
  - Verified production read-only upload rejection returns 403.
  - Public access could not be enabled because this workspace has Sites internet publishing disabled.
- Playwright screenshots captured for desktop and mobile:
  - `/tmp/nospace-desktop-v2.png`
  - `/tmp/nospace-mobile-v2.png`

## Mistakes

- See `mistake/pip-cache-json-truncation.md`.
- See `mistake/sites-public-publish-disabled.md`.
