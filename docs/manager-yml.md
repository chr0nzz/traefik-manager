# manager.yml Reference

`manager.yml` is Traefik Manager's settings file. It is stored inside the config volume at `/app/config/manager.yml` by default.

::: info
You do not normally need to edit this file by hand. All settings are managed through the **Settings** panel in the UI. This page is a reference for advanced use, scripted deployments, or bypassing the setup wizard.
:::

The file path can be overridden with the [`SETTINGS_PATH`](env-vars.md) environment variable.

---

## Full example

```yaml
domains:
  - example.com
  - example.net
cert_resolver: cloudflare
traefik_api_url: http://traefik:8080
acme_json_path: ""
access_log_path: ""
static_config_path: ""
auth_enabled: true
password_hash: "$2b$12$..."
must_change_password: false
setup_complete: true
otp_enabled: false
otp_secret: ""
oidc_enabled: false
oidc_provider_url: ""
oidc_client_id: ""
oidc_client_secret: ""
oidc_display_name: "OIDC"
oidc_allowed_emails: ""
oidc_allowed_groups: ""
oidc_groups_claim: "groups"
visible_tabs:
  docker: true
  kubernetes: false
  swarm: false
  nomad: false
  ecs: false
  consulcatalog: false
  redis: false
  etcd: false
  consul: false
  zookeeper: false
  http_provider: false
  file_external: false
  certs: true
  plugins: false
  logs: true
```

---

## Key reference

### `domains`

**Type:** list of strings
**Default:** `["example.com"]`
**Env override:** `DOMAINS` (comma-separated)

The base domains Traefik Manager uses when building route rules. Shown as options in the **Add Route** form.

```yaml
domains:
  - example.com
  - home.lab
```

---

### `cert_resolver`

**Type:** string (comma-separated)
**Default:** `"cloudflare"`
**Env override:** `CERT_RESOLVER`

One or more ACME cert resolver names from your `traefik.yml`, comma-separated. The first resolver is the default for new routes. Each route can override the resolver individually via the Add/Edit Route form.

```yaml
cert_resolver: letsencrypt

cert_resolver: letsencrypt, cloudflare
```

---

### `traefik_api_url`

**Type:** string (URL)
**Default:** `"http://traefik:8080"`
**Env override:** `TRAEFIK_API_URL`

The internal URL of your Traefik API. Must be reachable from inside the Traefik Manager container. When both containers share a Docker/Podman network, use the container name.

```yaml
traefik_api_url: http://traefik:8080
```

::: warning
Only `http://` and `https://` URLs are accepted. Any other value is rejected and the default is used.
:::

---

### `auth_enabled`

**Type:** boolean
**Default:** `true`
**Env override:** `AUTH_ENABLED`

Controls whether the built-in username/password login is active. Set to `false` if you are protecting Traefik Manager externally via Authentik, Authelia, or a Traefik `basicAuth` middleware.

```yaml
auth_enabled: false
```

::: warning
When `auth_enabled` is `false`, the UI is completely unauthenticated. Only disable if you have another auth layer in front.
:::

The environment variable takes priority over this field. See [`AUTH_ENABLED`](env-vars.md#auth_enabled).

---

### `password_hash`

**Type:** string (bcrypt hash)
**Default:** `""` (auto-generated on first start)

Bcrypt hash of the admin password. Generated automatically on first run if not present. Managed by the UI (Settings → Authentication → Change password) or by the [CLI reset command](reset-password.md).

To generate a hash manually:

```bash
python3 -c "import bcrypt; print(bcrypt.hashpw(b'yourpassword', bcrypt.gensalt()).decode())"
```

```yaml
password_hash: "$2b$12$abcdefghij..."
```

::: info
The `ADMIN_PASSWORD` environment variable takes priority over this field if set. See [env-vars](env-vars.md#admin_password).
:::

---

### `must_change_password`

**Type:** boolean
**Default:** `false`

When `true`, the user is redirected to a forced password-change screen after login. Set automatically by the CLI reset command. Clear it by changing your password through the UI, or set it to `false` manually.

---

### `setup_complete`

**Type:** boolean
**Default:** `false`

Whether the initial setup wizard has been completed. Set to `true` automatically at the end of the wizard. Set it manually to `true` to skip the wizard on first start.

::: tip Bypass the setup wizard
Pre-populate `manager.yml` with `setup_complete: true`, a valid `password_hash`, and your connection details before starting the container - the wizard will be skipped entirely.
:::

---

### `otp_enabled`

**Type:** boolean
**Default:** `false`

Whether TOTP two-factor authentication is active. Managed via **Settings → Authentication → Enable/Disable 2FA**. See [reset-password.md](reset-password.md#lost-totp-access) if you need to disable it from the CLI.

---

### `otp_secret`

**Type:** string (Fernet-encrypted)
**Default:** `""`

The TOTP secret used to generate and verify 6-digit codes. Stored **encrypted at rest** using Fernet symmetric encryption since v0.5.0. Generated when 2FA is enabled. Cleared when 2FA is disabled.

The encryption key is loaded from the `OTP_ENCRYPTION_KEY` environment variable or auto-generated to `/app/config/.otp_key`. Do not share or commit this value.

::: info Migration
Existing plaintext secrets from pre-v0.5.0 are automatically encrypted on the next settings save. No manual migration is needed.
:::

---

### `disabled_routes`

**Type:** map of string → object
**Default:** `{}`

Stores the full configuration of routes that have been disabled via the enable/disable toggle in the Routes tab. When a route is disabled, its router and service entries are removed from `dynamic.yml` (so Traefik stops routing it) and saved here.

This field is managed entirely by the UI - do not edit it by hand.

---

### `api_key_hash`

**Type:** string (bcrypt hash)
**Default:** `""`

Bcrypt hash of the generated API key for mobile/app authentication. Set automatically when a key is generated via **Settings → Authentication → Generate Key**. Clear it (or set `api_key_enabled: false`) to revoke access.

---

### `api_key_enabled`

**Type:** boolean
**Default:** `false`

Whether API key authentication is active. Requests with a valid `X-Api-Key` header bypass the session login flow when this is `true` and `api_key_hash` is set.

---

### `acme_json_path`

**Type:** string
**Default:** `""` (falls back to `ACME_JSON_PATH` env var, then `/app/acme.json`)

Path to Traefik's `acme.json` file inside the Traefik Manager container. When set here, it takes priority over the `ACME_JSON_PATH` environment variable and can be changed without restarting the container.

If Traefik stores `acme.json` in a Docker named volume, mount that volume into the Traefik Manager container in your `docker-compose.yml` first (this requires a one-time restart), then set the mounted path here or via the Settings UI - no further restart needed.

```yaml
# docker-compose.yml - mount Traefik's letsencrypt volume into TM
services:
  traefik-manager:
    volumes:
      - letsencrypt:/letsencrypt:ro

volumes:
  letsencrypt:
```

```yaml
# manager.yml
acme_json_path: /letsencrypt/acme.json
```

---

### `access_log_path`

**Type:** string
**Default:** `""` (falls back to `ACCESS_LOG_PATH` env var, then `/app/logs/access.log`)

Path to Traefik's access log file for the Logs tab. When set here, takes priority over the `ACCESS_LOG_PATH` environment variable. Configure via **Settings → File Paths → Access Log Path**.

```yaml
access_log_path: /var/log/traefik/access.log
```

---

### `static_config_path`

**Type:** string
**Default:** `""` (falls back to `STATIC_CONFIG_PATH` env var, then `/app/traefik.yml`)

Path to Traefik's static configuration file for the Plugins tab. When set here, takes priority over the `STATIC_CONFIG_PATH` environment variable. Configure via **Settings → File Paths → Static Config Path**.

```yaml
static_config_path: /etc/traefik/traefik.yml
```

---

### `oidc_enabled`

**Type:** boolean
**Default:** `false`

Whether OIDC login is active. When `true`, a "Sign in with [oidc_display_name]" button appears on the login page. Managed via **Settings → Authentication → OIDC / SSO Login**.

---

### `oidc_provider_url`

**Type:** string (URL)
**Default:** `""`

Base URL of the OIDC provider, without the `/.well-known/openid-configuration` suffix. Examples: `https://accounts.google.com`, `https://keycloak.example.com/realms/myrealm`.

---

### `oidc_client_id`

**Type:** string
**Default:** `""`

The client ID registered with your OIDC provider.

---

### `oidc_client_secret`

**Type:** string (Fernet-encrypted)
**Default:** `""`

The client secret. **Stored encrypted at rest** using the same Fernet key as `otp_secret`. Never store or share the plaintext value - always set it through the Settings UI.

---

### `oidc_display_name`

**Type:** string
**Default:** `"OIDC"`

Label shown on the login button: "Sign in with [display name]". Set to your provider's name for clarity, e.g. `Keycloak` or `Google`.

---

### `oidc_allowed_emails`

**Type:** string (comma-separated)
**Default:** `""` (allow any verified account)

Comma-separated list of email addresses allowed to log in via OIDC. Leave empty to allow any account that authenticates successfully with the provider.

---

### `oidc_allowed_groups`

**Type:** string (comma-separated)
**Default:** `""` (skip group check)

Comma-separated list of group names. At least one must match a group in the user's token. Leave empty to skip the group check.

---

### `oidc_groups_claim`

**Type:** string
**Default:** `"groups"`

The claim name in the userinfo response that contains the user's groups. Varies by provider: Keycloak uses `groups`, some providers use `roles`.

---

### `visible_tabs`

**Type:** map of string → boolean
**Default:** all `false`

Controls which optional tabs are shown in the navigation. Managed via the setup wizard or **Settings → Route Monitoring / System Monitoring**.

| Key | Tab |
|-----|-----|
| `docker` | Docker provider |
| `kubernetes` | Kubernetes provider |
| `swarm` | Docker Swarm provider |
| `nomad` | Nomad provider |
| `ecs` | Amazon ECS provider |
| `consulcatalog` | Consul Catalog provider |
| `redis` | Redis KV provider |
| `etcd` | etcd KV provider |
| `consul` | Consul KV provider |
| `zookeeper` | ZooKeeper KV provider |
| `http_provider` | HTTP Provider |
| `file_external` | File provider (external) |
| `certs` | SSL Certificates monitoring |
| `plugins` | Plugins monitoring |
| `logs` | Access logs |

---

## Bypassing the setup wizard

Pre-create `manager.yml` in your config volume before the first container start:

**1. Generate a bcrypt password hash**

```bash
python3 -c "import bcrypt; print(bcrypt.hashpw(b'yourpassword', bcrypt.gensalt()).decode())"
```

**2. Create the file**

```yaml
domains:
  - yourdomain.com
cert_resolver: cloudflare
traefik_api_url: http://traefik:8080
password_hash: "$2b$12$..."
setup_complete: true
must_change_password: false
```

**3. Start the container**

The wizard and the auto-generated password are both skipped. Log in immediately with the password you hashed above.
