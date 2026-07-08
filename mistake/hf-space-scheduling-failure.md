# Hugging Face Space scheduling failure returns 503

When production login shows `请求失败：503`, first check whether the Hugging Face Space itself is in error before debugging frontend invite logic.

Useful checks:

- `curl -i https://mannycooper-nospace-storage.hf.space/`
- `curl -i -X POST https://mannycooper-nospace-storage.hf.space/api/session -H 'content-type: application/json' --data '{"invite":"invalid-probe"}'`
- `HfApi().get_space_runtime("mannycooper/nospace-storage")`

If the runtime reports `RUNTIME_ERROR` with `Scheduling failure: unable to schedule`, the app may not be running even though the domain is `READY`. Restarting the Space with `HfApi().restart_space("mannycooper/nospace-storage")` can restore service without code changes. Verify afterward that `/` returns app health JSON and `/api/session` returns a business response such as `401` for an invalid invite instead of the Space-level 503 HTML page.
