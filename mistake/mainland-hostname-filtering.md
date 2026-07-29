# Mainland hostname filtering can differ from direct IP HTTPS

Do not infer public ingress availability from DNS resolution or a locally valid Caddy configuration.

On the Shanghai Huawei ECS:

- `sslip.io` resolved correctly to the public IP.
- Direct HTTP and temporary direct-IP TLS reached the origin.
- Requests carrying the `sslip.io` hostname were intercepted with Huawei `ADM/2.1.1` and `非法阻断 2403`, while TLS SNI connections were reset.
- Let’s Encrypt production successfully issued a short-lived certificate directly for the IP through Caddy 2.11.4.
- A bare IP site without an explicit ACME issuer makes Caddy choose its local CA. Pin the production Let's Encrypt directory and `profile shortlived`; a valid Caddyfile alone does not prove that browsers will trust its certificate.
- Bare-IP clients that omit SNI require Caddy `default_sni` to select the IP certificate.

For this host, use a trusted IP certificate and direct IP HTTPS. Keep automatic renewal monitored because the certificate is valid for roughly six days.
