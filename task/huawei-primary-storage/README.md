# huawei-primary-storage

## Goal

- Serve upload and download bytes directly from the Shanghai Huawei ECS over trusted IP HTTPS.
- Store files under the existing `/mnt/disk1` capacity without buying another EVS disk.
- Preserve current invite codes and GLM filename behavior without copying non-readable HF Space secrets to the shared server.
- Keep the existing HF deployment available as a control-plane and rollback path during migration.

## Architecture

- Browser file data: GitHub Pages -> `https://113.44.66.120` -> Caddy -> Huawei FastAPI -> local filesystem.
- Invite validation: Huawei FastAPI -> existing HF Space `/api/session`, cached by SHA-256 invite digest.
- Smart filename metadata: Huawei FastAPI -> protected HF Space internal endpoint. File bytes and notes are never sent.
- Image OCR: best-effort local Tesseract background work on Huawei.

## Capacity policy

- Storage root: `/mnt/disk1/nospace-storage`.
- Application cap: 40 GiB.
- Reserved filesystem free space: 150 GiB.
- Uploads fail with HTTP 507 before a write would cross either boundary.

## Verification

- `.venv/bin/python -m py_compile space/app.py space/test_app.py` passed.
- `.venv/bin/python -W ignore::DeprecationWarning -W error::RuntimeWarning -m unittest space/test_app.py -v` passed with 33 tests.
- Local-storage tests cover atomic file/index writes, path traversal rejection, capacity rejection, and migrated Dataset paths.
- Upstream-control-plane tests cover authorization caching by invite digest, invalid invites, stale authorization during an outage, and metadata-only filename naming.
- `npm run lint` passed.
- `GITHUB_PAGES=true VITE_API_BASE_URL=https://113.44.66.120 VITE_DEFAULT_INVITE= VITE_MAX_UPLOAD_MB=200 npm run build` passed.
- `docker build -t nospace-storage-huawei:test space` passed.
- The production container imported the app in local mode and reported `storage: local-filesystem`.
- `git diff --check` passed.

## Production

Pending.

## Recurrence

- See `mistake/mainland-hostname-filtering.md`.
