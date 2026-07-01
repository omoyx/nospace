# NoSpace

NoSpace is a tiny invite-gated sharing canvas for moving files and text between a normal network and a restricted intranet.

The frontend is a static Vite app. Production on Sites uses a tiny Worker API plus object storage; the `space/` folder remains a Hugging Face Space backend option. Invite codes decide whether a visitor can upload or only list and download.

## Why this shape

- Static frontend: simple to cache and cheap to host.
- Sites Worker backend for the first online version: one small API surface for invite checks, file upload, metadata, and downloads.
- Storage model: files plus `index.json` in object storage, no database or account system.

## Local development

Install frontend dependencies:

```bash
npm install
```

Install backend dependencies:

```bash
python3 -m venv .venv
.venv/bin/pip install --no-cache-dir -r space/requirements.txt
```

Run the Space backend:

```bash
cd space
INVITES='upload-demo:upload:Anzi,read-demo:download:Office' \
ALLOWED_ORIGINS='http://127.0.0.1:5173' \
NOSPACE_DATA_DIR='./storage' \
../.venv/bin/uvicorn app:app --host 127.0.0.1 --port 7860
```

Run the frontend:

```bash
VITE_API_BASE_URL=http://127.0.0.1:7860 \
VITE_DEFAULT_INVITE=upload-demo \
npm run dev
```

Open `http://127.0.0.1:5173`.

## Deploy

For Sites:

```bash
npm run build:sites
```

The production frontend calls same-origin `/api/*` by default. Set the `INVITES` and `MAX_UPLOAD_MB` runtime variables in the host.

The Hugging Face Space backend is still available by copying `space/` into a Docker Space. See [docs/deployment.md](docs/deployment.md).
