# API Reference

Traefik Manager exposes a REST API that powers the web UI and can be used to build integrations - the official mobile app uses it exclusively.

## Overview

All API endpoints are relative to your Traefik Manager base URL (e.g. `https://manager.example.com`).

### Authentication

Two methods are supported:

**Session cookie** - log in via the web UI. The browser session is used automatically for all subsequent requests.

**API key** - generate a key in **Settings → Authentication → API Key** and send it as a header:

```
X-Api-Key: your-api-key-here
```

API keys bypass CSRF checks, making them the right choice for scripts and apps.

### CSRF

State-changing endpoints (POST/DELETE) require a CSRF token when using session auth. The token is available in the web UI as a `<meta name="csrf-token">` tag. Send it as a header:

```
X-CSRF-Token: <token>
```

API key requests skip this requirement entirely.

### Rate limits

| Scope | Limit |
|---|---|
| Login, OTP verification | 5 / min per IP |
| OIDC login initiation | 10 / min per IP |
| Password change, OTP endpoints | 10 / min per IP |
| API key generation | 5 / hour per IP |
| All other endpoints | Unlimited |

### Response format

All API endpoints return JSON. Successful mutations return at minimum `{"ok": true}` or `{"success": true}`. Errors return `{"ok": false, "message": "..."}` or `{"error": "..."}` with an appropriate HTTP status code.

---

## Authentication endpoints

#### `POST /api/auth/change-password`

Change the login password.

**Auth:** Session · **CSRF:** required · **Rate limit:** 10/min

**Request**
```json
{
  "current_password": "old",
  "new_password": "new",
  "confirm_password": "new"
}
```

**Response**
```json
{ "success": true }
```

---

#### `POST /api/auth/toggle`

Enable or disable password authentication entirely.

**Auth:** Session · **CSRF:** required

**Request**
```json
{ "auth_enabled": true }
```

**Response**
```json
{ "success": true, "auth_enabled": true }
```

---

#### `GET /api/auth/otp/status`

Check whether TOTP two-factor authentication is enabled.

**Auth:** Session or API key

**Response**
```json
{ "otp_enabled": false }
```

---

#### `POST /api/auth/otp/setup`

Generate a TOTP secret and QR code URI for scanning with an authenticator app.

**Auth:** Session · **CSRF:** required

**Response**
```json
{
  "secret": "BASE32SECRET",
  "uri": "otpauth://totp/TraefikManager?secret=..."
}
```

---

#### `POST /api/auth/otp/enable`

Confirm and activate TOTP using a code from the authenticator app.

**Auth:** Session · **CSRF:** required

**Request**
```json
{ "code": "123456" }
```

**Response**
```json
{ "success": true }
```

---

#### `POST /api/auth/otp/disable`

Disable TOTP authentication.

**Auth:** Session · **CSRF:** required

**Response**
```json
{ "success": true }
```

---

#### `GET /api/auth/apikey/status`

List all active API keys. Returns names and previews - full keys are never returned after generation.

**Auth:** Session or API key

**Response**
```json
{
  "enabled": true,
  "count": 2,
  "keys": [
    { "name": "My Phone", "preview": "abcd1234...ef56", "created_at": "2026-04-03 12:00" },
    { "name": "Tablet", "preview": "wxyz5678...gh90", "created_at": "2026-04-04 09:15" }
  ]
}
```

---

#### `POST /api/auth/apikey/generate`

Generate a new API key for a named device. Up to 10 keys can exist at once.

**Auth:** Session · **CSRF:** required · **Rate limit:** 5/hour

**Request**
```json
{ "device_name": "My Phone" }
```

**Response**
```json
{ "ok": true, "key": "tm_abcdef123456..." }
```

The full key is returned once. Store it securely - it cannot be retrieved again.

---

#### `POST /api/auth/apikey/revoke`

Revoke a specific API key by its preview string.

**Auth:** Session · **CSRF:** required

**Request**
```json
{ "preview": "abcd1234...ef56" }
```

**Response**
```json
{ "ok": true }
```

---

#### `GET /api/auth/oidc`

Get current OIDC configuration. The client secret is never returned - `oidc_client_secret_set` indicates whether one is stored.

**Auth:** Session

**Response**
```json
{
  "oidc_enabled": false,
  "oidc_provider_url": "https://accounts.google.com",
  "oidc_client_id": "my-client-id",
  "oidc_client_secret_set": true,
  "oidc_display_name": "Google",
  "oidc_allowed_emails": "admin@example.com",
  "oidc_allowed_groups": "",
  "oidc_groups_claim": "groups"
}
```

---

#### `POST /api/auth/oidc`

Save OIDC configuration. Leave `oidc_client_secret` blank to keep the existing secret.

**Auth:** Session · **CSRF:** required

**Request**
```json
{
  "oidc_enabled": true,
  "oidc_provider_url": "https://accounts.google.com",
  "oidc_client_id": "my-client-id",
  "oidc_client_secret": "my-secret",
  "oidc_display_name": "Google",
  "oidc_allowed_emails": "admin@example.com",
  "oidc_allowed_groups": "",
  "oidc_groups_claim": "groups"
}
```

**Response**
```json
{ "ok": true }
```

---

#### `POST /api/auth/oidc/test`

Test connectivity to an OIDC provider's discovery endpoint.

**Auth:** Session · **CSRF:** required

**Request**
```json
{ "provider_url": "https://accounts.google.com" }
```

**Response**
```json
{ "ok": true, "issuer": "https://accounts.google.com" }
```

On error:
```json
{ "ok": false, "error": "Connection refused" }
```

---

## Traefik data

These endpoints proxy directly to the Traefik API and return live data. They are read-only.

#### `GET /api/traefik/overview`

Traefik dashboard overview - router/service/middleware counts, features, version.

**Auth:** Session or API key

---

#### `GET /api/traefik/routers`

All routers across HTTP, TCP, and UDP protocols.

**Auth:** Session or API key

**Response**
```json
{
  "http": [ { "name": "my-app@file", "rule": "Host(`app.example.com`)", ... } ],
  "tcp":  [ ... ],
  "udp":  [ ... ]
}
```

---

#### `GET /api/traefik/services`

All services across HTTP, TCP, and UDP protocols.

**Auth:** Session or API key

**Response**
```json
{
  "http": [ { "name": "my-app@file", "type": "loadbalancer", ... } ],
  "tcp":  [ ... ],
  "udp":  [ ... ]
}
```

---

#### `GET /api/traefik/middlewares`

All middlewares across HTTP and TCP.

**Auth:** Session or API key

**Response**
```json
{
  "http": [ { "name": "auth@file", "type": "basicauth", ... } ],
  "tcp":  [ ... ]
}
```

---

#### `GET /api/traefik/entrypoints`

All configured entrypoints.

**Auth:** Session or API key

**Response**
```json
[ { "name": "websecure", "address": ":443", ... } ]
```

---

#### `GET /api/traefik/version`

Traefik version info.

**Auth:** Session or API key

**Response**
```json
{ "Version": "3.2.0", "Codename": "...", "startDate": "..." }
```

---

#### `GET /api/traefik/ping`

Ping the Traefik API and return latency.

**Auth:** Session or API key

**Response**
```json
{ "ok": true, "latency_ms": 3 }
```

---

#### `GET /api/traefik/router/{protocol}/{name}`

Get details for a specific router.

**Auth:** Session or API key

**Path params:** `protocol` = `http` / `tcp` / `udp`, `name` = router name (URL-encoded)

---

#### `GET /api/traefik/plugins`

List plugins defined under `experimental.plugins` in the Traefik static config file. Reads from `STATIC_CONFIG_PATH` (default `/app/traefik.yml`).

**Auth:** Session or API key

**Response**
```json
{ "plugins": [ { "name": "...", "moduleName": "...", "version": "..." } ] }
```

On error (file not found or unreadable):
```json
{ "plugins": [], "error": "Static config not found at /app/traefik.yml. Set STATIC_CONFIG_PATH to override." }
```

---

#### `GET /api/traefik/certs`

List TLS certificates. Reads from two sources and merges results:

1. **ACME (`acme.json`)** - reads from the `acme_json_path` setting (if set), then the `ACME_JSON_PATH` env var, then the default `/app/acme.json`
2. **File-based (`tls.yml`)** - scans all loaded config files for `tls.certificates` entries and reads each `certFile` PEM directly

**Auth:** Session or API key

**Response**
```json
{
  "certs": [
    { "resolver": "cloudflare", "main": "example.com", "sans": ["*.example.com"], "not_after": "Apr 06 12:00:00 2027 GMT" },
    { "resolver": "file", "main": "internal.lan", "sans": [], "not_after": "Jan 01 00:00:00 2028 GMT", "certFile": "/etc/traefik/certs/chain.pem" }
  ]
}
```

`resolver` is the ACME resolver name for ACME certs, or `"file"` for PEM certs loaded from `tls.yml`.

---

#### `GET /api/traefik/logs`

Tail Traefik access logs. Reads from `ACCESS_LOG_PATH` (default `/app/logs/access.log`).

**Auth:** Session or API key

**Query params:** `lines` (1–1000, default 100)

**Response**
```json
{ "lines": ["192.168.1.1 - - [24/Mar/2026] ..."] }
```

On error:
```json
{ "lines": [], "error": "Access log not found at /app/logs/access.log. Set ACCESS_LOG_PATH to override." }
```

---

## Routes & middlewares

#### `GET /api/configs`

List all loaded dynamic config files.

**Auth:** Session or API key

**Response**
```json
{
  "files": [
    { "label": "routes.yml", "path": "/app/config/routes.yml" },
    { "label": "services.yml", "path": "/app/config/services.yml" }
  ],
  "configDirSet": true
}
```

`configDirSet` is `true` when `CONFIG_DIR` is set. The mobile app uses this to determine whether to show the "+ New file" option in add/edit forms.

---

#### `GET /api/routes`

Get all managed routes and middlewares from all loaded config files.

**Auth:** Session or API key

**Response**
```json
{
  "apps": [
    {
      "id": "my-app",
      "name": "my-app",
      "enabled": true,
      "protocol": "http",
      "rule": "Host(`app.example.com`)",
      "target": "http://192.168.1.10:8080",
      "middlewares": ["auth@file"],
      "tls": true,
      "certResolver": "letsencrypt",
      "passHostHeader": true,
      "configFile": "routes.yml"
    }
  ],
  "middlewares": [
    { "name": "auth", "type": "http", "yaml": "...", "configFile": "routes.yml" }
  ]
}
```

`configFile` is the basename of the config file the entry came from. Populated whenever `CONFIG_DIR` or `CONFIG_PATHS` is set, even with a single file.

`id` is prefixed as `configFile::name` when multiple config files are loaded (e.g. `routes.yml::my-app`), to avoid collisions across files. Strip the prefix before using the name as a YAML key.

---

#### `POST /api/routes/{route_id}/toggle`

Enable or disable a route without deleting it. The configuration is preserved in `manager.yml`.

**Auth:** Session or API key · **CSRF:** required (session only)

**Request**
```json
{ "enable": false }
```

**Response**
```json
{ "ok": true }
```

---

#### `POST /save`

Create a new route or update an existing one.

**Auth:** Session or API key · **CSRF:** required (session only)

**Request (form-encoded or JSON)**

| Field | Description |
|---|---|
| `serviceName` | Route/service name |
| `subdomain` | Hostname (e.g. `app.example.com`) |
| `targetIp` | Backend IP or hostname |
| `targetPort` | Backend port |
| `protocol` | `http`, `tcp`, or `udp` |
| `middlewares` | Comma-separated middleware names |
| `scheme` | Backend scheme: `http` or `https` (default `http`) |
| `passHostHeader` | `true` to forward original `Host` header (default `true`) |
| `certResolver` | ACME cert resolver name (HTTP/TCP with TLS only). Falls back to the first configured resolver when omitted. Pass `__none__` to use `tls: {}` without a resolver (for custom certs managed via `tls.yml`). |
| `configFile` | Basename of the target config file (multi-config only) |
| `isEdit` | `true` when updating an existing route |
| `originalId` | ID of the route being replaced (edit only) |

---

#### `POST /delete/{route_id}`

Delete a managed route.

**Auth:** Session or API key · **CSRF:** required (session only)

**Request (form-encoded)**

| Field | Description |
|---|---|
| `configFile` | Basename of the config file containing this route (multi-config only). Omit to search all files. |

---

#### `POST /save-middleware`

Create or update a middleware. Config is provided as raw YAML.

**Auth:** Session or API key · **CSRF:** required (session only)

**Request (form-encoded or JSON)**

| Field | Description |
|---|---|
| `middlewareName` | Middleware name |
| `middlewareContent` | YAML config body |
| `configFile` | Basename of the target config file (multi-config only) |
| `isMwEdit` | `true` when updating |
| `originalMwId` | Name of middleware being replaced (edit only) |

---

#### `POST /delete-middleware/{name}`

Delete a managed middleware.

**Auth:** Session or API key · **CSRF:** required (session only)

**Request (form-encoded)**

| Field | Description |
|---|---|
| `configFile` | Basename of the config file containing this middleware (multi-config only). Omit to search all files. |

---

## Dashboard

#### `GET /api/dashboard/config`

Get the saved Dashboard configuration - custom groups and per-route overrides.

**Auth:** Session or API key

**Response**
```json
{
  "custom_groups": [
    { "name": "My Apps", "keywords": ["myapp", "internal"] }
  ],
  "route_overrides": {
    "plex": {
      "display_name": "Plex Media Server",
      "icon_type": "slug",
      "icon_slug": "plex",
      "group": "Media"
    }
  }
}
```

---

#### `POST /api/dashboard/config`

Save the Dashboard configuration. Replaces the full config in `dashboard.yml`.

**Auth:** Session or API key · **CSRF:** required (session only)

**Request**
```json
{
  "custom_groups": [
    { "name": "My Apps", "keywords": ["myapp", "internal"] }
  ],
  "route_overrides": {
    "plex": { "display_name": "Plex", "icon_type": "auto" }
  }
}
```

**Response**
```json
{ "ok": true }
```

---

#### `GET /api/dashboard/icon/<slug>`

Serve a cached app icon by slug. On cache miss, fetches from the selfh.st CDN (`https://cdn.jsdelivr.net/gh/selfhst/icons/png/{slug}.png`) and stores it in `/config/cache/{slug}.png`. Subsequent requests are served from disk with a 24-hour browser cache (`Cache-Control: max-age=86400`).

**Auth:** Session or API key

**Path params:** `slug` - icon name (lowercase alphanumeric and hyphens only, e.g. `plex`, `grafana`, `home-assistant`)

**Response:** PNG image or `404` if the icon is not found on the CDN.

---

## Settings

#### `GET /api/settings`

Get current application settings. Password hash is never included.

**Auth:** Session or API key

**Response**
```json
{
  "domains": ["example.com"],
  "cert_resolver": "letsencrypt",
  "traefik_api_url": "http://traefik:8080",
  "acme_json_path": "",
  "access_log_path": "",
  "static_config_path": "",
  "auth_enabled": true,
  "oidc_enabled": false,
  "oidc_provider_url": "",
  "oidc_client_id": "",
  "oidc_client_secret_set": false,
  "oidc_display_name": "OIDC",
  "oidc_allowed_emails": "",
  "oidc_allowed_groups": "",
  "oidc_groups_claim": "groups",
  "visible_tabs": { "dashboard": true, "routemap": false, "docker": true, "kubernetes": false, ... }
}
```

`cert_resolver` is a comma-separated string when multiple resolvers are configured (e.g. `"letsencrypt, cloudflare"`). The first resolver is the default for new routes. `oidc_client_secret` is never returned; `oidc_client_secret_set` indicates whether one is stored.

---

#### `POST /api/settings`

Update application settings. `acme_json_path` overrides the `ACME_JSON_PATH` env var for the Certificates tab without a container restart.

**Auth:** Session or API key · **CSRF:** required (session only)

**Request**
```json
{
  "domains": ["example.com", "internal.lan"],
  "cert_resolver": "letsencrypt",
  "traefik_api_url": "http://traefik:8080",
  "acme_json_path": "/letsencrypt/acme.json",
  "access_log_path": "/var/log/traefik/access.log",
  "static_config_path": "/etc/traefik/traefik.yml"
}
```

---

#### `GET /api/settings/self-route`

Get the current self-route configuration. If no domain is saved, TM scans config files for an existing route pointing to the TM service and returns it with `"detected": true`.

**Auth:** Session or API key

**Response**
```json
{ "domain": "manager.example.com", "service_url": "http://traefik-manager:5000" }
```

---

#### `POST /api/settings/self-route`

Save or remove the self-route. When a domain is provided, TM writes `traefik-manager-self.yml` to the config directory. When domain is empty, the file is deleted.

**Auth:** Session or API key · **CSRF:** required (session only)

**Request**
```json
{ "domain": "manager.example.com", "service_url": "http://traefik-manager:5000" }
```

**Response**
```json
{ "ok": true }
```

---

#### `POST /api/settings/tabs`

Show or hide optional provider tabs in the UI.

**Auth:** Session or API key · **CSRF:** required (session only)

**Request**
```json
{ "dashboard": true, "routemap": true, "docker": false, "kubernetes": false }
```

**Response**
```json
{ "success": true, "visible_tabs": { "docker": true, ... } }
```

---

## Backups

#### `GET /api/backups`

List all configuration backups.

**Auth:** Session or API key

**Response**
```json
[
  { "name": "backup_2026-03-24T22-00-00.yml", "size": 1024, "modified": "2026-03-24T22:00:00" }
]
```

---

#### `POST /api/backup/create`

Create a manual backup of the current configuration.

**Auth:** Session or API key · **CSRF:** required (session only)

**Response**
```json
{ "success": true, "name": "backup_2026-03-24T22-05-00.yml" }
```

---

#### `POST /api/restore/{filename}`

Restore configuration from a backup file.

**Auth:** Session or API key · **CSRF:** required (session only) · **Rate limit:** 10/min

**Response**
```json
{ "success": true }
```

---

#### `POST /api/backup/delete/{filename}`

Delete a backup file.

**Auth:** Session or API key · **CSRF:** required (session only)

**Response**
```json
{ "success": true }
```

---

## Notifications

#### `GET /api/notifications`

List all stored notifications, newest first.

**Auth:** Session or API key

**Response**
```json
[
  { "ts": "2026-04-13 20:25:03", "type": "route_saved", "msg": "Route my-app saved" },
  { "ts": "2026-04-13 19:10:41", "type": "route_deleted", "msg": "Route old-app deleted" }
]
```

`type` indicates the event kind (e.g. `route_saved`, `route_deleted`, `middleware_saved`, `middleware_deleted`, `backup_created`, `restore`). `ts` is the UTC timestamp used as a unique identifier.

---

#### `POST /api/notifications/delete`

Delete a single notification by timestamp.

**Auth:** Session or API key · **CSRF:** required (session only)

**Request**
```json
{ "ts": "2026-04-13 20:25:03" }
```

**Response**
```json
{ "ok": true }
```

---

#### `POST /api/notifications/clear`

Delete all stored notifications.

**Auth:** Session or API key · **CSRF:** required (session only)

**Response**
```json
{ "ok": true }
```

---

## Static config

These endpoints power the [Static Config tab](tab-static.md). All require `STATIC_CONFIG_PATH` to be set and the file to exist.

#### `GET /api/static/available`

Check whether the static config editor is available.

**Auth:** Session or API key

**Response**
```json
{ "available": true }
```

`available` is `false` if `STATIC_CONFIG_PATH` is not set or the file does not exist.

---

#### `GET /api/static/config`

Read and parse the current static config file. Returns the full YAML as a string plus structured section data.

**Auth:** Session or API key

**Response**
```json
{
  "raw": "entryPoints:\n  web:\n    address: ':80'\n",
  "parsed": {
    "entryPoints": { "web": { "address": ":80" } },
    "certificatesResolvers": {},
    "api": { "dashboard": true },
    "log": { "level": "INFO" }
  },
  "path": "/app/traefik.yml"
}
```

---

#### `POST /api/static/config`

Validate and write an updated static config. A timestamped backup of the current file is created before writing.

**Auth:** Session or API key · **CSRF:** required (session only)

**Request**
```json
{ "yaml": "entryPoints:\n  web:\n    address: ':80'\n" }
```

**Response**
```json
{ "ok": true }
```

Returns `400` with `{ "error": "..." }` if the YAML is invalid.

---

#### `POST /api/static/restart`

Trigger a Traefik restart using the configured `RESTART_METHOD`.

**Auth:** Session or API key · **CSRF:** required (session only)

**Response**
```json
{ "ok": true }
```

Returns `500` with `{ "error": "..." }` if the restart method is not configured or the restart call fails.

---

#### `GET /api/static/status`

Check whether Traefik is currently up. Polls `/api/overview` on the Traefik API URL.

**Auth:** Session or API key

**Response**
```json
{ "up": true }
```

Used by the reconnect overlay to detect when Traefik has finished restarting.

---

#### `POST /api/static/section`

Update a single named item within the static config, or set a single-block section. Returns the updated raw YAML and parsed config so the UI can reflect the change without a full reload.

**Auth:** Session or API key · **CSRF:** required (session only)

**Request fields**

| Field | Type | Description |
|-------|------|-------------|
| `action` | string | `add`, `edit`, `remove`, or `set` |
| `section` | string | Target section - see table below |
| `name` | string | Item name (required for `add`/`edit`/`remove`; omit or empty for `set`) |
| `old_name` | string | Previous name when renaming an item during `edit` |
| `data` | object | Section-specific fields (see below) |
| `current_raw` | string | Current raw YAML from the client - used instead of reading from disk if provided |

**Sections and actions**

| `section` | Supported actions | `data` fields |
|-----------|-------------------|---------------|
| `entrypoints` | `add`, `edit`, `remove` | `address`, `redirect_to` |
| `resolvers` | `add`, `edit`, `remove` | `email`, `storage`, `challenge_type` (`dnsChallenge`/`httpChallenge`/`tlsChallenge`), `provider`, `http_entrypoint` |
| `plugins` | `add`, `edit`, `remove` | `moduleName`, `version` |
| `api` | `set` | `enabled`, `dashboard`, `insecure`, `debug` |
| `log` | `set` | `level` (`DEBUG`/`INFO`/`WARN`/`ERROR`), `accessLog`, `accessLogPath` |
| `providers` | `set` | `docker`, `dockerEndpoint`, `dockerExposedByDefault`, `dockerWatch`, `file`, `fileDirectory`, `fileWatch` - updates the Docker and File providers only, leaving all other provider keys untouched |
| `providers` | `add`, `edit`, `remove` | `name` = provider type key (e.g. `swarm`, `http`, `ecs`). For `swarm`: `endpoint`, `exposedByDefault`, `watch`. For `http`: `endpoint`, `pollInterval`. Other types: empty config (configure via Raw YAML). |

**Example - add an entrypoint**
```json
{
  "action": "add",
  "section": "entrypoints",
  "name": "websecure",
  "data": { "address": ":443" }
}
```

**Example - configure the API section**
```json
{
  "action": "set",
  "section": "api",
  "data": { "enabled": true, "dashboard": true, "insecure": false, "debug": false }
}
```

**Example - set log level and enable access log**
```json
{
  "action": "set",
  "section": "log",
  "data": { "level": "INFO", "accessLog": true, "accessLogPath": "/var/log/traefik/access.log" }
}
```

**Example - add a Swarm provider**
```json
{
  "action": "add",
  "section": "providers",
  "name": "swarm",
  "data": { "endpoint": "unix:///var/run/docker.sock", "exposedByDefault": false, "watch": true }
}
```

**Example - remove a provider**
```json
{
  "action": "remove",
  "section": "providers",
  "name": "swarm"
}
```

**Response**
```json
{
  "ok": true,
  "raw": "entryPoints:\n  websecure:\n    address: ':443'\n",
  "parsed": { "entryPoints": { "websecure": { "address": ":443" } } }
}
```

---

## Utility

#### `GET /api/manager/version`

Get the latest published Traefik Manager version from GitHub.

**Auth:** Session or API key

**Response**
```json
{ "version": "v0.5.0", "repo": "https://github.com/chr0nzz/traefik-manager" }
```

---

#### `GET /api/manager/router-names`

Get all router names across every protocol. Useful for autocomplete or validation.

**Auth:** Session or API key

**Response**
```json
[ "my-app@file", "api@file", "dashboard@internal" ]
```

---

#### `POST /api/setup/test-connection`

Test connectivity to a Traefik API URL. Used during initial setup but available for integrations.

**Auth:** None required

**Request**
```json
{ "url": "http://traefik:8080" }
```

**Response**
```json
{ "ok": true, "version": "3.2.0" }
```

---

## Example: API key usage

```bash
# Get all routes
curl https://manager.example.com/api/routes \
  -H "X-Api-Key: tm_your_key_here"

# Toggle a route off
curl -X POST https://manager.example.com/api/routes/my-app/toggle \
  -H "X-Api-Key: tm_your_key_here" \
  -H "Content-Type: application/json" \
  -d '{"enable": false}'

# Get live services
curl https://manager.example.com/api/traefik/services \
  -H "X-Api-Key: tm_your_key_here"
```
