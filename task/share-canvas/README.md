# share-canvas

## Goal

Build a minimal modern website for invite-gated upload and download across normal network and company intranet.

## Scope

- Static React frontend with a canvas-like masonry feed.
- Invite roles: `upload` can list, download, upload; `download` can list and download only.
- Hugging Face Space FastAPI backend for file storage.
- Deployment notes for static host plus Space backend.

## Verification

- `npm run lint` passed.
- `npm run build` passed.
- `python3 -m py_compile space/app.py` passed.
- Backend local API passed:
  - `POST /api/session` accepts upload and download invites.
  - `POST /api/assets` accepts `upload-demo`.
  - `GET /api/assets` works with `read-demo`.
  - `GET /files/{id}/download?invite=read-demo` returns uploaded content.
  - `POST /api/assets` rejects `read-demo` with 403.
- Playwright screenshots captured for desktop and mobile:
  - `/tmp/nospace-desktop-v2.png`
  - `/tmp/nospace-mobile-v2.png`

## Mistakes

- See `mistake/pip-cache-json-truncation.md`.
