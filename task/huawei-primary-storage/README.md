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

Cut over on 2026-07-29 (Asia/Shanghai).

### Deployments

- Huawei backend source: `a0157b8` (`Add Huawei local storage backend`).
- HF control-plane source: `c145fccf66718f0d598a5f53002cdfbb2f794bb7`.
- GitHub Pages cutover source: `eb5f0f3f0788d1c85e2b1ca051ba038229805b35`.
- GitHub Pages workflow: <https://github.com/omoyx/nospace/actions/runs/30434283328>.
- Public frontend: <https://omoyx.github.io/nospace/>.
- Public API: <https://113.44.66.120/>.

Both `nospace-api.service` and `nospace-caddy.service` are enabled and active. The API binds only to `127.0.0.1:7860`; Caddy is the public entry point.

### Data migration

The final pre-cutover download of private Dataset `mannycooper/nospace-data` produced:

- 21 asset files plus `index.json`.
- 21 index entries, with no missing or unindexed asset files.
- 121,390,310 total bytes including the index.
- Manifest SHA-256: `6fd335adcbb95482b72589b71ff9f6553d3b7fece8f82362d01ce76668cc4b79`.

The same file count, byte count, index count, and manifest digest were recomputed as user `nospace` under `/mnt/disk1/nospace-storage`. Directories are mode 750 and files are mode 640.

### TLS

Caddy 2.11.4 obtained a production Let's Encrypt `shortlived` IP certificate:

- SAN: IP address `113.44.66.120`.
- Issuer: `C=US, O=Let's Encrypt, CN=YE1`.
- Valid from: 2026-07-29 06:53:43 UTC.
- Valid until: 2026-08-04 22:53:42 UTC.
- Strict client verification: passed.
- HTTP redirect: `308` to `https://113.44.66.120/`.

Five strict public HTTPS requests returned HTTP 200. TLS handshake time was 0.080-0.163 seconds and total time was 0.118-0.196 seconds.

### End-to-end verification

`scripts/verify_huawei_storage.py` ran against the public IP with a temporary local invite:

- Invite session returned the upload role.
- GitHub Pages origin CORS preflight passed.
- The protected HF smart-filename control plane returned `glm-5.2`.
- Upload, list, inline read, download, byte SHA-256 comparison, delete, and post-delete count restoration passed.
- The temporary asset was deleted.
- The temporary local invite was removed and the API was restarted.
- An invalid invite still returned 401 through the HF authorization control plane.

After cutover, the public frontend returned HTTP 200 with a `last-modified` time after the successful Pages deployment. The workflow log confirms the deployed build used `VITE_API_BASE_URL=https://113.44.66.120`.

### Rollback

1. Change the Pages workflow API URL back to `https://mannycooper-nospace-storage.hf.space`.
2. Deploy that frontend revision and verify the public page.
3. Only then stop the Huawei services if necessary.

The HF Dataset is an exact cutover snapshot, not a continuous mirror. Before rolling back after new Huawei uploads exist, export those newer files and index entries or they will not appear through the old HF backend.

### Remaining backup work

New Huawei uploads currently have capacity protection and atomic local writes, but no ongoing off-server byte backup. Adding a scheduled encrypted backup or asynchronous mirror is a separate follow-up. It must not put HF in the browser upload/download data path.

## Recurrence

- See `mistake/mainland-hostname-filtering.md`.
