# NoSpace deployment

## First online version

- Host: Sites.
- Runtime API: same-origin Worker endpoints under `/api/*` and `/files/*`.
- Data: object storage via the `FILES` binding, with uploaded bytes plus `__nospace_index.json`.

This keeps the project simple: no database, no user accounts, no server-side render path.

Set production runtime variables:

```text
INVITES=upload-code:upload:Anzi,read-code:download:Office
MAX_UPLOAD_MB=80
```

Build the deployable artifact:

```bash
npm run build:sites
```

## Hugging Face Space option

The `space/` folder is still a Docker Space backend if you prefer keeping storage on Hugging Face.

## Network note

Mainland access can change. Test with the actual corporate network before relying on the site. If GitHub Pages or Hugging Face is blocked by that network, the frontend can stay unchanged while the backend moves to a small VPS, Cloudflare Worker + R2, or any FastAPI host with a writable disk.

## Hugging Face Space settings

Create a Docker Space and copy everything in `space/` into it.

Set these Space variables:

```text
INVITES=upload-demo:upload:Anzi,read-demo:download:Office
ALLOWED_ORIGINS=https://yourname.github.io,http://127.0.0.1:5173
APP_BASE_URL=https://YOUR_USERNAME-YOUR_SPACE_NAME.hf.space
MAX_UPLOAD_MB=80
```

Use paid persistent storage if uploads must survive Space restarts. The app stores files under `/data/nospace/files` and metadata in `/data/nospace/index.json`.

## Frontend settings

Create `.env.local` for local development:

```text
VITE_API_BASE_URL=http://127.0.0.1:7860
VITE_DEFAULT_INVITE=upload-demo
```

For production static hosting:

```text
VITE_API_BASE_URL=https://YOUR_USERNAME-YOUR_SPACE_NAME.hf.space
```

Build:

```bash
npm run build
```

Publish the `dist/` directory to the static host.

For GitHub Pages, a common path is to set GitHub Actions to build with `npm run build` and publish `dist/`.

## Local run

Terminal 1:

```bash
cd space
INVITES='upload-demo:upload:Anzi,read-demo:download:Office' \
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
