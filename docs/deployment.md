# NoSpace deployment

## First online version

- Frontend: GitHub Pages.
- Backend/API: Hugging Face Docker Space.
- Storage: private Hugging Face Dataset.
- Data: files under `files/` plus `index.json` in the Dataset repo.

Live URLs:

```text
Frontend: https://omoyx.github.io/nospace/
Backend:  https://mannycooper-nospace-storage.hf.space
Dataset:  mannycooper/nospace-data
```

This keeps the project simple: no database, no user accounts, no server-side render path.

## Hugging Face Space

Create a Docker Space from `space/`.

Set Space variables:

```text
INVITES=upload-code:upload:Uploader,read-code:download:Office
ALLOWED_ORIGINS=https://omoyx.github.io,http://127.0.0.1:5173
APP_BASE_URL=https://mannycooper-nospace-storage.hf.space
DATASET_REPO_ID=mannycooper/nospace-data
MAX_UPLOAD_MB=200
BAILIAN_OPENCODE_BASE_URL=<OpenAI-compatible GLM endpoint>
BAILIAN_OPENCODE_MODEL=glm-5.2
```

Production invite values are access credentials. Keep the real values in the Space `INVITES` secret/variable and do not commit them to the repository.

For `upload` invites, the configured display name is not shown on uploaded items. The backend records the requester IP visible to the Space from `cf-connecting-ip`, `x-real-ip`, `x-forwarded-for`, `forwarded`, or the direct client connection.

Set Space secrets:

```text
HF_TOKEN=<token with write access to the private Dataset repo>
BAILIAN_OPENCODE_API_KEY=<GLM credential>
```

`BAILIAN_OPENCODE_API_KEY` must remain a Space secret. The filename renamer sends every uploaded filename, its MIME type, extension, and local encoding-repair candidates to GLM 5.2. File bytes and notes are not sent to the model. If the model is unavailable, uploads continue: mojibake uses safe deterministic encoding repair when possible, and other names receive an objective MIME type suffix.

The Dataset repo should be private so visitors cannot bypass the invite API and read files directly from the Hub.

## GitHub Pages

Build with:

```text
VITE_API_BASE_URL=https://mannycooper-nospace-storage.hf.space
VITE_DEFAULT_INVITE=
VITE_MAX_UPLOAD_MB=200
```

Then publish `dist/` through GitHub Pages.

The current GitHub Actions workflow publishes on pushes to `main`.

Keep frontend `VITE_MAX_UPLOAD_MB` aligned with the Space `MAX_UPLOAD_MB` variable. The frontend uses it to reject oversized files before upload, while the backend remains the final enforcement point.

## Network note

Mainland access can change. Test with the actual corporate network before relying on the site. If GitHub Pages or Hugging Face is blocked by that network, the frontend can stay unchanged while the backend moves to a small VPS, Cloudflare Worker + R2, or any FastAPI host with a writable disk.

## Local settings

Create `.env.local` for local development:

```text
VITE_API_BASE_URL=http://127.0.0.1:7860
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
