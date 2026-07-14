# image-ocr-caption-rename

## Goal

- Add OCR text and an image caption as evidence for automatic image filename generation.
- Keep visual analysis bounded, non-fatal, and private by default outside the required provider request.

## Implementation

- Decode supported raster images with Pillow before external analysis.
- Keep small PNG/JPEG/WebP files in their source encoding for OCR quality.
- Resize other images to a 1600-pixel longest edge and compress JPEG output toward a 3 MB cap.
- Run Chinese/English Tesseract OCR locally inside the Space.
- Call `google/mobilenet_v2_1.0_224` through Hugging Face Inference for bounded visual classification labels.
- Build a caption from image dimensions, visual labels, and whether OCR text is present; no Qwen vision model is used.
- Pass only bounded OCR/caption text to GLM 5.2 as untrusted naming evidence.
- Never persist OCR/caption in Dataset metadata and never send upload notes.
- Skip unsupported/corrupt images and continue normal filename generation when either vision or filename analysis fails.

## Verification

- Confirmed paid vision providers are unsuitable for this deployment because of quota constraints; prohibited Flash models are not used or configured.
- Verified `google/mobilenet_v2_1.0_224` is live on the Hugging Face Inference provider using the existing `HF_TOKEN`.
- The exact screenshot classified primarily as `web site` (`47%`) and secondarily as `menu`, which complements OCR for screenshot naming.
- Real end-to-end visual naming on `Screenshot 2026-07-13 at 11.40.39.png` produced:
  - Local OCR: multiple `Hong Kong` rows and their visible numeric suffixes.
  - Visual classification: `web site` (`47%`) and `menu` (`5%`).
  - Caption: `531x441 图片，视觉类别可能包括 web site（47%）、menu（5%），包含可识别文字。`
  - GLM 5.2 filename: `香港数据列表截图_2026-07-13.png`.
- `.venv/bin/python -m py_compile space/app.py space/test_app.py` passed.
- `.venv/bin/python -W ignore::DeprecationWarning -W error::RuntimeWarning -m unittest space/test_app.py -v` passed with 22 tests.
- Tests cover source-format preservation, large-image resize/JPEG conversion, unsupported formats, structured OCR/caption parsing, non-fatal vision failure, prompt context, and upload-route context forwarding.
- `npm run lint` passed.
- `GITHUB_PAGES=true VITE_API_BASE_URL=https://mannycooper-nospace-storage.hf.space VITE_MAX_UPLOAD_MB=200 npm run build` passed.
- `pip install --dry-run --no-cache-dir -r space/requirements.txt` resolved `Pillow==10.4.0` and all production requirements.
- `docker build -t nospace-storage-ocr-caption:test space` passed.
- The built image imports `space/app.py` successfully and `tesseract --list-langs` includes `chi_sim`, `eng`, and `osd`.
- `git diff --check` passed.

## Production

- Pushed implementation commit `07d7574` and deployment-artifact guard commit `d285061` to `main`.
- Set the Space variable `IMAGE_CLASSIFICATION_MODEL=google/mobilenet_v2_1.0_224`; no Qwen variable or secret is configured.
- Uploaded the backend to Hugging Face Space commit `a49d9e94ea3af5bcc49a1607d047c0396cf643d1`.
- Detected and removed ignored local `storage/` and `__pycache__/` artifacts from the Space, then deployed clean commit `b987b6a5514f2dbf61dbd7a09b642e86514c8339`.
- Verified the Space repo SHA and runtime SHA both equal the clean commit and the runtime stage is `RUNNING`.
- Verified the public Space file list contains no `storage/`, bytecode, or uploaded image artifacts.
- Verified the public Dockerfile installs `tesseract-ocr`, `tesseract-ocr-chi-sim`, and `tesseract-ocr-eng`.
- Verified the public app source contains the bounded Tesseract, MobileNet, and `imageAnalysis` flow and contains no `qwen3-vl-flash` marker.
- Verified `https://mannycooper-nospace-storage.hf.space/` returns `imageAnalysis: tesseract+google/mobilenet_v2_1.0_224`, `smartFilenameRename: glm-5.2`, and Dataset storage.
- A production upload was not performed because the current upload invite remains intentionally absent from the repository. The user should retry the exact screenshot through the public frontend.

## Mistakes

- See `mistake/vision-rename-input-bounds.md`.
- See `mistake/huggingface-upload-folder-ignored-artifacts.md`.
