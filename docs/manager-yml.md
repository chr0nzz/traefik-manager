# manager.yml Reference

`manager.yml` is Traefik Manager's settings file, stored at `/app/config/manager.yml` by default (override with [`SETTINGS_PATH`](env-vars.md)).

::: info
You don't normally need to edit this file by hand - all settings are managed through the **Settings** panel in the UI. This page is a reference for advanced use, scripted deployments, or bypassing the setup wizard.
:::

## Companion files

TM stores some data in separate files alongside `manager.yml` in the same config directory:

| File                        | Contents                                                                                                                        |
| -----------------------------| ---------------------------------------------------------------------------------------------------------------------------------|
| `manager.yml`               | All TM settings - auth, domains, tabs, webhooks, OIDC, git backup, CrowdSec, disabled routes                                    |
| `agents.yml`                | Remote agent registrations (encrypted API keys). Auto-created and migrated from `manager.yml` on first start after v1.5.0       |
| `templates.yml`             | Custom middleware templates created from the Middlewares tab toolbar                                                            |
| `notifications.yml`         | Recent notification history, capped at the 200 newest entries                                                                   |
| `notifications.yml.lock`    | Empty lock file that keeps the workers from overwriting each other's notifications. Safe to delete while TM is stopped          |
| `notifications.yml.next_id` | The next notification id, so ids are never reused after a clear. Safe to delete while TM is stopped                             |
| `notification_queue.json`   | What a digest or quiet-hours window is holding, up to 500 per channel. Safe to delete while TM is stopped                        |
| `dashboard.yml`             | Dashboard custom groups and per-card overrides, kept per server                                                                 |
| `.secret_key`, `.otp_key`   | Auto-generated session key and the Fernet key for every encrypted field below. Lose `.otp_key` and those secrets are unreadable |

None of these need to be edited by hand. Back up the entire config directory to preserve all TM state.

---

## Hand-written secrets

Encrypted fields are marked **Fernet-encrypted** below. You can write any of them in plain text and TM will read the value as written. On the next start TM encrypts it in place and raises a Security notification saying it did.

| You write | TM does |
| ---| ---|
| `oidc_client_secret: my-secret` | Reads `my-secret`, rewrites the key encrypted on next start |
| `oidc_client_secret: gAAAAA...` | Decrypts it, leaves the file alone |
| A value encrypted with a different `.otp_key` | Reads it as empty and logs a warning |

`agents.yml` works the same way, so a hand-written `api_key`, `crowdsec_api_key`, `crowdsec_machine_password` or `git_backup_token` is read and then encrypted.

The rewrite needs the config directory to be writable. If it is not, the plain text keeps working and TM keeps the file as it is.

Prefer [environment variables](env-vars.md) for scripted deployments: `OIDC_CLIENT_SECRET` and the other `OIDC_*` variables never put the secret in the file in the clear.

---

## Example

```yaml
domains:
  - example.com
  - example.net
cert_resolver: cloudflare
traefik_api_url: http://traefik:8080
traefik_api_user: ""
traefik_api_password: ""
acme_json_path: ""
access_log_path: ""
static_config_path: ""
auth_enabled: true
password_hash: "$2b$12$..."
must_change_password: false
setup_password_reset: false
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
oidc_allow_any_authenticated: false
oidc_auto_login: false
notification_channels: []
webhook_url: ""
webhook_type: "discord"
webhook_username: ""
webhook_password: ""
default_theme: "dark"
ui_prefs: {}
geoip_enabled: false
geoip_db_path: ""
backup_keep_count: 0
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
  tls: false
  crowdsec: false
  plugins: false
  logs: true
  static: false
disabled_routes: {}
managed_middlewares: {}
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

### `traefik_api_user` / `traefik_api_password`

**Type:** string - **Default:** `""` - **Env:** `TRAEFIK_API_USER` / `TRAEFIK_API_PASSWORD`

HTTP Basic Auth credentials for the Traefik API, needed only when it sits behind basic auth. Both are required together. The password is stored encrypted. Set via **Settings - Connection**.

---

## Authentication

### `auth_enabled`

**Type:** boolean - **Default:** `true` - **Env:** `AUTH_ENABLED`

Set to `false` when TM is protected by an external auth provider (Authentik, Authelia, etc.).

```yaml
auth_enabled: false
```

::: warning
When `false` and OIDC is also disabled, the UI is fully open (TM logs a SECURITY warning at startup). If `oidc_enabled` is `true`, OIDC login is still enforced. Only disable behind another auth layer.
:::

---

### `auth_external_ack`

**Type:** boolean - **Default:** `false`

Confirms the open-UI state above is deliberate. When `true` the startup SECURITY warning becomes an informational line. Set by **Acknowledge and hide** in Settings - Authentication.

---

### `password_hash`

**Type:** string (bcrypt hash) - **Default:** `""`

Managed by the UI (Settings - Authentication) or the [CLI reset command](reset-password.md). Left empty, TM generates a random password on first start and prints it to the container log. To generate a hash manually:

```bash
python3 -c "import bcrypt; print(bcrypt.hashpw(b'yourpassword', bcrypt.gensalt()).decode())"
```

---

### `must_change_password`

**Type:** boolean - **Default:** `false`

When `true`, the user is redirected to a forced password-change screen after login. Set automatically by the CLI reset command when run with no password option.

---

### `setup_password_reset`

**Type:** boolean - **Default:** `false`

When `true`, opening Traefik Manager asks for a new password and nothing else - the setup wizard is
skipped and the rest of `manager.yml` is left alone. While it is `true` that page is open to anyone who
can reach Traefik Manager, so use it promptly. It clears on any password change and on the next
successful login. Set by the CLI reset command when run with no password option, or by hand to recover
from a lost password (see [Reset Password](/reset-password#method-3-manual-reset-via-manager-yml)).

---

### `setup_complete`

**Type:** boolean - **Default:** `false`

Set to `true` automatically at the end of the setup wizard. Pre-set to `true` to skip the wizard entirely (see [Bypassing the setup wizard](#bypassing-the-setup-wizard)).

---

## Two-Factor Authentication

### `otp_enabled`

**Type:** boolean - **Default:** `false`

Whether TOTP 2FA is active. Managed via **Settings - Authentication - Two-factor**.

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
    hash: "sha256:3f9a..."
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

The client secret. Stored encrypted at rest. Set it in the Settings UI, with `OIDC_CLIENT_SECRET`, or in plain text here - see [Hand-written secrets](#hand-written-secrets).

---

### `oidc_display_name`

**Type:** string - **Default:** `"OIDC"`

Label on the login button: "Sign in with [display name]".

---

### `oidc_allowed_emails`

**Type:** string (comma-separated) - **Default:** `""`

Restrict login to specific email addresses. Leaving this **and** `oidc_allowed_groups` empty denies all OIDC logins unless `oidc_allow_any_authenticated` is `true`.

---

### `oidc_allowed_groups`

**Type:** string (comma-separated) - **Default:** `""` (skip check)

At least one group must match. Leave empty to skip group enforcement.

---

### `oidc_allow_any_authenticated`

**Type:** boolean - **Default:** `false`

Allow every account the provider authenticates, with no email or group allowlist. Set in **Settings - Authentication - OIDC / SSO - Access Control**.

---

### `oidc_groups_claim`

**Type:** string - **Default:** `"groups"`

The claim name in the userinfo response that contains groups. Varies by provider (Keycloak: `groups`, some use `roles`).

---

### `oidc_auto_login`

**Type:** boolean - **Default:** `false`

Redirect straight to the provider instead of showing the login page. Append `?auto=0` to the login URL to reach the password form.

---

## Notifications

### `notification_channels`

**Type:** list - **Default:** `[]`

Notification destinations, each with its own type, credentials, filters and schedule. Managed via **Settings - Notifications**. See [Notifications](webhooks.md) for setup.

| Key | Type | Notes |
|---|---|---|
| `id` | string | Generated, e.g. `ch_1a2b3c4d` |
| `name` | string | Label shown in the UI |
| `kind` | string | `discord`, `slack`, `ntfy`, `unifiedpush`, `generic`, `gotify`, `pushover`, `pushbullet`, `telegram` |
| `enabled` | boolean | Default `true` |
| `url` | string | Webhook, topic or server URL |
| `token` | string (Fernet-encrypted) | Gotify app token, Pushover app token, Pushbullet access token, Telegram bot token |
| `token2` | string (Fernet-encrypted) | Pushover user key, Telegram chat ID |
| `username` | string | Basic auth username for ntfy or generic |
| `password` | string (Fernet-encrypted) | Basic auth password for ntfy or generic |
| `categories` | list | Any of `config`, `backup`, `security`, `traefik`, `certs`, `crowdsec`, `agent`, `update`. Empty means all |
| `min_severity` | string | `info`, `success`, `warning` or `error`. Default `info` |
| `digest` | string | `immediate`, `hourly` or `daily`. Default `immediate` |
| `quiet_hours` | string | `HH:MM-HH:MM`, e.g. `22:00-07:00`. Empty means always on |
| `break_through` | boolean | Send `error` messages during quiet hours. Default `false` |

```yaml
notification_channels:
  - id: ch_1a2b3c4d
    name: Phone
    kind: telegram
    enabled: true
    url: ""
    token: "gAAAAAB..."
    token2: "gAAAAAB..."
    categories:
      - security
      - traefik
    min_severity: warning
    digest: immediate
    quiet_hours: "22:00-07:00"
    break_through: true
```

Entries with an unknown `kind` are dropped when the file is loaded. Secrets are encrypted at rest - always set them through the UI.

---

### `webhook_url` / `webhook_type` / `webhook_username` / `webhook_password`

**Type:** string - **Default:** `""`, `"discord"`, `""`, `""`

The single webhook from before v1.12.0. Still read, and migrated on first start into a channel named **Webhook** when `notification_channels` is absent. Once channels exist these keys are ignored.

---

## File Paths

These can be changed without a container restart via **Settings - System Monitoring - File Paths**. The UI setting takes priority over the env var.

### `acme_json_path`

**Type:** string - **Default:** `""` (falls back to `ACME_JSON_PATH`, then `/app/acme.json`)

Path to Traefik's `acme.json` inside the TM container. Required for the Certificates tab.

Accepts several files comma-separated, or a directory whose `.json` files are all read - useful when you run more than one cert resolver, since Traefik gives each its own storage file.

```yaml
acme_json_path: /letsencrypt/acme.json
acme_json_path: /letsencrypt/ovh.json, /letsencrypt/lan.json
acme_json_path: /letsencrypt
```

---

### `access_log_path`

**Type:** string - **Default:** `""` (falls back to `ACCESS_LOG_PATH`, then `/app/logs/access.log`)

Path to Traefik's access log. Required for the Logs tab.

```yaml
access_log_path: /var/log/traefik/access.log
```

---

### `static_config_path`

**Type:** string - **Default:** `""` (falls back to `STATIC_CONFIG_PATH`; there is no built-in default path)

Path to Traefik's static config. Required for the Plugins tab and Static Config editor - both stay unconfigured while this and the env var are empty.

```yaml
static_config_path: /etc/traefik/traefik.yml
```

---

## Backups

### `backup_keep_count`

**Type:** integer - **Default:** `0` (keep all) - **Env:** `BACKUP_KEEP_COUNT`

How many timestamped `.bak` files to keep per config file. Set in **Settings - Backups**.

---

## UI & Tabs

### `default_theme`

**Type:** string - **Default:** `dark`

The default theme for the UI and the login page. One of `dark`, `light`, or `system` (follows the OS preference). Set by the theme toggle in the nav bar or in **Settings - Interface - Appearance**.

```yaml
default_theme: light
```

### `ui_prefs`

**Type:** map - **Default:** `{}`

Display preferences, stored here rather than in the browser so they follow you across browsers, devices and private windows. Set by the toggles in **Settings - Interface** and by the card/list buttons on the Routes, Middlewares and Services tabs. Managed automatically; there is no need to edit it by hand.

| Key | Values | Default |
|---|---|---|
| `showStatCards`, `compactStatCards`, `showEntrypoints` | boolean | `true`, `false`, `true` |
| `layoutMode` | `fluid` \| `fixed` | `fluid` - fills the screen, or capped width |
| `staticPlacement` | `off` \| `settings` \| `tab` | Where the Static Config editor lives. Unset follows `visible_tabs.static` |
| `dashPodDensity` | `list` \| `icons` | `list` - dashboard categories as rows with domains, or a compact grid of app icons |
| `statBarScope` | `all` \| `dashboard` | Which tabs show the stat cards and entry points. `all` (default) means Dashboard, Routes, Middlewares and Services; `dashboard` limits them to the Dashboard tab. Only these two values are stored - any other value (including `none` or a comma-separated list) is discarded when the file is loaded. |
| `logsAutoRefresh` | boolean | `false` - poll the access log while the Logs tab is open and visible |
| `showDocsLink`, `showApiLink`, `showShortcutsBtn`, `showIpDiagBtn` | boolean | `true`, `false`, `true`, `true` |
| `showTraefikBadge`, `showTmBadge`, `showRouteIcons` | boolean | `true`, `true`, `false` |
| `routeViewMode`, `mwViewMode`, `svcViewMode` | `grid` \| `list` | `grid` |
| `staticOpenSections`, `settingsOpenSections` | list | Which accordion sections were left open |

```yaml
ui_prefs:
  showApiLink: true
  compactStatCards: true
  svcViewMode: list
```

Unknown keys are dropped rather than stored. A few things stay in the browser deliberately, because they describe that device rather than a preference: the active server, dismissed notices, and notification read markers.

---

### `geoip_enabled`

**Type:** boolean - **Default:** `false`

Enables [IP geolocation](geoip.md) - country flags and a world map in the Logs and CrowdSec tabs. Toggle in **Settings - Interface - Geolocation**.

```yaml
geoip_enabled: true
```

### `geoip_db_path`

**Type:** string - **Default:** `""` (auto-download DB-IP Lite) - **Env:** `GEOIP_DB_PATH`

Path to a custom GeoIP `.mmdb` database. Leave empty to use the free DB-IP Lite country database TM downloads automatically.

```yaml
geoip_db_path: /data/GeoLite2-Country.mmdb
```

### `visible_tabs`

**Type:** map of string - boolean - **Default:** all `false`

Controls which optional tabs are shown. Managed via the setup wizard, **Settings - Route Monitoring** (providers), **Settings - System Monitoring** (certs, plugins, logs, CrowdSec) and **Settings - Interface - Tabs** (dashboard, routemap, tls, static).

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
| `tls` | TLS Options tab |
| `crowdsec` | CrowdSec tab |
| `plugins` | Plugins tab |
| `logs` | Logs tab |
| `static` | Static Config tab - kept in step with `ui_prefs.staticPlacement` |

---

### `notifications_read_until`

**Type:** integer - **Default:** `0`

Epoch seconds of the last time notifications were marked read, so the unread badge survives a restart. Set by the bell menu; do not edit by hand.

---

## Route State

### `disabled_routes`

**Type:** map - **Default:** `{}`

Stores the full config of disabled routes so they can be re-enabled without data loss. Managed automatically by the enable/disable toggle. Do not edit by hand. An agent's snapshots are keyed `agent_<id>::` and are removed when that agent is removed.

---

### `managed_middlewares`

**Type:** map - **Default:** `{}`

Ownership ledger for the middlewares and `serversTransports` that traefik-manager generated on your behalf. Each entry records that the tool created it, so it will only ever update or remove what it owns, and refuses to overwrite a same-named entry you wrote by hand. Managed automatically; do not edit by hand.

| Key | What it owns |
|---|---|
| `<route>-headers` | The middleware created by the [Security headers preset](./tab-routes#security-headers-preset) |
| `tp::<name>` | A generated `serversTransport`. Written whenever a route needs one, including Skip TLS verification as well as the streaming preset |
| `svc::<name>` | A composite service ([Services tab](./tab-services)) - the parent, and one entry per generated `<name>-backend-<n>` child. The entry records the type and child list, and ownership only holds while the file still matches it, so a hand edit or a restore makes the service read only instead of being overwritten |
| `agent_<id>::...` | The same, on a remote agent - each server is tracked separately |

Deleting a route removes the `<service>-transport` it owns and its ledger entry, unless another service or a disabled route still references it. Removing an agent drops every `agent_<id>::` entry.

```yaml
managed_middlewares:
  jellyfin-headers:
    kind: route-headers
    route: jellyfin
```

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

## CrowdSec and Git backup

These sections are documented on their own pages. All are set through the UI and stored here; the secrets are Fernet-encrypted.

| Keys | Set in | Reference |
|---|---|---|
| `crowdsec_lapi_url`, `crowdsec_api_key`, `crowdsec_machine_id`, `crowdsec_machine_password`, `crowdsec_client_cert`, `crowdsec_client_key`, `crowdsec_ca_cert`, `crowdsec_alert_limit` | Settings - System Monitoring - CrowdSec | [CrowdSec tab](tab-crowdsec.md) |
| `git_backup_enabled`, `git_backup_repo`, `git_backup_branch`, `git_backup_username`, `git_backup_token`, `git_backup_commit_message`, `git_backup_auto_push` | Settings - Backups - Git | [Git Backup](git-backup.md) |

`crowdsec_read_timeout` is read from this file if you add it by hand, but TM never writes it - the next Settings save drops it. Use [`CROWDSEC_READ_TIMEOUT`](env-vars.md) instead.

`agent_api_rate_limit` is stored here but not enforced in this release. Registered agents live in `agents.yml`, not in this file.

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
