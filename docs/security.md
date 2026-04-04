# Security

Traefik Manager is designed to run behind a reverse proxy on a trusted network. This page documents the security controls built in and recommended practices for hardening your installation.

---

## Authentication

### Password

The login password is hashed with **bcrypt at cost 12** before storage in `manager.yml`. The plaintext password is never written to disk.

Login attempts are rate-limited to **5 per minute per IP** to slow brute-force attacks. After three failed attempts within a short window, the rate limit will block further attempts temporarily.

### Session management

Sessions use signed client-side cookies (Flask SecureCookieSession). The signing key is generated once and persisted to `/app/config/.secret_key` - it does not change on restart, so sessions survive container restarts.

| Setting | Value |
|---|---|
| Max session lifetime | 7 days (when "Remember me" is checked) |
| Inactivity timeout | 120 minutes (configurable via `INACTIVITY_TIMEOUT_MINUTES`) |
| Cookie flags | `HttpOnly`, `SameSite=Lax` |
| Secure flag | Off by default - set `COOKIE_SECURE=true` when behind HTTPS |

The inactivity timeout is bypassed when "Remember me" is checked. Sessions are invalidated immediately on logout.

---

## Two-factor authentication (TOTP)

TM supports TOTP-based 2FA compatible with any standard authenticator app (Google Authenticator, Authy, etc.).

The TOTP secret is encrypted at rest using Fernet symmetric encryption. The encryption key is derived from the session secret key and stored alongside the secret in `manager.yml`.

2FA can be reset via the [reset password page](reset-password.md) if you lose access to your authenticator.

---

## API keys

API keys are used by the mobile app and scripts to access the API without a browser session.

- Up to **10 keys** can exist simultaneously, each with a **device name** for identification
- Each key is **bcrypt-hashed at cost 12** - the plaintext is shown once at creation and never stored
- Keys are revoked individually by device name - revoking one device does not affect others
- API key requests bypass CSRF checks by design (they carry the key in a header instead)
- Generation is rate-limited to **5 per hour per IP**

Keys are passed via the `X-Api-Key` request header:

```
X-Api-Key: your-key-here
```

---

## CSRF protection

All state-changing endpoints (POST, DELETE) require a CSRF token when using session authentication. The token is embedded in every HTML page as a `<meta name="csrf-token">` tag and rotates on each session.

API key requests are exempt from CSRF checks.

---

## Rate limiting

| Endpoint | Limit |
|---|---|
| Login, OTP verification | 5 / min per IP |
| Password change, OTP management | 10 / min per IP |
| API key generation | 5 / hour per IP |
| Backup restore | 10 / min per IP |
| All other endpoints | Unlimited |

---

## Cookie security

| Flag | Default | How to enable |
|---|---|---|
| `HttpOnly` | Always on | - |
| `SameSite=Lax` | Always on | - |
| `Secure` | Off | Set `COOKIE_SECURE=true` env var |

Set `COOKIE_SECURE=true` whenever TM is accessed over HTTPS. Without it, browsers may send cookies over HTTP, which is a risk if your reverse proxy is not enforcing HTTPS-only access.

---

## Recommended setup

::: tip Run behind a reverse proxy with HTTPS
Never expose Traefik Manager directly on port 5000 to the internet. Use a reverse proxy (Traefik itself works well) with a valid TLS certificate.
:::

Recommended configuration:

1. **Use HTTPS** - configure a cert resolver in Traefik and enable the self-route in TM Settings
2. **Set `COOKIE_SECURE=true`** in your docker-compose environment
3. **Enable 2FA** via Settings → Authentication → Two-Factor Authentication
4. **Use per-device API keys** - generate a separate key for each device/script, revoke individually if compromised
5. **Mount config files read-only** where possible - TM only needs write access to `CONFIG_DIR` and `/app/config`

---

## File permissions

TM writes to three locations:

| Path | Purpose |
|---|---|
| `/app/config/manager.yml` | Settings, hashed password, API key hashes |
| `/app/config/.secret_key` | Session signing key (generated once) |
| `CONFIG_DIR` / `CONFIG_PATHS` | Dynamic Traefik config files |

These paths should be owned by the container user and not world-readable on the host. The `/app/config/` directory is the most sensitive as it contains the password hash and session key.
