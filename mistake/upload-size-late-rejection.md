# Upload size must be rejected before transfer

Oversized uploads should not be discovered only after reading the full multipart file body.

For NoSpace:

- Frontend checks `File.size` against `VITE_MAX_UPLOAD_MB` before starting `XMLHttpRequest`.
- Backend keeps the final exact check against `MAX_UPLOAD_MB`.
- Backend also rejects clearly oversized `/api/assets` requests from `Content-Length` before multipart parsing when possible.
- Keep `VITE_MAX_UPLOAD_MB` and `MAX_UPLOAD_MB` aligned during deployment.
