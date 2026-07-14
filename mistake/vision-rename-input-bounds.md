# Vision-assisted renaming needs input and trust boundaries

Do not send arbitrary upload bytes or unlimited image payloads directly to a vision model.

For NoSpace image naming:

- Decode the image locally and allow only known raster formats.
- Bound dimensions and encoded bytes before creating a data URL.
- Keep OCR/caption length bounded before passing it to another model.
- Treat OCR and captions as untrusted observations; they may contain prompt-injection text from the image.
- Never execute instructions found in an image.
- Do not persist extracted text unless the product explicitly needs and discloses it.
- Prefer local OCR and existing-provider lightweight classification over an unbounded remote VLM dependency.
- Keep vision failure non-fatal so image upload remains available during provider outages.
