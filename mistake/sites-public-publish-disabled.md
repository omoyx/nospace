# Sites public publishing may be disabled

The Sites deployment succeeded, but changing access to public failed with:

```text
Publishing Sites to the internet is not enabled for this workspace.
```

In this workspace, the available access modes were only `custom` and `workspace_all`.

Impact:

- The production URL works for the allowed owner account.
- External visitors are stopped by the ChatGPT sign-in gate before reaching the app's own invite-code screen.
- The app's same-origin invite API and object storage still work behind that gate.

For a public invite-only link, use a workspace with Sites public publishing enabled or deploy this repo to another public host.
