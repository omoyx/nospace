# async-image-enrichment

## Goal

- Keep Hugging Face image classification, OCR, and evidence-based image renaming off the upload response path.
- Preserve a successful upload even when background image enrichment fails or the Space restarts.

## Implementation

- New image uploads first receive the normal filename/MIME-based smart name and are stored immediately.
- Supported raster images retain their temporary upload file for a FastAPI background task.
- After the response is sent, the background task runs bounded OCR and Hugging Face classification, asks GLM for an evidence-based name, and updates `index.json` only when the initial display name is still current.
- Temporary files are removed by the background task.
- Dataset index mutations are serialized inside the process so concurrent background enrichment cannot overwrite an upload or delete update.
- Background enrichment is best-effort and non-durable; losing it can only lose the optional refined display name, never the uploaded file.

## Verification

- `.venv/bin/python -m py_compile space/app.py space/test_app.py` passed.
- `.venv/bin/python -W ignore::DeprecationWarning -W error::RuntimeWarning -m unittest space/test_app.py -v` passed with 25 tests.
- The upload-route test verifies that image analysis has not started when the durable upload result is produced, then runs the queued background task and verifies the evidence-based metadata update.
- A stale background update test verifies that a newer display name is not overwritten.
- `npm run lint` passed.
- `GITHUB_PAGES=true VITE_API_BASE_URL=https://mannycooper-nospace-storage.hf.space VITE_DEFAULT_INVITE= VITE_MAX_UPLOAD_MB=200 npm run build` passed.
- `docker build -t nospace-storage-async-image:test space` passed.
- The built container imported the production app and reported `async:tesseract+google/mobilenet_v2_1.0_224`.
- `git diff --check` passed.

## Production

- Committed the implementation as `b707255` and pushed `main` to GitHub.
- Uploaded the backend to Hugging Face Space commit `06eac5364ba4f5f73f46c1296bc3b7f30282abf0`.
- Verified the Space runtime reached `RUNNING` at that exact SHA and its public domain reached `READY`.
- Verified `https://mannycooper-nospace-storage.hf.space/` returns `imageAnalysis: async:tesseract+google/mobilenet_v2_1.0_224`.
- GitHub Pages workflow run `30418684027` completed successfully for `b707255`:
  - `https://github.com/omoyx/nospace/actions/runs/30418684027`
- A production upload was not performed because the current upload invite remains intentionally absent from the repository. Route tests prove classification is queued after the durable upload result rather than awaited by it.

## Recurrence

See `mistake/network-enrichment-on-upload-path.md`.
