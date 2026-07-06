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
- Committed local milestone as `3acbb4a Stream uploads through temporary files`.
- Pushed `main` to GitHub.
- Updated Hugging Face Space variable `MAX_UPLOAD_MB` from `80` to `200`.
- Uploaded `space/` to Hugging Face Space `mannycooper/nospace-storage`.
- GitHub Pages workflow run `28791399956` initially failed in the deploy step with `Deployment failed, try again later`; rerunning the failed job succeeded.
- Verified public frontend `https://omoyx.github.io/nospace/` returned `HTTP/2 200` and referenced:
  - `/nospace/assets/index-Npk8aTEu.js`
  - `/nospace/assets/index-dm-BHXki.css`
- Verified public JS `https://omoyx.github.io/nospace/assets/index-Npk8aTEu.js` contains:
  - `jf=200`
  - `fi*1024*1024`
  - `超过 ${fi} MB 上限`
  - `单个文件不超过 ${fi} MB`
- Verified Space `MAX_UPLOAD_MB` variable is `200`.
- Verified Space repo SHA and runtime SHA both equal `dd0644f670747685f0686eccf9b3cc8d41f7c8d1`.
- Verified Space runtime stage is `RUNNING` and domain stage is `READY`.
- Verified the deployed Space `app.py` at that SHA contains:
  - `MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "200"))`
  - `spool_upload_to_temp_file`
  - `path_or_fileobj=temp_path`
- Verified public Space health `https://mannycooper-nospace-storage.hf.space/` returned `{"ok":"true","service":"nospace-storage","storage":"huggingface-dataset"}`.
- Verified production CORS preflight for `POST /api/assets` from `https://omoyx.github.io` returned `HTTP/2 200` with `access-control-allow-origin: https://omoyx.github.io`.

## Mistakes

- Added `mistake/upload-memory-buffering.md`.
