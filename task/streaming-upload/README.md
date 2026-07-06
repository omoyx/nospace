# streaming-upload

## Goal

Avoid buffering the full upload in Space memory and raise the practical upload cap to 200 MB while keeping invite checks, progress UI, Dataset storage, and public deployment intact.

## Verification

- Monkeypatched backend script passed:
  - `spool_upload_to_temp_file` writes chunks to a temp file and returns the expected size/hash.
  - oversize chunked input raises `413` and leaves no `nospace-upload-*.tmp` file behind.
  - `create_asset` passes a temp file `Path` to `hf_api.upload_file`, records the saved item, closes the uploaded file, and removes the temp file after returning.
- `npm run lint` passed.
- `GITHUB_PAGES=true VITE_API_BASE_URL=https://mannycooper-nospace-storage.hf.space VITE_MAX_UPLOAD_MB=200 npm run build` passed.
- `.venv/bin/python -m py_compile space/app.py` passed.
- Direct middleware check with a synthetic `/api/assets` request whose `Content-Length` is larger than `MAX_UPLOAD_MB` plus multipart allowance returned:
  - `413`
  - `{"detail":"文件超过 200 MB"}`
- `rg -n "单个文件不超过|超过 .* MB 上限|文件超过 200 MB|jf=200|fi\\*1024\\*1024" dist src space docs README.md .github/workflows task mistake -g '!node_modules/**'` confirmed the built frontend and docs include the 200 MB limit.
- `rg -n "await file\\.read\\(\\)|BytesIO\\(content\\)|hashlib\\.sha256\\(content" space/app.py src/api.ts` returned no matches.
- `git diff --check` passed.
- `git status --short` before commit showed only the streaming upload code, upload limit config/docs, task note, and mistake note modified/added.

## Mistakes

- Added `mistake/upload-memory-buffering.md`.
