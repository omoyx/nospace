# Hugging Face folder upload included ignored artifacts

## Problem

`HfApi.upload_folder(folder_path="space")` uploaded local `space/storage/` data and
`space/__pycache__/` bytecode even though they were not tracked by the main Git
repository.

## Prevention

- Keep a deployment-local `space/.gitignore` covering `storage/` and
  `__pycache__/`.
- Inspect `HfApi.list_repo_files(..., repo_type="space")` after every Space
  upload, not only the local Git status.
- Delete unexpected remote artifacts before considering a deployment complete.

