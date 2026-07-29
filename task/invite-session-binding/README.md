# invite-session-binding

## Goal

Prevent a previously cached read-only invite or an unsubmitted invite-field
edit from being combined with stale upload UI permissions.

## Implementation

- Cached sessions now include the invite they were issued for.
- Legacy, malformed, or mismatched session cache entries are discarded and
  revalidated before the canvas is restored.
- The editable invite field is separate from the authenticated invite used by
  API requests.
- Upload and delete controls are unavailable while an invite is being restored
  or switched.
- The cached canvas can still render immediately for a matching invite, using a
  visible `验证中` state until write access is revalidated.

## Local verification

- `npm run lint`
- `GITHUB_PAGES=true VITE_API_BASE_URL=https://mannycooper-nospace-storage.hf.space VITE_DEFAULT_INVITE= VITE_MAX_UPLOAD_MB=200 npm run build`
- `node --check task/invite-session-binding/mock-api.mjs`
- Browser regression against `task/invite-session-binding/mock-api.mjs`:
  - a legacy cached upload role paired with the synthetic `read-test` invite
    showed `恢复中`, then restored as `仅下载` with no upload control;
  - a matching cached upload session showed the canvas immediately as
    `验证中`, with no write controls until validation completed;
  - after validation, editing the invite field to `read-test` without
    submitting did not change the authenticated credential;
  - the mock recorded the text upload with `uploadInvites: ["upload-test"]`;
  - submitting the read-only switch immediately removed write controls and
    completed as `Office · 仅下载`.

## Production deployment

Pending commit, GitHub Pages deployment, and public verification.

## Recurrence

See `mistake/invite-session-cache-mismatch.md`.
