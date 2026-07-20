# Security

Traefik Manager is designed to run behind a reverse proxy on a trusted network. This page documents the security controls built in and recommended practices for hardening your installation.

> Looking to harden **Traefik itself** (underscore header spoofing, encoded characters, forwardAuth limits, CVE advisories)? See [Traefik Security Hardening](hardening.md).

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
| Inactivity timeout | 120 minutes for regular sessions (configurable via `INACTIVITY_TIMEOUT_MINUTES`); 24 hours for "Remember me" sessions |
| Cookie flags | `HttpOnly`, `SameSite=Lax` |
| Secure flag | Off by default - set `COOKIE_SECURE=true` when behind HTTPS |

Sessions are invalidated immediately on logout.

---

## Authentication modes

Traefik Manager has two independent web-UI auth mechanisms - **built-in password** and **OIDC / SSO** - plus **API keys** for programmatic access. Access to the UI is required whenever *either* password or OIDC is enabled:

| Password | OIDC | Result |
|---|---|---|
| Enabled | Off | Password login (optionally with 2FA). |
| Enabled | Enabled | Login page offers both. |
| **Disabled** | **Enabled** | **OIDC is the sole login** - the password form is hidden and users are sent to your identity provider. |
| Disabled | Off | **No authentication - the UI is publicly accessible.** A red warning is shown in the app and Settings, and logged at startup. Avoid this outside a fully trusted, isolated network. |

Disabling built-in authentication only turns off the password form - it does **not** disable OIDC. **API keys keep working in every mode**, so the mobile app and automation are unaffected when OIDC is your only interactive login.

> **Recovery / lockout safety:** disabling built-in authentication preserves your password hash in `manager.yml`. If your OIDC provider becomes unreachable and you are locked out, set `auth_enabled: true` in `manager.yml` and restart the container - the password form returns and you can log in with your existing password. You can also generate a fresh password with `flask reset-password` (see the [Reset Password](reset-password.md) guide).

## OIDC / SSO login

TM supports OpenID Connect, either alongside the built-in password or as the **sole** login method (disable built-in authentication to make OIDC mandatory). When enabled, a "Sign in with [provider]" button appears on the login page.

Supported providers include Google, Keycloak, Authentik, Entra ID, Zitadel, and any OIDC-compliant identity provider. Access can be restricted to specific email addresses or groups.

See the [OIDC setup guide](oidc.md) for full configuration details.

| Setting | Detail |
|---|---|
| Client secret storage | Fernet-encrypted at rest (same key as TOTP secret) |
| CSRF protection | `state` parameter validated on callback |
| Rate limit on `/auth/oidc/login` | 10 / min per IP |
| Token exchange | Server-side only - no tokens exposed to the browser |

---

## Two-factor authentication (TOTP)

TM supports TOTP-based 2FA compatible with any standard authenticator app (Google Authenticator, Authy, etc.).

The TOTP secret is encrypted at rest using Fernet symmetric encryption. The encryption key is derived from the session secret key and stored alongside the secret in `manager.yml`.

2FA can be reset via the [reset password page](reset-password.md) if you lose access to your authenticator.

---

## API keys

API keys are used by the mobile app and scripts to access the API without a browser session.

- Up to **10 keys** can exist simultaneously, each with a **device name** for identification
- Each key is **hashed with SHA-256** - the plaintext is shown once at creation and never stored
- Keys are revoked individually by device name - revoking one device does not affect others
- API key requests bypass CSRF checks only when the key is valid - an invalid or missing key still requires a CSRF token
- Generation is rate-limited to **5 per hour per IP**

Keys are passed via the `X-Api-Key` request header:

```
X-Api-Key: your-key-here
```

---

## CSRF protection

All state-changing endpoints (POST, DELETE) require a CSRF token when using session authentication. The token is embedded in every HTML page and rotates on each session.

API key requests are exempt from CSRF checks only when a **valid** key is provided. A request with a missing or invalid key still requires a CSRF token.

---

## External auth providers

Traefik Manager's built-in auth can be disabled when using an external provider such as Authentik, Authelia, or Keycloak via Traefik's `forwardAuth` middleware.

::: warning Mobile app compatibility
`forwardAuth` intercepts all requests including mobile app API calls. To use the mobile app alongside an external auth provider, split the Traefik route so `/api/*` bypasses `forwardAuth` and relies on Traefik Manager's built-in API key auth. See the [mobile app docs](mobile.md#external-auth-providers) for the full example.
:::

---

## Rate limiting

| Endpoint | Limit |
|---|---|
| Login, OTP verification | 5 / min per IP |
| OIDC login initiation | 10 / min per IP |
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

## Browser autofill

Every field in the app except the sign-in form is marked so browsers and password managers do not autofill it. Credential fields inside the app (API user and password, git backup token, CrowdSec key, the basic-auth and digest-auth generators) are marked `new-password`, which stops Chrome offering saved logins and prompting to save what you type there.

The sign-in form is deliberately untouched, so your password manager still works where it should. The password change and TOTP fields in Settings keep their proper `current-password`, `new-password`, and `one-time-code` semantics.

---

## Outbound requests (SSRF protection)

Several features make TM issue outbound HTTP requests on your behalf - the connection test, the webhook test, the URL ping tool, and OIDC provider discovery. To prevent these from being used to reach cloud metadata endpoints, these fetchers reject:

- Link-local addresses (`169.254.0.0/16`, including the `169.254.169.254` cloud metadata IP)
- Multicast, reserved, and unspecified addresses

Private and loopback targets are still allowed, because reaching internal services (e.g. `http://traefik:8080`) is the normal, legitimate use for a self-hosted reverse-proxy manager. Redirects are not followed on the ping tool.

---

## IP geolocation

[IP geolocation](geoip.md) (off by default) resolves client IPs to countries entirely **on the server against a local database** - IP addresses are never sent to any third-party geolocation API. The only outbound request is to download the database file itself (once a month, from `download.db-ip.com`), and only when the feature is enabled. Point `GEOIP_DB_PATH` at your own `.mmdb` to avoid the download entirely and run fully offline.

---

## Git backup safety

When you configure git backup:

- The repository URL must use `https://`, `http://`, `ssh://`, or `git://`. Other transports (`ext::`, `file://`, `fd::`) are rejected, and git is invoked with those protocols disabled, so a crafted URL cannot execute local commands.
- The access token is passed to git through `GIT_ASKPASS` rather than being embedded in the remote URL. It is not written to `.git/config`, does not appear in process arguments, and is redacted from any error message shown in the UI.

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

## Static config editor

The Static Config tab lets you edit `traefik.yml` directly from the UI and restart Traefik with one click. This has security implications beyond the dynamic config:

- **Read-write mount** - `traefik.yml` must be mounted without `:ro`, giving TM write access to Traefik's entire static configuration including entrypoints, providers, and TLS settings
- **Restart access** - restarting Traefik requires one of three methods, each with different trust boundaries:

| Method | Access granted |
|---|---|
| `proxy` (recommended) | TM connects to a socket proxy sidecar limited to container restart operations only |
| `poison-pill` | TM writes a signal file to a shared volume - no Docker API access at all |
| `socket` | TM has direct access to the Docker socket - broadest access |

The socket proxy and poison-pill methods limit the blast radius if TM is compromised. Direct socket access allows TM to interact with any container on the host.

If you do not use the Static Config editor, do not mount `traefik.yml` read-write and do not set `RESTART_METHOD`.

---

## File permissions

TM writes to these locations:

| Path | Purpose |
|---|---|
| `/app/config/manager.yml` | Settings, hashed password, API key hashes |
| `/app/config/.secret_key` | Session signing key (generated once, written `0600`) |
| `/app/config/.otp_key` | TOTP/secret encryption key (written `0600`) |
| `CONFIG_DIR` / `CONFIG_PATHS` | Dynamic Traefik config files |

The `.secret_key` and `.otp_key` files are created with `0600` permissions so only the container user can read them. These paths should be owned by the container user and not world-readable on the host. The `/app/config/` directory is the most sensitive as it contains the password hash and encryption keys.

If you provide your own session key with the `SECRET_KEY` environment variable, it must be at least 32 characters - TM refuses to start with a shorter key.
