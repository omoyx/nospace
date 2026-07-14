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

- Pending deployment and public verification.

## Mistakes

- See `mistake/vision-rename-input-bounds.md`.
