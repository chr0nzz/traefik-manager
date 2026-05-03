# API Reference

Traefik Manager exposes a REST API used by the web UI and official mobile app.

::: tip Interactive reference
Every TM instance has a built-in API reference with live **Try It** support at `/api` (or click **API** in the navbar). Requests are sent to your own instance with your session already authenticated - no extra setup needed.
:::

---

## Authentication

**API key** *(recommended)* - generate a key in **Settings → Authentication → API Keys** and pass it as a header. API keys bypass CSRF checks entirely.

```
X-Api-Key: your-api-key
```

**Session cookie** - log in via the web UI. The browser session cookie is used automatically.

---

## Response format

All endpoints return JSON.

| Outcome | Shape |
|---|---|
| Success | `{ "ok": true }` or `{ "success": true }` |
| Error | `{ "ok": false, "message": "..." }` or `{ "error": "..." }` |

State-changing endpoints (POST / DELETE) require an `X-CSRF-Token` header when using session auth. API key requests skip this.

---

## Routes & Middlewares

### `GET /api/routes`

Get all managed routes and middlewares from all loaded config files.

**Response**

```json
{
  "apps": [ /* Route[] */ ],
  "middlewares": [ /* Middleware[] */ ]
}
```

When multiple config files are loaded, route `id` is prefixed as `configFile::name`. Strip the prefix before using the name as a YAML key.

**Route object**

| Field | Type | Description |
|---|---|---|
| `id` | string | Unique identifier |
| `name` | string | Router/service name |
| `enabled` | boolean | |
| `protocol` | string | `http`, `tcp`, or `udp` |
| `rule` | string | Traefik rule expression |
| `target` | string | Backend URL |
| `middlewares` | string[] | Applied middleware names |
| `tls` | boolean | |
| `certResolver` | string | ACME resolver name, or empty for external certs |
| `configFile` | string | Source config file |

---

### `POST /save`

Create or update a route. Accepts `application/x-www-form-urlencoded`.

| Field | Type | Description |
|---|---|---|
| `serviceName` | string | Route name |
| `subdomain` | string | Hostname (e.g. `app.example.com`) |
| `targetIp` | string | Backend host |
| `targetPort` | string | Backend port |
| `protocol` | string | `http`, `tcp`, or `udp` |
| `middlewares` | string | Comma-separated middleware names |
| `scheme` | string | `http` or `https` (default: `http`) |
| `passHostHeader` | boolean | Default: `true` |
| `certResolver` | string | ACME resolver name. Use `none` to write `tls: {}` with no resolver (external certs). |
| `configFile` | string | Target config file (multi-config only) |
| `isEdit` | boolean | `true` when updating an existing route |
| `originalId` | string | Original route ID when renaming |

---

### `POST /delete/{route_id}`

Delete a route by ID. Accepts `application/x-www-form-urlencoded`.

| Param | Description |
|---|---|
| `route_id` | Route ID (path) |
| `configFile` | Config file basename (body, multi-config only) |

---

### `POST /api/routes/{route_id}/toggle`

Enable or disable a route without deleting it. Config is preserved in `manager.yml`.

```json
{ "enable": true }
```

---

### `GET /api/configs`

List all loaded dynamic config files.

```json
{
  "files": [{ "label": "routes.yml", "path": "/config/routes.yml" }],
  "configDirSet": true
}
```

---

### `POST /save-middleware`

Create or update a middleware. Config is provided as raw YAML. Accepts `application/x-www-form-urlencoded`.

| Field | Description |
|---|---|
| `middlewareName` | Middleware name |
| `middlewareContent` | Raw YAML body |
| `configFile` | Target config file |
| `isMwEdit` | `true` when updating |
| `originalMwId` | Original ID when renaming |

---

### `POST /delete-middleware/{name}`

Delete a middleware by name. Accepts `application/x-www-form-urlencoded`.

| Param | Description |
|---|---|
| `name` | Middleware name (path) |
| `configFile` | Config file basename (body, multi-config only) |

---

## Traefik

These endpoints proxy read-only data from the Traefik API. They require a valid Traefik API URL in settings.

### `GET /api/traefik/overview`

Router, service, and middleware counts plus Traefik feature flags. Passes through the Traefik dashboard overview object.

---

### `GET /api/traefik/routers`

All routers across HTTP, TCP, and UDP.

```json
{ "http": [...], "tcp": [...], "udp": [...] }
```

---

### `GET /api/traefik/services`

All services across HTTP, TCP, and UDP.

---

### `GET /api/traefik/middlewares`

All middlewares across HTTP and TCP.

---

### `GET /api/traefik/entrypoints`

All configured entrypoints.

```json
[{ "name": "websecure", "address": ":443" }]
```

---

### `GET /api/traefik/router/{protocol}/{name}`

Details for a specific router. `protocol` is `http`, `tcp`, or `udp`. `name` is URL-encoded.

---

### `GET /api/traefik/version`

Traefik version string and codename.

---

### `GET /api/traefik/ping`

Ping the Traefik API and return latency.

```json
{ "ok": true, "latency_ms": 3 }
```

---

### `GET /api/traefik/plugins`

List plugins defined under `experimental.plugins` in the static config. Requires `STATIC_CONFIG_PATH`.

---

### `GET /api/traefik/certs`

List TLS certificates from ACME (`acme.json`) and file-based (`tls.yml`) sources. Requires `ACME_JSON_PATH`.

| Field | Description |
|---|---|
| `resolver` | ACME resolver name |
| `main` | Primary domain |
| `sans` | Subject alternative names |
| `not_after` | Expiry timestamp (ISO 8601) |
| `certFile` | Source file |

---

### `GET /api/traefik/logs`

Tail Traefik access logs. Requires `ACCESS_LOG_PATH`.

| Query param | Default | Max |
|---|---|---|
| `lines` | `100` | `1000` |

---

## Dashboard

### `GET /api/dashboard/config`

Get saved dashboard configuration - custom groups and per-route icon/name overrides.

---

### `POST /api/dashboard/config`

Save dashboard configuration. Replaces the full config in `dashboard.yml`.

```json
{
  "custom_groups": [{ "name": "Media" }],
  "route_overrides": {
    "plex": { "display_name": "Plex", "icon_type": "slug", "icon_slug": "plex", "group": "Media" }
  }
}
```

`icon_type` is `auto`, `slug`, or `url`.

---

### `GET /api/dashboard/icon/{slug}`

Serve a cached app icon by slug (e.g. `plex`, `grafana`). Fetches from the selfh.st CDN on cache miss. Responses include `Cache-Control: max-age=86400`.

---

## Settings

### `GET /api/settings`

Get current application settings. Password hash is never included.

| Field | Description |
|---|---|
| `domains` | Allowed domains list |
| `cert_resolver` | Default ACME resolver name(s) |
| `traefik_api_url` | Traefik API base URL |
| `acme_json_path` | Path to `acme.json` inside the container |
| `access_log_path` | Path to Traefik access log |
| `static_config_path` | Path to `traefik.yml` |
| `auth_enabled` | Password auth on/off |
| `oidc_enabled` | OIDC on/off |
| `visible_tabs` | Tab visibility map |

---

### `POST /api/settings`

Update settings. Send only the fields you want to change.

---

### `GET /api/settings/self-route`

Get the saved self-route domain. If none is saved, TM scans config files for an existing route pointing to the TM service.

---

### `POST /api/settings/self-route`

Save or remove the self-route. Sending an empty `domain` deletes the self-route file.

```json
{ "domain": "manager.example.com", "service_url": "http://traefik-manager:5000" }
```

---

### `POST /api/settings/tabs`

Show or hide optional UI tabs.

```json
{ "dashboard": true, "routemap": true, "docker": false }
```

---

## Backups

### `GET /api/backups`

List all backup files, newest first.

```json
[{ "name": "backup_2026-03-24T22-00-00.yml", "size": 1024, "modified": "2026-03-24T22:00:00" }]
```

---

### `POST /api/backup/create`

Create a manual backup. Returns the backup filename.

---

### `POST /api/restore/{filename}`

Restore configuration from a backup file. Rate-limited to 10/min.

---

### `POST /api/backup/delete/{filename}`

Delete a backup file.

---

## Notifications

### `GET /api/notifications`

List all stored notifications, newest first.

```json
[{ "ts": "2026-04-13 20:25:03", "type": "route_saved", "msg": "Route my-app saved" }]
```

---

### `POST /api/notifications/delete`

Delete a single notification by timestamp.

```json
{ "ts": "2026-04-13 20:25:03" }
```

---

### `POST /api/notifications/clear`

Clear all notifications.

---

## Authentication endpoints

### `POST /api/auth/change-password`

Change the login password. Rate-limited to 10/min.

```json
{ "current_password": "...", "new_password": "...", "confirm_password": "..." }
```

---

### `POST /api/auth/toggle`

Enable or disable password authentication.

```json
{ "auth_enabled": false }
```

---

### `GET /api/auth/otp/status`

Check whether TOTP is enabled.

---

### `POST /api/auth/otp/setup`

Generate a TOTP secret and QR code URI for scanning with an authenticator app. Returns `secret` and `uri`.

---

### `POST /api/auth/otp/enable`

Confirm and activate TOTP using a code from the authenticator app.

```json
{ "code": "123456" }
```

---

### `POST /api/auth/otp/disable`

Disable TOTP.

---

### `GET /api/auth/apikey/status`

List active API keys. Full keys are never returned after generation.

```json
{
  "enabled": true,
  "count": 2,
  "keys": [{ "name": "My Phone", "preview": "abcd1234...ef56", "created_at": "2026-04-03 12:00" }]
}
```

---

### `POST /api/auth/apikey/generate`

Generate a new API key. Up to 10 keys can exist. Rate-limited to 5/hour. The full key is returned once - store it securely.

```json
{ "device_name": "My Phone" }
```

Response: `{ "ok": true, "key": "tm_abcdef123456..." }`

---

### `POST /api/auth/apikey/revoke`

Revoke an API key by its preview string.

```json
{ "preview": "abcd1234...ef56" }
```

---

### `GET /api/auth/oidc`

Get current OIDC configuration. Client secret is never returned.

---

### `POST /api/auth/oidc`

Save OIDC configuration. Leave `oidc_client_secret` blank to keep the existing secret.

| Field | Description |
|---|---|
| `oidc_enabled` | Enable or disable OIDC |
| `oidc_provider_url` | Provider base URL (without `/.well-known/...`) |
| `oidc_client_id` | Client ID |
| `oidc_client_secret` | Client secret (omit to keep existing) |
| `oidc_display_name` | Login button label |
| `oidc_allowed_emails` | Comma-separated allowed emails |
| `oidc_allowed_groups` | Comma-separated allowed groups |
| `oidc_groups_claim` | Claim name containing groups |

---

### `POST /api/auth/oidc/test`

Test connectivity to an OIDC provider's discovery endpoint.

```json
{ "provider_url": "https://accounts.google.com" }
```

---

## Static Config

Requires `STATIC_CONFIG_PATH` to be set. See [Enable Static Config](/static-enable).

### `GET /api/static/available`

Check whether the static config editor is available.

```json
{ "available": true }
```

---

### `GET /api/static/config`

Read and parse the current static config file.

```json
{ "raw": "...", "parsed": { ... }, "path": "/app/traefik.yml" }
```

---

### `POST /api/static/config`

Validate and write an updated static config. A timestamped backup is created before writing.

```json
{ "yaml": "entryPoints:\n  web:\n    address: ':80'\n" }
```

Returns `400` with `{ "error": "..." }` if the YAML is invalid.

---

### `POST /api/static/restart`

Trigger a Traefik restart using the configured `RESTART_METHOD`.

---

### `GET /api/static/status`

Check whether Traefik is currently up. Used by the reconnect overlay after a restart.

```json
{ "up": true }
```

---

### `POST /api/static/section`

Update a single named section of the static config without writing raw YAML.

```json
{
  "action": "add",
  "section": "entrypoints",
  "name": "websecure",
  "data": { "address": ":443" }
}
```

**Supported sections and actions**

| Section | Actions | `data` fields |
|---|---|---|
| `entrypoints` | `add`, `edit`, `remove` | `address`, `redirect_to` |
| `resolvers` | `add`, `edit`, `remove` | `email`, `storage`, `challenge_type`, `provider`, `http_entrypoint` |
| `plugins` | `add`, `edit`, `remove` | `moduleName`, `version` |
| `api` | `set` | `enabled`, `dashboard`, `insecure`, `debug` |
| `log` | `set` | `level`, `accessLog`, `accessLogPath` |
| `providers` | `set` | `docker`, `dockerEndpoint`, `dockerExposedByDefault`, `dockerWatch`, `file`, `fileDirectory`, `fileWatch` |
| `providers` | `add`, `edit`, `remove` | `name` = provider type key, `yaml_config` = YAML body |

Response includes the updated `raw` YAML and `parsed` object.

---

## Utility

### `GET /api/manager/version`

Get the deployed Traefik Manager version.

```json
{ "version": "1.0.0", "repo": "https://github.com/chr0nzz/traefik-manager" }
```

---

### `GET /api/manager/router-names`

Get all router names across every protocol. Useful for autocomplete.

```json
["my-app@file", "api@file"]
```

---

### `POST /api/setup/test-connection`

Test connectivity to a Traefik API URL. No authentication required.

```json
{ "url": "http://traefik:8080" }
```

---

## OpenAPI spec

The raw OpenAPI 3.1 spec is available from your instance at:

```
https://your-tm-url/openapi.yaml
```
