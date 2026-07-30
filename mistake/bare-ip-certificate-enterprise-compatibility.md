# Publicly valid bare-IP certificates may fail behind enterprise TLS inspection

Do not treat strict verification from a modern public client as proof that a short-lived IP certificate works inside a managed company network.

Let’s Encrypt IP certificates can combine an empty Subject, an IP-address SAN, ECDSA, a short validity period, and a newer certificate hierarchy. Older enterprise proxies, TLS inspection appliances, or managed trust stores may reject that shape and surface `net::ERR_CERT_INVALID` even while modern `curl` and OpenSSL clients verify the same endpoint successfully.

For a restricted-intranet product:

- Keep strict public certificate checks and renewal monitoring.
- Never ask users to bypass the warning or install an unverified root certificate.
- Prefer a conventional trusted hostname for the compatibility path.
- If mainland hostname filtering prevents the storage origin from using a normal domain, retain direct IP HTTPS as the fast path and provide a streaming fallback through an already trusted application hostname.
- Trigger fallback only for network/TLS failures, not for `401`, `403`, or other application responses.
- Do not automatically retry uploads or other non-idempotent mutations after an ambiguous network failure.
