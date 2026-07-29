# Network enrichment must not block durable uploads

Optional OCR, image classification, captions, and AI-generated display names must not sit on the critical path between receiving file bytes and returning a successful upload response.

For NoSpace:

- Persist the file and base metadata first.
- Run optional image enrichment after the response.
- Treat enrichment as best-effort and never turn its failure into an upload failure.
- Bound temporary files and remove them after background processing.
- Apply background metadata updates conditionally so stale work cannot overwrite a newer name.
- Serialize `index.json` read-modify-write operations while it remains the metadata store.
