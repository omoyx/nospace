# intranet-tls-compatibility

## Goal

- Keep the Shanghai Huawei ECS as the primary browser data path.
- Let browsers behind enterprise TLS inspection reach the same Huawei files when the bare-IP certificate cannot be processed.
- Avoid asking users to bypass browser warnings or install an untrusted certificate.

## Diagnosis

On 2026-07-30, the public endpoint presented the expected Let's Encrypt short-lived IP certificate:

- SAN: IP address `113.44.66.120`.
- Issuer: `C=US, O=Let's Encrypt, CN=YE1`.
- Valid from: 2026-07-29 06:53:43 UTC.
- Valid until: 2026-08-04 22:53:42 UTC.
- Strict `curl` and OpenSSL verification: passed.
- HTTPS reached Caddy and the FastAPI origin.

The valid IP certificate has an empty Subject, an IP SAN, an ECDSA leaf, and the new Let's Encrypt YE hierarchy. The reported `net::ERR_CERT_INVALID` occurs only on the company intranet, which points to an enterprise TLS inspection device or managed trust store that cannot process this certificate shape or hierarchy.

## Implementation

- The frontend tries `https://113.44.66.120` first.
- A network-level failure during invite verification or asset listing switches the active session to `https://mannycooper-nospace-storage.hf.space/compat`.
- HTTP authentication failures do not trigger fallback.
- Uploads, deletes, previews, copies, and downloads use the selected endpoint for the rest of the session, avoiding an unsafe retry of a possibly completed mutation.
- The Hugging Face Space exposes only the required storage routes under `/compat` and streams request/response bodies to the Huawei origin.
- The proxy does not buffer complete uploads or downloads and does not expose internal smart-filename routes.
- `COMPAT_UPSTREAM_URL` controls the proxy target and must be set to `https://113.44.66.120` in the Space.

## Verification

- `.venv/bin/python -m py_compile space/app.py space/test_app.py` passed.
- `.venv/bin/python -W ignore::DeprecationWarning -W error::RuntimeWarning -m unittest space/test_app.py -v` passed with 37 tests.
- Proxy tests cover the public-route allowlist, request-header filtering, source IP forwarding, and download response metadata.
- `npm run lint` passed.
- `GITHUB_PAGES=true VITE_API_BASE_URL=https://113.44.66.120 VITE_API_FALLBACK_URL=https://mannycooper-nospace-storage.hf.space/compat VITE_DEFAULT_INVITE= VITE_MAX_UPLOAD_MB=200 npm run build` passed.
- `docker build -t nospace-storage-intranet-compat:test space` passed.
- The built container proxied a deliberately invalid invite to the public Huawei endpoint and preserved its `401 邀请码无效` response.
- The built container returned a successful GitHub Pages CORS preflight for the compatibility upload path.
- The standalone Playwright CLI wrapper could not resolve its `playwright-cli` executable. The in-app Chromium browser completed the real-browser fallback check instead.
- A browser build with the primary API deliberately set to unreachable `https://127.0.0.1:1` still received and displayed `邀请码无效` from the public compatibility endpoint after login submission.
- Browser error/warning logs were empty after the fallback request.
- `git diff --check` passed.

## Production

- Local implementation commit: `6b7bd6f` (`Add intranet TLS compatibility fallback`).
- Hugging Face Space commit: `36788863a485d2d7a08f5f08d2c277b16d3f6c77`.
- Set Space variable `COMPAT_UPSTREAM_URL=https://113.44.66.120`.
- Verified the Space runtime reached `RUNNING` at the exact target SHA and `mannycooper-nospace-storage.hf.space` reached `READY`.
- Verified `POST https://mannycooper-nospace-storage.hf.space/compat/api/session` forwarded a deliberately invalid invite and returned Huawei's `401 邀请码无效`.
- Verified the public compatibility upload preflight allows `https://omoyx.github.io`, `POST`, and `x-invite-code`.
- Verified `/compat/internal/smart-filename` returns `404`, so internal control-plane routes are not exposed.
- Pushed `main` and verified GitHub Pages workflow `30547410348` completed successfully:
  - <https://github.com/omoyx/nospace/actions/runs/30547410348>
- Verified <https://omoyx.github.io/nospace/?release=6b7bd6f> returns HTTP 200 with a `last-modified` timestamp after the deployment.
- Verified the public page loads `/nospace/assets/index-DFUHBqXR.js`.
- Verified that public bundle contains both `https://113.44.66.120` and `https://mannycooper-nospace-storage.hf.space/compat`.
- No production upload or valid-invite listing was performed because invite values remain intentionally absent from the repository.

## Recurrence

See `mistake/bare-ip-certificate-enterprise-compatibility.md`.
