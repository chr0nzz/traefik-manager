# OIDC / SSO Login

Traefik Manager supports **OpenID Connect (OIDC)** as an additional login method alongside the built-in password. When enabled, a "Sign in with ..." button appears on the login page. Password login continues to work - OIDC is additive, not a replacement.


---

## How it works

1. User clicks "Sign in with [Provider]" on the login page
2. Traefik Manager fetches the provider's discovery document (`/.well-known/openid-configuration`) and redirects to the authorization endpoint
3. User authenticates at the provider
4. Provider redirects back to `/auth/oidc/callback` with an authorization code
5. Traefik Manager exchanges the code for tokens, fetches user info, checks access control, and establishes a session

OIDC login creates the same session as password login - the user lands on the dashboard with full access.

---

## Setup

### 1. Register an application with your provider

You need a **client ID** and **client secret**. The redirect URI to register is:

```
https://your-traefik-manager.example.com/auth/oidc/callback
```

### 2. Configure OIDC in Traefik Manager

Go to **Settings → Authentication → OIDC / SSO Login** and fill in:

| Field | Description |
|-------|-------------|
| Provider URL | Base URL of your OIDC provider (without `/.well-known/...`) |
| Client ID | The client ID from your provider |
| Client Secret | The client secret (stored encrypted at rest) |
| Display Name | Label shown on the login button, e.g. `Keycloak` |
| Allowed Emails | Comma-separated list of emails that can log in. Empty = any verified account |
| Allowed Groups | Comma-separated group names required. Empty = skip group check |
| Groups Claim Key | Claim name that contains groups (default: `groups`) |

Click **Test** next to the Provider URL to verify the discovery document is reachable, then click **Save OIDC Config** and toggle **Enable**.

---

## Provider examples

### Google OAuth2

1. Go to [Google Cloud Console](https://console.cloud.google.com/) → APIs & Services → Credentials
2. Create an **OAuth 2.0 Client ID** (Web application)
3. Add `https://your-traefik-manager.example.com/auth/oidc/callback` to Authorized redirect URIs

| Field | Value |
|-------|-------|
| Provider URL | `https://accounts.google.com` |
| Groups Claim Key | *(leave default - Google does not expose groups)* |
| Allowed Emails | Restrict to your domain or specific addresses |

### Keycloak

| Field | Value |
|-------|-------|
| Provider URL | `https://keycloak.example.com/realms/your-realm` |
| Groups Claim Key | `groups` |
| Allowed Groups | Your Keycloak group name, e.g. `traefik-admins` |

In Keycloak: create a client with **Standard Flow** enabled, set the redirect URI, and add the `groups` mapper under Client Scopes so groups appear in the token.

### Authentik

| Field | Value |
|-------|-------|
| Provider URL | `https://authentik.example.com/application/o/your-app/` |
| Groups Claim Key | `groups` |
| Allowed Groups | Your Authentik group name |

In Authentik: create an OAuth2/OpenID Provider and a corresponding Application. Use **Authorization Code** flow.

---

## Access control

Both filters are optional and independent:

- **Allowed Emails** - if set, the user's `email` claim must be in this list. Useful when you want to allow specific people from a shared provider (e.g. a Google Workspace domain).
- **Allowed Groups** - if set, at least one of the user's groups must match. Useful when you use Keycloak or Authentik and want to restrict by role.

If both are set, **both** conditions must pass.

Leave both empty to allow any account that successfully authenticates with your provider.

---

## Mobile app

OIDC login applies to the **web UI only**. The mobile app authenticates via API key (`X-Api-Key` header) regardless of which login method is configured on the web.

If you use OIDC to log in to the web UI, generate an API key via **Settings → Authentication → App / Mobile API Keys**, then enter that key in the mobile app's Server settings. The process is identical to password-based login.

---

## Rate limiting

`/auth/oidc/login` is rate-limited to **10 requests per minute per IP** to prevent abuse.

---

## Security notes

- The OIDC client secret is **encrypted at rest** using Fernet symmetric encryption (the same key used for TOTP secrets).
- The `state` parameter is validated on callback to prevent CSRF attacks.
- A `nonce` is sent in the authorization request and stored in the session.
- Token exchange and userinfo fetch happen server-side - no tokens are exposed to the browser.
