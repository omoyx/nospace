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

- Pending deployment and public verification.

## Mistakes

- See `mistake/ai-generated-filename-safety.md`.
