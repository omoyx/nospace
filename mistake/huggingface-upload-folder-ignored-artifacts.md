# Hugging Face folder upload included ignored artifacts

## Problem

`HfApi.upload_folder(folder_path="space")` uploaded local `space/storage/` data and
`space/__pycache__/` bytecode even though they were not tracked by the main Git
repository.

## Prevention

- A deployment-local `.gitignore` is insufficient: `HfApi.upload_folder` has
  uploaded ignored files more than once in this project.
- Call `upload_folder` with an explicit `allow_patterns` list containing only
  the production files, or build explicit `CommitOperationAdd` operations.
- Inspect `HfApi.list_repo_files(..., repo_type="space")` after every Space
  upload, not only the local Git status.
- Delete unexpected remote artifacts before considering a deployment complete.
