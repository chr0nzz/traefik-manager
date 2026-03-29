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

Check whether an API key exists and is active.

**Auth:** Session or API key

**Response**
```json
{ "enabled": true, "has_key": true }
```

---

#### `POST /api/auth/apikey/generate`

Generate a new API key. Only one key exists at a time - generating a new one replaces the previous one.

**Auth:** Session · **CSRF:** required · **Rate limit:** 5/hour

**Response**
```json
{ "ok": true, "key": "tm_abcdef123456..." }
```

---

#### `POST /api/auth/apikey/revoke`

Revoke the current API key immediately.

**Auth:** Session · **CSRF:** required

**Response**
```json
{ "ok": true }
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

List plugins from `traefik.yml` if the file is mounted.

**Auth:** Session or API key

**Response**
```json
{ "plugins": [ { "name": "...", "version": "..." } ] }
```

---

#### `GET /api/traefik/certs`

List TLS certificates from `acme.json` if the file is mounted.

**Auth:** Session or API key

**Response**
```json
{ "certs": [ { "domain": "example.com", "sans": [...], "expiry": "..." } ] }
```

---

#### `GET /api/traefik/logs`

Tail Traefik access logs if the log file is mounted.

**Auth:** Session or API key

**Query params:** `lines` (1–1000, default 100)

**Response**
```json
{ "lines": ["192.168.1.1 - - [24/Mar/2026] ..."] }
```

---

## Routes & middlewares

#### `GET /api/configs`

List all loaded dynamic config files. Returns one entry when only `CONFIG_PATH` is set; multiple entries when `CONFIG_DIR` or `CONFIG_PATHS` is used.

**Auth:** Session or API key

**Response**
```json
[
  { "label": "routes.yml", "path": "/app/config/routes.yml" },
  { "label": "services.yml", "path": "/app/config/services.yml" }
]
```

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

`configFile` is the basename of the config file the entry came from. Empty string when only one file is loaded.

`id` is prefixed as `configFile::name` when multiple config files are loaded (e.g. `routes.yml::my-app`), to avoid collisions across files.

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
| `certResolver` | ACME cert resolver name (HTTP/TCP with TLS only). Falls back to the first configured resolver when omitted. |
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
  "auth_enabled": true,
  "visible_tabs": { "dashboard": true, "routemap": false, "docker": true, "kubernetes": false, ... }
}
```

`cert_resolver` is a comma-separated string when multiple resolvers are configured (e.g. `"letsencrypt, cloudflare"`). The first resolver is the default for new routes.

---

#### `POST /api/settings`

Update application settings.

**Auth:** Session or API key · **CSRF:** required (session only)

**Request**
```json
{
  "domains": ["example.com", "internal.lan"],
  "cert_resolver": "letsencrypt",
  "traefik_api_url": "http://traefik:8080"
}
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
