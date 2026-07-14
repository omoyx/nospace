# delete-confirm-dialog

## Goal

- Replace the browser-native delete confirmation with a NoSpace UI component.
- Keep destructive intent explicit without disrupting the minimal gray canvas.

## Behavior

- Show the display filename and muted original filename when they differ.
- Support cancel, backdrop click, close icon, and Escape.
- Lock dismissal while deletion is running and show the request error inline.
- Preserve the existing card delete icon and delete API behavior.

## Verification

- `npm run lint` passed.
- Production frontend build passed with the configured Space API and 200 MB upload limit.
- `git diff --check` passed.
- Browser-level asset interaction is pending production deployment because no upload invite is stored in the repository or local environment.
