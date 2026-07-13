# AI-generated filenames are untrusted input

Model output must never be used directly as a filesystem path, download name, or repository path.

For NoSpace filename renaming:

- Parse a narrow JSON response instead of accepting free-form prose.
- Remove path separators and control characters.
- Preserve the upload's original extension instead of trusting a model-provided extension.
- Enforce a length limit and reject empty, unchanged, or still-garbled results.
- Keep durable storage paths based on server-generated IDs.
- Keep the original upload name in metadata for traceability.
- Treat model failure as non-fatal so it cannot block uploads.
