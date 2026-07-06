# Upload handlers must not buffer full files in memory

Do not implement NoSpace uploads with `await file.read()` followed by an in-memory `BytesIO(content)` upload for large-file support.

For the current FastAPI + Hugging Face Dataset architecture:

- Check the invite and storage config before consuming the request body.
- Read `UploadFile` in bounded chunks.
- Write chunks to a temporary file while counting bytes and hashing content.
- Stop and delete the temp file as soon as the configured size limit is exceeded.
- Pass the temp file path or file object to `huggingface_hub`, then delete the temp file in `finally`.
