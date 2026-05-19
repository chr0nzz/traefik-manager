# manager.yml Reference

`manager.yml` is Traefik Manager's settings file, stored at `/app/config/manager.yml` by default (override with [`SETTINGS_PATH`](env-vars.md)).

::: info
You don't normally need to edit this file by hand - all settings are managed through the **Settings** panel in the UI. This page is a reference for advanced use, scripted deployments, or bypassing the setup wizard.
:::

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
api_key_enabled: false
api_keys: []
oidc_enabled: false
oidc_provider_url: ""
oidc_client_id: ""
oidc_client_secret: ""
oidc_display_name: "OIDC"
oidc_allowed_emails: ""
oidc_allowed_groups: ""
oidc_groups_claim: "groups"
webhook_url: ""
webhook_type: "discord"
webhook_username: ""
webhook_password: ""
visible_tabs:
  dashboard: false
  routemap: false
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
disabled_routes: {}
self_route:
  domain: ""
  service_url: ""
```

---

## Connection

### `domains`

**Type:** list - **Default:** `["example.com"]` - **Env:** `DOMAINS`

Base domains shown as options in the Add Route form.

```yaml
domains:
  - example.com
  - home.lab
```

---

### `cert_resolver`

**Type:** string - **Default:** `"cloudflare"` - **Env:** `CERT_RESOLVER`

One or more ACME cert resolver names, comma-separated. The first is the default for new routes. Set to `none` if you manage certificates externally.

```yaml
cert_resolver: cloudflare
cert_resolver: letsencrypt, cloudflare
cert_resolver: none
```

---

### `traefik_api_url`

**Type:** string (URL) - **Default:** `"http://traefik:8080"` - **Env:** `TRAEFIK_API_URL`

Internal URL of the Traefik API. Must be reachable from inside the TM container.

```yaml
traefik_api_url: http://traefik:8080
```

---

## Authentication

### `auth_enabled`

**Type:** boolean - **Default:** `true` - **Env:** `AUTH_ENABLED`

Set to `false` when TM is protected by an external auth provider (Authentik, Authelia, etc.).

```yaml
auth_enabled: false
```

::: warning
When `false`, the UI is fully open. Only disable behind another auth layer.
:::

---

### `password_hash`

**Type:** string (bcrypt hash) - **Default:** auto-generated

Managed by the UI (Settings - Authentication) or the [CLI reset command](reset-password.md). To generate manually:

```bash
python3 -c "import bcrypt; print(bcrypt.hashpw(b'yourpassword', bcrypt.gensalt()).decode())"
```

---

### `must_change_password`

**Type:** boolean - **Default:** `false`

When `true`, the user is redirected to a forced password-change screen after login. Set automatically by the CLI reset command.

---

### `setup_complete`

**Type:** boolean - **Default:** `false`

Set to `true` automatically at the end of the setup wizard. Pre-set to `true` to skip the wizard entirely (see [Bypassing the setup wizard](#bypassing-the-setup-wizard)).

---

## Two-Factor Authentication

### `otp_enabled`

**Type:** boolean - **Default:** `false`

Whether TOTP 2FA is active. Managed via **Settings - Authentication - 2FA**.

---

### `otp_secret`

**Type:** string (Fernet-encrypted) - **Default:** `""`

The TOTP secret, encrypted at rest. Generated when 2FA is enabled, cleared when disabled. Do not edit by hand.

---

## API Keys

### `api_key_enabled`

**Type:** boolean - **Default:** `false`

Whether API key authentication is active. When `true`, requests with a valid `X-Api-Key` header bypass the session login. Set automatically when any key exists.

---

### `api_keys`

**Type:** list - **Default:** `[]`

List of active API keys. Each entry contains `name`, `hash`, `preview`, and `created_at`. Managed via **Settings - Authentication - API Keys**. Up to 10 keys can exist.

```yaml
api_keys:
  - name: My Phone
    hash: "$2b$12$..."
    preview: "abcd1234...ef56"
    created_at: "2026-04-03 12:00"
```

---

## OIDC / SSO

### `oidc_enabled`

**Type:** boolean - **Default:** `false`

When `true`, a "Sign in with [display name]" button appears on the login page.

---

### `oidc_provider_url`

**Type:** string - **Default:** `""`

Base URL of the OIDC provider, without the `/.well-known/openid-configuration` suffix.

```yaml
oidc_provider_url: https://accounts.google.com
oidc_provider_url: https://keycloak.example.com/realms/myrealm
```

---

### `oidc_client_id`

**Type:** string - **Default:** `""`

The client ID registered with your OIDC provider.

---

### `oidc_client_secret`

**Type:** string (Fernet-encrypted) - **Default:** `""`

The client secret. Stored encrypted at rest. Always set through the Settings UI, never edit by hand.

---

### `oidc_display_name`

**Type:** string - **Default:** `"OIDC"`

Label on the login button: "Sign in with [display name]".

---

### `oidc_allowed_emails`

**Type:** string (comma-separated) - **Default:** `""` (allow any)

Restrict login to specific email addresses. Leave empty to allow any authenticated account.

---

### `oidc_allowed_groups`

**Type:** string (comma-separated) - **Default:** `""` (skip check)

At least one group must match. Leave empty to skip group enforcement.

---

### `oidc_groups_claim`

**Type:** string - **Default:** `"groups"`

The claim name in the userinfo response that contains groups. Varies by provider (Keycloak: `groups`, some use `roles`).

---

## Notification Webhooks

### `webhook_url`

**Type:** string - **Default:** `""`

The URL to POST notification payloads to. See [Notification Webhooks](webhooks.md) for full setup details.

---

### `webhook_type`

**Type:** string - **Default:** `"discord"`

Controls the payload format. One of: `discord`, `slack`, `ntfy`, `generic`.

---

### `webhook_username`

**Type:** string - **Default:** `""`

Optional basic auth username for ntfy or generic endpoints.

---

### `webhook_password`

**Type:** string (Fernet-encrypted) - **Default:** `""`

Optional basic auth password. Stored encrypted at rest. Do not edit by hand.

---

## File Paths

These can be changed without a container restart via **Settings - Connection**. The UI setting takes priority over the env var.

### `acme_json_path`

**Type:** string - **Default:** `""` (falls back to `ACME_JSON_PATH` env var, then `/app/acme.json`)

Path to Traefik's `acme.json` inside the TM container. Required for the Certificates tab.

```yaml
acme_json_path: /letsencrypt/acme.json
```

---

### `access_log_path`

**Type:** string - **Default:** `""` (falls back to `ACCESS_LOG_PATH` env var, then `/app/logs/access.log`)

Path to Traefik's access log. Required for the Logs tab.

```yaml
access_log_path: /var/log/traefik/access.log
```

---

### `static_config_path`

**Type:** string - **Default:** `""` (falls back to `STATIC_CONFIG_PATH` env var, then `/app/traefik.yml`)

Path to Traefik's static config. Required for the Plugins tab and Static Config editor.

```yaml
static_config_path: /etc/traefik/traefik.yml
```

---

## UI & Tabs

### `visible_tabs`

**Type:** map of string - boolean - **Default:** all `false`

Controls which optional tabs are shown. Managed via the setup wizard or **Settings - System Monitoring / Route Monitoring**.

| Key | Tab |
|---|---|
| `dashboard` | Dashboard tab |
| `routemap` | Route Map tab |
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
| `http_provider` | HTTP provider |
| `file_external` | File provider (external) |
| `certs` | Certificates tab |
| `plugins` | Plugins tab |
| `logs` | Logs tab |

---

## Route State

### `disabled_routes`

**Type:** map - **Default:** `{}`

Stores the full config of disabled routes so they can be re-enabled without data loss. Managed automatically by the enable/disable toggle. Do not edit by hand.

---

## Self Route

### `self_route`

**Type:** map - **Default:** `{domain: "", service_url: ""}`

Stores TM's own Traefik route so it can be managed from within the UI. Set via **Settings - Connection - Self Route**.

```yaml
self_route:
  domain: manager.example.com
  service_url: http://traefik-manager:5000
  router_name: traefik-manager
  entry_point: websecure
```

---

## Bypassing the Setup Wizard

Pre-create `manager.yml` in your config volume before the first container start:

**1. Generate a password hash**

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

The wizard and auto-generated password are skipped. Log in immediately with the password you hashed above.
