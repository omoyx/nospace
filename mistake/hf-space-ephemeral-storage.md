# Hugging Face Space disk is not durable file storage

Do not rely on a Space's local filesystem for uploaded files unless paid persistent storage is explicitly enabled and sized for the use case.

For NoSpace, the better default is:

- Space: API, invite checks, upload/download proxy.
- Private Dataset repo: durable files plus `index.json`.
- Space secret `HF_TOKEN`: lets the API read/write the private Dataset.

This avoids losing uploads on Space rebuilds or restarts, and avoids filling the Space runtime disk.
