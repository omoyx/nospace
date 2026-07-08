# login-503

## Goal

Restore production login after the public frontend showed `请求失败：503`.

## Diagnosis

- The frontend login request calls `POST /api/session` on the production Hugging Face Space.
- `https://mannycooper-nospace-storage.hf.space/` and `/api/session` both returned `HTTP/2 503` with `Your space is in error, check its status on hf.co`.
- Hugging Face runtime API reported:
  - `stage=RUNTIME_ERROR`
  - `errorMessage=Scheduling failure: unable to schedule`
  - requested hardware `cpu-basic`
  - domain stage `READY`
- This was a Space scheduling/runtime availability issue, not an invite validation or frontend build issue.

## Fix

- Restarted Hugging Face Space `mannycooper/nospace-storage` with `HfApi.restart_space`.
- The Space moved through `BUILDING` and `APP_STARTING`, then reached `RUNNING` on `cpu-basic`.

## Verification

- `curl -i https://mannycooper-nospace-storage.hf.space/` returned `HTTP/2 200` with `{"ok":"true","service":"nospace-storage","storage":"huggingface-dataset"}`.
- `POST /api/session` with an invalid probe invite returned `HTTP/2 401` and `{"detail":"邀请码无效"}`, confirming login requests now reach the app instead of the Space 503 page.
- CORS preflight for `POST /api/session` from `https://omoyx.github.io` returned `HTTP/2 200`.
- `https://omoyx.github.io/nospace/` returned `HTTP/2 200` and still references `/nospace/assets/index-Npk8aTEu.js`.
- Hugging Face runtime API reported `stage=RUNNING`, `hardware=cpu-basic`, domain `READY`, runtime SHA `dd0644f670747685f0686eccf9b3cc8d41f7c8d1`.

## Production

- No code deployment was required.
- Production backend was restored by restarting the existing Hugging Face Space.

## Git

- `git status --short` before documentation edits was clean.
- `git status --short` after documentation edits showed only `mistake/hf-space-scheduling-failure.md` and `task/login-503/README.md`.
