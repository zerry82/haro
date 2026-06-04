# Security Policy

Haro is a developer-preview project. Please do not expose a public deployment
without reviewing authentication, sandboxing, network access, data retention,
and credential storage for your environment.

## Supported Versions

Security fixes target the current `main` branch.

## Reporting a Vulnerability

If you find a vulnerability, please report it privately to the maintainers
instead of opening a public issue with exploit details.

Include:

- affected component or route
- reproduction steps
- expected impact
- relevant logs or screenshots, without secrets
- suggested mitigation, if known

## Secret Handling

Do not commit:

- `.env` files
- OAuth credentials
- API keys
- private keys
- token stores
- workspace runtime data
- user project artifacts that contain private information

Run the local scanner before pushing:

```powershell
.\scripts\scan-secrets.ps1 -All
```

The scanner omits secret values from output. It is a guardrail, not a complete
security solution. If a credential may have been exposed, rotate it immediately.

## Sandbox Notes

Haro uses Docker for code execution and web previews. Treat the sandbox as an
important boundary, but not as a substitute for production hardening. Review
mounts, network policy, resource limits, image provenance, and container
lifecycle behavior before exposing sandbox features to untrusted users.
