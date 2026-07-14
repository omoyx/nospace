# upload-storage-retry

## Goal

- Prevent transient Hugging Face Hub failures from surfacing as an unexplained upload `500` after the browser reaches 96%.
- Preserve immediate failure for non-retryable authentication and repository configuration errors.

## Diagnosis

- The reported file was `Screenshot 2026-07-13 at 11.40.39.png`, a valid 55,407-byte PNG.
- The same file had uploaded successfully before the rename-every-upload deployment.
- GLM 5.2 successfully generated `截图_2026-07-13_11.40.39.png` for the exact filename.
- The failed attempt produced no Dataset `Upload` commit, placing the failure before or inside the first Hub write.
- The Space was `RUNNING/READY`, all required secret keys remained present, and a direct diagnostic upload of the same file to the Dataset succeeded and was immediately removed.
- The upload path had no retry or Hub-specific error mapping, so a transient Hub request failure became a generic FastAPI `500`.

## Implementation

- Retry Dataset availability checks and uploads after 0.5 and 1.5 seconds for network errors, HTTP 429, and HTTP 5xx.
- Do not retry HTTP 401/403/404.
- Reset in-memory index payloads before retrying so a consumed `BytesIO` is never uploaded empty.
- Map exhausted transient failures to `503 存储服务暂时不可用，请稍后重试`.
- Map authentication and missing-repository errors to explicit server configuration messages.
- Declare `requests` directly because the retry classifier imports its network exception types.

## Verification

- Confirmed the exact file is a valid `531x441` RGBA PNG with size `55,407` bytes and SHA-256 `634931c3828dab9382c3e349932ead05bee1d4fdf78adf791fb28ef49859b3aa`.
- Confirmed GLM 5.2 renames the exact filename to `截图_2026-07-13_11.40.39.png` without error.
- Directly uploaded the same file to a temporary Dataset diagnostic path and immediately removed it:
  - Upload commit: `ca0fd2c7e66634dd7a0ee5d717286e2b5a8878bf`
  - Cleanup commit: `b7f4a10cde93657f0b789c933941985e76c9cd7a`
- Verified Space secret keys `INVITES`, `HF_TOKEN`, and `BAILIAN_OPENCODE_API_KEY` remain configured without reading or printing their values.
- `.venv/bin/python -m py_compile space/app.py space/test_app.py` passed.
- `.venv/bin/python -W ignore::DeprecationWarning -W error::RuntimeWarning -m unittest space/test_app.py -v` passed with 15 tests.
- Retry tests cover recoverable network errors, exhausted retries, non-retryable authentication, and rewinding an in-memory payload before retry.
- `npm run lint` passed.
- `GITHUB_PAGES=true VITE_API_BASE_URL=https://mannycooper-nospace-storage.hf.space VITE_MAX_UPLOAD_MB=200 npm run build` passed.
- `pip install --dry-run --no-cache-dir -r space/requirements.txt` resolved the added direct `requests==2.32.3` dependency.
- `git diff --check` passed.

## Production

- Pending deployment and public verification.

## Mistakes

- See `mistake/hf-hub-transient-upload-failure.md`.
