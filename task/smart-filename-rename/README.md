# smart-filename-rename

## Goal

- Detect suspicious mojibake filenames during upload.
- Use the configured GLM 5.2 endpoint to recover a safe, readable display and download name.
- Refresh the frontend asset feed after upload so the server's final name is shown.

## Implementation

- Normal filenames bypass the model.
- Suspect filenames are evaluated with their extension, MIME type, and reversible encoding candidates; file bytes and notes are not sent.
- Model output is parsed as JSON, stripped of path/control characters, length-limited, and forced to keep the original extension.
- The Dataset index keeps `originalName` and adds `displayName` plus `renameModel` only when a rename succeeds.
- Downloads and frontend cards use `displayName` when present, while search still matches both names.
- A failed model call does not fail the upload; deterministic encoding repair is used when possible.

## Verification

- `.venv/bin/python -m py_compile space/app.py space/test_app.py` passed.
- `.venv/bin/python -m unittest space/test_app.py -v` passed with detection, repair, sanitization, model bypass/fallback, and upload metadata coverage.
- A real GLM 5.2 integration call using the local reference configuration renamed `æµ‹è¯•æŠ¥å‘Š.pdf` to `测试报告.pdf`.
- `npm run lint` passed.
- `GITHUB_PAGES=true VITE_API_BASE_URL=https://mannycooper-nospace-storage.hf.space VITE_MAX_UPLOAD_MB=200 npm run build` passed.
- In-app browser verification against `mock-api.mjs` confirmed:
  - The uploaded card displayed `测试报告.txt` instead of the stored `originalName`.
  - The mock recorded three `GET /api/assets` calls and `uploaded=true`, including the explicit post-upload refresh.
  - Download, copy, and delete controls remained available on the renamed card.
  - Browser error/warning logs were empty.
  - Screenshot: `/tmp/nospace-smart-filename-rename.png`.
- The standalone Playwright skill wrapper could not run because its internal `playwright-cli` command was unavailable; the installed in-app browser completed the real-browser checks.
- `git diff --check` passed.

## Production

- Committed the implementation as `c5b9f9f Rename garbled uploads with GLM 5.2` and pushed `main` to GitHub.
- Configured the Space from the local GLM 5.2 reference contract:
  - `BAILIAN_OPENCODE_BASE_URL` as a Space variable.
  - `BAILIAN_OPENCODE_MODEL=glm-5.2` as a Space variable.
  - `BAILIAN_OPENCODE_API_KEY` as a Space secret; its value was never printed or committed.
- Uploaded the backend to Hugging Face Space commit `41cb36302de48b7b79ae2b5ed343e1a273200b59`.
- Verified Space repo SHA and runtime SHA both equal that commit, runtime stage is `RUNNING`, and the public domain stage is `READY`.
- Verified `https://mannycooper-nospace-storage.hf.space/` returns `HTTP 200` with `"smartFilenameRename":"glm-5.2"`.
- Verified the production CORS preflight for `POST /api/assets` from `https://omoyx.github.io` returns `HTTP 200` and the expected origin/method/header permissions.
- GitHub Pages workflow run `29248084622` completed successfully for commit `c5b9f9fcea36dcfda8762a9590fb49d472f1f660`:
  - `https://github.com/omoyx/nospace/actions/runs/29248084622`
- Verified `https://omoyx.github.io/nospace/?release=c5b9f9f` returns `HTTP 200` and loads:
  - `/nospace/assets/index-CLcldk3c.js`
  - `/nospace/assets/index-BTAExjn6.css`
- Verified the public JavaScript contains the deployed `displayName` handling and `/api/assets` request paths.
- Opened the public frontend in the in-app browser; the page title was `NoSpace` and browser error/warning logs were empty.
- A temporary production upload was not performed because the current upload invite has been rotated and is intentionally absent from the repository and readable Space variables. Old documented invites returned `401`; no production test asset was created. The deployed code/config, real GLM call, backend route tests, and local browser upload-refresh flow provide the completed verification without bypassing production access controls.

## Mistakes

- See `mistake/ai-generated-filename-safety.md`.
