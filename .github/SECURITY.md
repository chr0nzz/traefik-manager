# Security Policy

## Supported Versions

Only the latest release receives security fixes.

| Version | Supported |
|---------|-----------|
| Latest  | Yes |
| Older   | No |

## Reporting a Vulnerability

Please **do not** open a public GitHub issue for security vulnerabilities.

**Preferred:** Use [GitHub private vulnerability reporting](https://github.com/chr0nzz/traefik-manager/security/advisories/new) - this keeps the report confidential until a fix is released.

**Alternative:** Email [187675356+chr0nzz@users.noreply.github.com](mailto:187675356+chr0nzz@users.noreply.github.com) with a description of the issue and steps to reproduce.

Please include:
- A description of the vulnerability and its potential impact
- Steps to reproduce or proof-of-concept
- The version of Traefik Manager affected

You can expect an acknowledgement within **48 hours** and a fix or mitigation plan within **14 days** depending on severity.

## Scope

In scope:
- Authentication bypass or privilege escalation
- Remote code execution
- Path traversal or unauthorized file read/write
- CSRF or session fixation
- Secrets exposed in logs, responses, or config files

Out of scope:
- Vulnerabilities requiring physical access to the host
- Issues in Traefik itself (report those to the [Traefik project](https://github.com/traefik/traefik/security))
- Self-XSS or issues requiring the attacker to already be an authenticated admin
- Rate limit bypasses with no meaningful security impact
