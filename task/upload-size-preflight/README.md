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

## Mistakes

- Added `mistake/upload-size-late-rejection.md`.
