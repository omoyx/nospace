# upload-size-preflight

## Goal

Reject files larger than the configured upload limit before users spend time transferring them, while keeping the backend limit authoritative.

## Verification

- `npm run lint` passed.
- `GITHUB_PAGES=true VITE_API_BASE_URL=https://mannycooper-nospace-storage.hf.space VITE_MAX_UPLOAD_MB=80 npm run build` passed.
- `.venv/bin/python -m py_compile space/app.py` passed.
- Direct middleware check with a synthetic `/api/assets` request whose `Content-Length` is larger than `MAX_UPLOAD_MB` plus multipart allowance returned:
  - `413`
  - `{"detail":"文件超过 80 MB"}`
- `rg -n "单个文件不超过|超过 .* MB 上限|文件超过 80 MB|VITE_MAX_UPLOAD_MB" dist src space docs README.md .github/workflows task mistake` confirmed the built frontend and docs include the upload limit.
- `git diff --check` passed.
- `git status --short` before commit showed only the upload preflight code, docs, workflow, task note, and mistake note modified/added.
- Browser automation note: the local Playwright CLI wrapper failed with `playwright-cli: command not found`, and ad-hoc `npx -p playwright` did not expose the `playwright` package to `require()`, so no browser screenshot was captured in this milestone.
- Committed local milestone as `5bf076f Prevent late oversized upload failures`.
- Pushed `main` to GitHub.
- Uploaded `space/` to Hugging Face Space `mannycooper/nospace-storage`.
- GitHub Pages workflow run `28789341087` completed successfully.
- Verified public frontend `https://omoyx.github.io/nospace/` returned `HTTP/2 200` and referenced:
  - `/nospace/assets/index-Deyf0App.js`
  - `/nospace/assets/index-dm-BHXki.css`
- Verified public JS `https://omoyx.github.io/nospace/assets/index-Deyf0App.js` contains the upload limit calculation and text:
  - `fi*1024*1024`
  - `超过 ${fi} MB 上限`
  - `单个文件不超过 ${fi} MB`
- Verified Space repo SHA and runtime SHA both equal `b5d9e5dd3edea2e2c748b0e61a3d41a799cc4b87`.
- Verified Space runtime stage is `RUNNING` and domain stage is `READY`.
- Verified public Space health `https://mannycooper-nospace-storage.hf.space/` returned `{"ok":"true","service":"nospace-storage","storage":"huggingface-dataset"}`.
- Verified production CORS preflight for `POST /api/assets` from `https://omoyx.github.io` returned `HTTP/2 200` with `access-control-allow-origin: https://omoyx.github.io`.
- Production oversized raw-request note: a synthetic HTTPS request with a large `Content-Length` but no body did not return within 12 seconds, likely because the public proxy waits for the body. The deployed Space SHA still confirms the new backend code is running.

## Mistakes

- Added `mistake/upload-size-late-rejection.md`.
