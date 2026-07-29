# Invite session cache mismatch

Do not cache an invite code and its authorization role as unrelated values.

A cached `upload` session can be paired with a different current invite after a
legacy cache restore, interrupted storage update, browser history restore, or
editing an invite field before submitting it. The UI may then expose upload
controls while the backend correctly rejects the request as read-only.

Prevention:

- Include the authenticated invite in the cached session and reject legacy or
  mismatched session records.
- Keep the authenticated invite separate from the editable invite-field draft.
- Use only the authenticated invite for list, upload, delete, preview, and
  download requests.
- Disable write controls while an invite is being restored or switched.
- Keep backend authorization authoritative even when the UI has cached state.
