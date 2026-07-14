# delete-confirm-dialog

## Goal

- Replace the browser-native delete confirmation with an inline card state.
- Keep destructive intent explicit without interrupting the surrounding canvas.

## Behavior

- Blur only the selected card and center the second confirmation action over it.
- Support a quiet cancel action without a page-level overlay or dialog.
- Lock cancellation while deletion is running and show the request error in the card.
- Preserve the existing card delete icon and delete API behavior.

## Verification

- `npm run lint` passed.
- Production frontend build passed with the configured Space API and 200 MB upload limit.
- `git diff --check` passed.
- Browser-level asset interaction is pending production deployment because no upload invite is stored in the repository or local environment.
