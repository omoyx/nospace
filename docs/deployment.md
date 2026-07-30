# NoSpace deployment

## Current production

- Frontend: GitHub Pages.
- Backend/API: the Shanghai Huawei ECS at a trusted bare-IP HTTPS endpoint.
- Compatibility API: the Hugging Face Space `/compat` path streams requests to the Huawei ECS for enterprise networks that reject the IP certificate.
- Primary storage: the ECS's existing `/mnt/disk1/nospace-storage` filesystem.
- Control plane: the Hugging Face Docker Space validates existing invites and performs GLM filename generation.
- Rollback snapshot: the private Hugging Face Dataset contains the data present at cutover, but is not a continuous mirror of later Huawei uploads.

Live URLs:

```text
Frontend: https://omoyx.github.io/nospace/
Backend:  https://113.44.66.120
Control:  https://mannycooper-nospace-storage.hf.space
Compat:   https://mannycooper-nospace-storage.hf.space/compat
Snapshot: mannycooper/nospace-data
```

Upload, inline-read, and download bytes travel directly between the browser and the Huawei ECS. They do not pass through Hugging Face. The Huawei API sends only invite-validation JSON and filename/MIME/OCR metadata to the control plane; it does not send file bytes or notes.

If the browser cannot establish TLS to the bare IP, invite verification falls back to the Space `/compat` path. Only that compatibility session's bytes pass through Hugging Face; normal sessions continue to use the Shanghai direct path.

## Huawei ECS

The two systemd services are:

```text
nospace-api.service
nospace-caddy.service
```

Caddy obtains and renews a Let's Encrypt `shortlived` certificate directly for `113.44.66.120`. `default_sni` is required because some bare-IP TLS clients omit SNI.

The application uses only the server's existing data disk:

```text
Application: /mnt/disk1/nospace-app
Files:       /mnt/disk1/nospace-storage/files
Index:       /mnt/disk1/nospace-storage/index.json
Caddy data:  /mnt/disk1/nospace-caddy
```

Uploads are refused with HTTP 507 if NoSpace would exceed 40 GiB or if the data disk would fall below 150 GiB free. No additional EVS disk is required.

## Hugging Face Space

The existing Space remains online as the authorization and smart-filename control plane. It also preserves the old Dataset-backed implementation as a rollback path.

Set Space variables:

```text
INVITES=upload-code:upload:Uploader,read-code:download:Office
ALLOWED_ORIGINS=https://omoyx.github.io,http://127.0.0.1:5173
APP_BASE_URL=https://mannycooper-nospace-storage.hf.space
COMPAT_UPSTREAM_URL=https://113.44.66.120
DATASET_REPO_ID=mannycooper/nospace-data
MAX_UPLOAD_MB=200
BAILIAN_OPENCODE_BASE_URL=<OpenAI-compatible GLM endpoint>
BAILIAN_OPENCODE_MODEL=glm-5.2
IMAGE_CLASSIFICATION_MODEL=google/mobilenet_v2_1.0_224
```

Production invite values are access credentials. Keep the real values in the Space `INVITES` secret/variable and do not commit them to the repository.

For `upload` invites, the configured display name is not shown on uploaded items. The backend records the requester IP visible to the Space from `cf-connecting-ip`, `x-real-ip`, `x-forwarded-for`, `forwarded`, or the direct client connection.

Set Space secrets:

```text
HF_TOKEN=<token with write access to the private Dataset repo>
BAILIAN_OPENCODE_API_KEY=<GLM credential>
INTERNAL_API_KEY=<shared random control-plane credential>
```

`BAILIAN_OPENCODE_API_KEY` and `INTERNAL_API_KEY` must remain secrets. Huawei calls the protected `/internal/smart-filename` endpoint with filename, MIME type, and optional local OCR evidence. File bytes and notes are never sent. If the model is unavailable, uploads continue with a safe deterministic fallback name.

Supported raster images are durably stored before a best-effort background task runs local Chinese/English Tesseract on Huawei. OCR or naming failure never fails or blocks the durable upload response. The production Huawei path does not send image bytes to Hugging Face Inference.

The Dataset repo remains private so visitors cannot bypass the invite API and read the rollback snapshot directly from the Hub.

## GitHub Pages

Build with:

```text
VITE_API_BASE_URL=https://113.44.66.120
VITE_API_FALLBACK_URL=https://mannycooper-nospace-storage.hf.space/compat
VITE_DEFAULT_INVITE=
VITE_MAX_UPLOAD_MB=200
```

Then publish `dist/` through GitHub Pages.

The current GitHub Actions workflow publishes on pushes to `main`.

Keep frontend `VITE_MAX_UPLOAD_MB` aligned with the Huawei API's `MAX_UPLOAD_MB`. The frontend uses it to reject oversized files before upload, while the backend remains the final enforcement point.

## Network note

The normal Shanghai data path avoids routing file bytes through Hugging Face. GitHub Pages still serves the static frontend, and invite/name control requests still depend on the HF Space. Company networks that reject the short-lived IP certificate use the streaming compatibility path. Caddy must remain running so the IP certificate renews automatically.

## Local settings

Create `.env.local` for local development:

```text
VITE_API_BASE_URL=http://127.0.0.1:7860
VITE_API_FALLBACK_URL=
VITE_DEFAULT_INVITE=upload-demo
VITE_MAX_UPLOAD_MB=200
```

## Local run

Terminal 1:

```bash
cd space
INVITES='upload-demo:upload:Uploader,read-demo:download:Office' \
ALLOWED_ORIGINS='http://127.0.0.1:5173' \
DATASET_REPO_ID='mannycooper/nospace-data' \
HF_TOKEN='<token with dataset write access>' \
uvicorn app:app --host 127.0.0.1 --port 7860 --reload
```

Terminal 2:

```bash
npm install
npm run dev
```

Open `http://127.0.0.1:5173`.
