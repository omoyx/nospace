# pip package index response can be truncated

When installing Python backend dependencies, pip failed once with:

```text
json.decoder.JSONDecodeError: Unterminated string
```

The retry succeeded after:

```bash
.venv/bin/pip cache purge
.venv/bin/pip install --no-cache-dir -r space/requirements.txt
```

For future backend verification, prefer `--no-cache-dir` if package installation fails during metadata parsing.
