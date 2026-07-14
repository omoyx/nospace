# Hugging Face Hub writes need bounded retries

A healthy Space can still receive a transient network, rate-limit, or Hub 5xx error while checking or writing its Dataset repo. Without an explicit retry boundary, FastAPI turns the provider exception into a generic `500` after the browser has already transferred the file.

For NoSpace Dataset operations:

- Retry only network failures, HTTP 429, and HTTP 5xx.
- Keep delays short and bounded so upload requests do not hang indefinitely.
- Do not retry authentication, permission, missing-repository, validation, or user-input errors.
- Rewind reusable file-like payloads before retrying.
- Return a stable `503` message after transient retries are exhausted.
- Log provider status and operation names without logging tokens or private file contents.
