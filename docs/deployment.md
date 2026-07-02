# NoSpace deployment

## First online version

- Frontend: GitHub Pages.
- Backend/storage: Hugging Face Docker Space.
- Data: files under `/data/nospace/files` plus `/data/nospace/index.json`.

Live URLs:

```text
Frontend: https://omoyx.github.io/nospace/
Backend:  https://mannycooper-nospace-storage.hf.space
```

This keeps the project simple: no database, no user accounts, no server-side render path.

## Hugging Face Space

Create a Docker Space from `space/`.

Set Space variables:

```text
INVITES=upload-code:upload:IP,read-code:download:Office
ALLOWED_ORIGINS=https://omoyx.github.io,http://127.0.0.1:5173
APP_BASE_URL=https://mannycooper-nospace-storage.hf.space
MAX_UPLOAD_MB=80
```

Use paid persistent storage if uploads must survive Space restarts. The app stores files under `/data/nospace/files` and metadata in `/data/nospace/index.json`.

## GitHub Pages

Build with:

```text
VITE_API_BASE_URL=https://mannycooper-nospace-storage.hf.space
VITE_DEFAULT_INVITE=
```

Then publish `dist/` through GitHub Pages.

The current GitHub Actions workflow publishes on pushes to `main`.

## Network note

Mainland access can change. Test with the actual corporate network before relying on the site. If GitHub Pages or Hugging Face is blocked by that network, the frontend can stay unchanged while the backend moves to a small VPS, Cloudflare Worker + R2, or any FastAPI host with a writable disk.

## Local settings

Create `.env.local` for local development:

```text
VITE_API_BASE_URL=http://127.0.0.1:7860
VITE_DEFAULT_INVITE=upload-demo
```

## Local run

Terminal 1:

```bash
cd space
INVITES='upload-demo:upload:IP,read-demo:download:Office' \
ALLOWED_ORIGINS='http://127.0.0.1:5173' \
NOSPACE_DATA_DIR='./storage' \
uvicorn app:app --host 127.0.0.1 --port 7860 --reload
```

Terminal 2:

```bash
npm install
npm run dev
```

Open `http://127.0.0.1:5173`.
