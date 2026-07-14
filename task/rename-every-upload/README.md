# rename-every-upload

## Goal

- Run GLM 5.2 filename optimization for every new upload, not only detected mojibake.
- Display the generated name as the primary card title.
- Display the original upload name as a muted second line.

## Implementation

- Every upload calls the configured GLM filename endpoint with the original name, extension, MIME type, and reversible encoding candidates.
- File bytes and notes remain private and are not sent to the model.
- Mojibake keeps deterministic encoding repair as a fallback.
- If GLM is unavailable or returns the original name unchanged, an objective MIME label guarantees a distinct result such as `季度报告 · PDF.pdf`; unrecoverable mojibake uses a generic type name instead of preserving broken text.
- Cards render `displayName` on the first line and a smaller muted `originalName` below it when the names differ.
- Historical assets without `displayName` remain single-line instead of repeating the same name.

## Verification

- `.venv/bin/python -m py_compile space/app.py space/test_app.py` passed.
- `.venv/bin/python -m unittest space/test_app.py -v` passed with 11 tests covering every-file model calls, unchanged model responses, model failure, mojibake repair, MIME fallback, output sanitization, and saved metadata.
- Real GLM 5.2 calls using the local reference configuration produced distinct names for normal inputs:
  - `Quarterly_Report_FINAL_v3.txt` -> `季度报告_v3.txt`
  - `季度报告.pdf` -> `季度报告文档.pdf`
  - `IMG_1234.jpg` -> `照片IMG_1234.jpg`
- `npm run lint` passed.
- `GITHUB_PAGES=true VITE_API_BASE_URL=https://mannycooper-nospace-storage.hf.space VITE_MAX_UPLOAD_MB=200 npm run build` passed.
- In-app browser verification against the local mock API confirmed:
  - The card displays generated `季度报告 v3.txt` on the first line and original `Quarterly_Report_FINAL_v3.txt` on the second line.
  - The original line computes to `10px`, weight `500`, color `rgb(162, 165, 168)`, with ellipsis overflow.
  - Desktop screenshot: `/tmp/nospace-rename-every-desktop.png`.
  - Mobile screenshot at `390x844`: `/tmp/nospace-rename-every-mobile.png`.
  - At mobile width, the original-name line remained within the asset card bounds.
  - Browser error/warning logs were empty.
- `git diff --check` passed.

## Production

- Committed the implementation as `de173e9 Rename every uploaded file` and pushed `main` to GitHub.
- Uploaded the backend to Hugging Face Space commit `821ff950edf2dc0fe9caa4dc926437e40b3b1d61`.
- Verified the Space runtime reached `RUNNING` at that exact SHA.
- Verified `https://mannycooper-nospace-storage.hf.space/` returns `HTTP 200` with `"smartFilenameRename":"glm-5.2"`.
- Verified the public Space `app.py` contains the every-upload prompt, `objective_file_type`, `type_normalized_filename`, and the upload-time `smart_display_filename` call.
- GitHub Pages workflow run `29299980338` completed successfully for commit `de173e92a2851194e297b266fd280aad3fc3d493`:
  - `https://github.com/omoyx/nospace/actions/runs/29299980338`
- Verified `https://omoyx.github.io/nospace/?release=de173e9` returns `HTTP 200` and loads:
  - `/nospace/assets/index-Bnzjz3wW.js`
  - `/nospace/assets/index-CQNaUKkS.css`
- Verified the public JavaScript contains `asset-title-stack`, `asset-original-name`, `displayName`, and `originalName`.
- Verified the public CSS contains the muted original-name class with `#a2a5a8` and `font-size:10px`.
- Opened the public frontend in the in-app browser; the page title was `NoSpace` and browser error/warning logs were empty.
- A temporary production upload was not performed because the current upload invite remains intentionally absent from the repository. The deployed backend source/config, real GLM calls, route tests, and local desktop/mobile browser upload flow verify the change without bypassing production access controls.

## Mistakes

- No new recurring issue identified; model-output safety remains covered by `mistake/ai-generated-filename-safety.md`.
