# NoSpace

NoSpace is a tiny invite-gated sharing canvas for moving files and text between a normal network and a restricted intranet.

The frontend is a static Vite app deployed on GitHub Pages. The backend is a Hugging Face Docker Space, and durable files live in a private Hugging Face Dataset repo. Invite codes decide whether a visitor can upload/delete or only list and download.

## Why this shape

- Static frontend: simple to cache and cheap to host.
- Hugging Face Space backend: one small API surface for invite checks, file upload, metadata, and downloads.
- Hugging Face Dataset storage: files plus `index.json`, no Space persistent disk, database, or account system.
- Upload source: recorded from the requester IP that the Space can see through proxy/client headers.

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
INVITES='upload-demo:upload:Uploader,read-demo:download:Office' \
ALLOWED_ORIGINS='http://127.0.0.1:5173' \
DATASET_REPO_ID='mannycooper/nospace-data' \
HF_TOKEN='<token with dataset write access>' \
MAX_UPLOAD_MB=200 \
BAILIAN_OPENCODE_BASE_URL='<OpenAI-compatible endpoint>' \
BAILIAN_OPENCODE_API_KEY='<GLM credential>' \
BAILIAN_OPENCODE_MODEL='glm-5.2' \
../.venv/bin/uvicorn app:app --host 127.0.0.1 --port 7860
```

Run the frontend:

```bash
VITE_API_BASE_URL=http://127.0.0.1:7860 \
VITE_DEFAULT_INVITE=upload-demo \
VITE_MAX_UPLOAD_MB=200 \
npm run dev
```

Open `http://127.0.0.1:5173`.

## Deploy

Current public frontend:

```text
https://omoyx.github.io/nospace/
```

The root GitHub Pages URL also redirects there:

```text
https://omoyx.github.io/
```

Current backend:

```text
https://mannycooper-nospace-storage.hf.space
```

When GLM 5.2 credentials are configured on the backend, every uploaded filename is optimized before the asset is added to the feed. The original upload name remains in metadata and appears as a muted second line, while the generated name is used for primary display and downloads. Model failure never blocks an upload; an objective MIME type suffix provides a distinct fallback name.

For GitHub Pages:

```bash
npm run build
```

The production frontend points at the Hugging Face Space URL through `VITE_API_BASE_URL`. See [docs/deployment.md](docs/deployment.md).
