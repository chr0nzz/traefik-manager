# API Reference

Traefik Manager exposes a REST API used by the web UI and official mobile app.

::: tip Interactive reference
Every TM instance has a built-in API reference with live **Try It** at `/api`, or the **API** button in the top bar. Requests go to your own instance with your session already authenticated.
:::

---

## Authentication

**API key** *(recommended)* - generate a key in **Settings → Authentication → API Keys** and pass it as a header. API keys bypass CSRF checks entirely.

```
X-Api-Key: your-api-key
```

**Session cookie** - log in via the web UI. The browser session cookie is used automatically.

### When authentication fails

Every `/api/` endpoint except `GET /api/health` answers an unauthenticated or expired request with **`401`** and a JSON body. It never redirects.

```json
{ "ok": false, "error": "Not authenticated", "auth_required": true }
```

Treat `401` on any `/api/` path as "log in again", not as an empty result. Sessions expire on inactivity (`INACTIVITY_TIMEOUT_MINUTES`, default 120), so a long-lived script on session auth will start getting `401` even though it authenticated earlier. API keys do not expire.

Page routes (everything outside `/api/`) still redirect to `/login` as a browser expects.

::: tip Changed in v1.10.1
Before v1.10.1, `/api/` paths also redirected to `/login`, which returned the login page's HTML with status `200`. Clients could not distinguish "logged out" from "no data". If you parsed those responses, switch to checking for `401`.
:::

---

## Response format

All `/api/` endpoints return JSON. The form endpoints `POST /save`, `POST /delete/{id}`, `POST /save-middleware` and `POST /delete-middleware/{name}` return JSON only when the request sends `X-Requested-With: fetch`; otherwise they redirect (302) to the UI.

| Outcome | Shape |
|---|---|
| Success | `{ "ok": true }` or `{ "success": true }` |
| Error | `{ "ok": false, "message": "..." }` or `{ "error": "..." }` |

Common status codes:

| Code | Meaning |
|---|---|
| `400` | Invalid or missing parameters |
| `401` | Not authenticated, or the session expired |
| `403` | CSRF token missing or invalid |
| `404` | Object not found |
| `429` | Rate limit exceeded |
| `502` | An upstream (Traefik, an agent, CrowdSec, a remote repo) could not be reached |

State-changing endpoints (POST / PUT / DELETE / PATCH) require an `X-CSRF-Token` header when using session auth. API key requests skip this.

## Caching

Responses are sent with `Cache-Control: no-store, no-cache, must-revalidate` by default. Two things keep their own caching: anything under `/static/`, and any endpoint that sets the header itself - `GET /api/dashboard/icon/<slug>` serves icons with `max-age=86400`.

---

## Routes & Middlewares

### `GET /api/routes`

All managed routes and middlewares from every loaded config file.

**Response**

```json
{
  "apps": [ /* Route[] */ ],
  "middlewares": [ /* Middleware[] */ ],
  "configErrors": [ { "file": "dynamic.yml", "error": "..." } ],
  "services": { "http": ["app-service"], "tcp": [], "udp": [] }
}
```

`services` lists the service names defined in the config files, per protocol - what `serviceRef` accepts.

When multiple config files are loaded, route `id` is prefixed as `configFile::name`. Strip the prefix before using the name as a YAML key.

**Route object**

| Field | Type | Description |
|---|---|---|
| `id` | string | Unique identifier |
| `name` | string | Router name |
| `service_name` | string | Service the router points at, as written (may be `svc@docker`) |
| `enabled` | boolean | |
| `protocol` | string | `http`, `tcp`, or `udp` |
| `rule` | string | Traefik rule expression |
| `entryPoints` | string[] | Router entrypoints |
| `target` | string | First backend. Kept for backwards compatibility; same as `servers[0]` |
| `servers` | string[] | All backends. URLs for HTTP, `host:port` for TCP and UDP |
| `sticky` | object | `loadBalancer.sticky.cookie`, or `{}` when off. HTTP only |
| `stickyEnabled` | boolean | Whether a sticky block is present. HTTP only |
| `healthCheck` | object | `loadBalancer.healthCheck`, or `{}` when unset. HTTP only |
| `priority` | integer \| null | Router priority, `null` when unset. HTTP and TCP only |
| `middlewares` | string[] | Applied middleware names |
| `tls` | boolean \| object \| null | Boolean for HTTP and UDP. For TCP it is the router's `tls` mapping (e.g. `{"passthrough": true}`), or `null` when TLS is not set |
| `certResolver` | string | ACME resolver name, or empty for external certs |
| `configFile` | string | Source config file |
| `provider` | string | `file` for managed routes, otherwise the Traefik provider it was discovered from |

HTTP routes also carry `passHostHeader`, `tlsDomains`, `tlsOptionsProfile`, `insecureSkipVerify`, `streaming` and `serviceType`.

A route whose service is composite additionally carries `compositeChildren` - one
`{name, url, weight, percent}` per backend, with `url` filled only for children Traefik Manager
generated - and `serviceOwned`, true when Traefik Manager manages the service so the route form can
edit it. For a composite, `passHostHeader` and friends are read from the first generated child.

---

### `GET /api/routes/all`

Same shape as `GET /api/routes`, minus `configErrors`, and nothing is filtered out: routes from other Traefik providers (Docker, Kubernetes, and the rest) are enriched from the live Traefik API, and Traefik's own `@internal` routers are included.

Use this for everything Traefik is serving, and `/api/routes` for only what this instance manages in its own config files.

---

### `POST /save`

Create or update a route. Accepts `application/x-www-form-urlencoded`.

| Field | Type | Description |
|
`backendsJsonHttp` may also carry `children` and `compositeType` to make the route's service a
`weighted`, `mirroring` or `failover` composite - see the [OpenAPI spec](#openapi-spec) for the row
shape. The key only takes effect when present, so older clients cannot flatten a composite, and
`children: []` reverts to a plain `loadBalancer`.

---|---|---|
| `serviceName` | string | Route name. Required |
| `protocol` | string | `http`, `tcp`, or `udp` (default: `http`) |
| `subdomain` | string | Hostname. A value containing a dot is used as-is; a bare label is combined with the configured domain(s). Becomes `Host()` for HTTP and `HostSNI()` for TCP |
| `domains` | string | Repeatable. Domains used to build the rule. Defaults to the first configured domain |
| `httpRule` / `tcpRule` | string | Raw Traefik rule expression. Overrides `subdomain` |
| `targetIp` | string | Backend host, repeated per protocol - see below. Ignored when the matching `backendsJson*` field is sent |
| `targetPort` | string | Backend port, repeated per protocol |
| `serviceRef` | string | Reference an existing service instead of creating `<name>-service`. Writes only the router; target and load-balancing fields are ignored. A bare name must exist in the file config for that protocol (400 otherwise); a provider-qualified name (`svc@docker`) is written verbatim |
| `backendsJsonHttp` | string (JSON) | HTTP service definition - see [Multiple backends](#multiple-backends) below |
| `backendsJsonTcp` | string (JSON) | TCP service definition |
| `backendsJsonUdp` | string (JSON) | UDP service definition |
| `entryPoints` | string | Comma-separated, repeated per protocol. HTTP defaults to `https`. UDP uses `udpEntryPoint` instead |
| `middlewares` | string | Comma-separated middleware names. HTTP only; TCP uses `middlewaresTcp` |
| `scheme` | string | `http` or `https` (default: `http`). HTTP only |
| `passHostHeader` | boolean | Send `true` to keep the host header. Omitting the field writes `passHostHeader: false` into the service |
| `insecureSkipVerify` | boolean | `true` writes a `<serviceName>-transport` serversTransport that skips backend certificate checks |
| `certResolver` | string | ACME resolver name, repeated per protocol. Use `none` to write `tls: {}` with no resolver (external certs), or `__disabled__` to write no `tls` block at all |
| `useTls` / `tlsPassthrough` | boolean | TCP only. `tlsPassthrough` wins and writes `tls: {passthrough: true}` |
| `tlsWildcardMain` | string | Main domain for `tls.domains` (e.g. `example.com`). Use with DNS challenge resolvers for wildcard certs |
| `tlsWildcardSans` | string | Newline-separated SANs for `tls.domains` (e.g. `*.example.com`) |
| `tlsOptionsProfile` | string | `tls.options` profile name to attach to the router. HTTP only |
| `configFile` | string | Target config file (multi-config only) |
| `agent_id` | string | Write to this agent instead of the Host |
| `isEdit` | boolean | `true` when updating an existing route |
| `originalId` | string | Original route ID when renaming |

#### Multiple backends

A service can point at several servers. Send the `backendsJson*` field matching the protocol; it takes precedence over `targetIp`/`targetPort`, which stay supported for single-backend clients.

```json
{
  "servers": [
    { "scheme": "http", "host": "192.168.1.10", "port": "8080" },
    { "scheme": "http", "host": "192.168.1.11", "port": "8080" }
  ],
  "sticky":      { "enabled": true, "cookieName": "tm_sticky", "secure": true, "httpOnly": true },
  "healthCheck": { "enabled": true, "path": "/health", "interval": "10s", "timeout": "3s" },
  "priority": 10
}
```

- A `host` already starting with `http://` or `https://` is used verbatim; otherwise `scheme://host:port` is built.
- Rows with an empty `host` are skipped. Invalid JSON falls back to `targetIp`/`targetPort` rather than failing the save.
- `healthCheck` needs a `path`; without one the whole block is dropped. `interval` and `timeout` take a Go duration of one unit (`10s`, `1m`, `500ms`); a bare number is read as seconds, anything else is dropped.
- A `priority` of `0` is treated as unset.
- `sticky`, `healthCheck`, and `priority` apply to HTTP. TCP accepts `servers` and `priority`; UDP accepts `servers` only.
- `targetIp`, `targetPort`, `certResolver` and `entryPoints` are repeated fields indexed by protocol - index 0 for HTTP, 1 for TCP, 2 for UDP - so a TCP save must send two `targetIp` values (the first may be empty). `certResolver` and `entryPoints` only use indexes 0 and 1.
- For TCP and UDP you may instead send the joined `host:port` form in `targetIp` at that index and leave `targetPort` empty.

::: warning Sending `backendsJson*` replaces the whole service
A save whose `backendsJson*` yields at least one valid server row is authoritative: `servers` is replaced outright, and `sticky` or `healthCheck` absent from the payload are **deleted**. A client that edits backends must read the route first and echo `sticky`, `healthCheck` and `priority` back, or it will silently drop them. Omit `backendsJson*` to get the merge behaviour below instead.
:::

::: tip Editing from a single-backend client
A save that omits `backendsJson*` on an edit replaces only the **first** backend. Further backends, plus `sticky`, `healthCheck` and `priority`, are preserved, so the mobile app and older cached pages cannot wipe a multi-backend route.

The same protection covers shared services: an edit that omits `serviceRef` on a router pointing at a shared or cross-provider service keeps the reference and ignores the posted target fields.
:::

---

### `POST /delete/{route_id}`

Delete a route by ID. Accepts `application/x-www-form-urlencoded`. Removes the router and, unless another router still uses it, its service. `404` when no config file and no disabled-route record holds that router.

| Param | Description |
|---|---|
| `route_id` | Route ID (path) |
| `configFile` | Config file basename (body, multi-config only) |
| `agent_id` | Delete on this agent instead of the Host (body) |

---

### `POST /api/routes/{route_id}/toggle`

Enable or disable a route without deleting it. Config is preserved in `manager.yml`. Pass `agent_id` to toggle a route on an agent.

```json
{ "enable": true, "agent_id": "" }
```

---

### `GET /api/routes/{route_id}/raw`

The YAML for one route and its service, as stored. `route_id` is either the router name or `file.yml::router` on a multi-file install. Go template expressions are preserved rather than being expanded.

```json
{ "raw": "http:\n  routers:\n    my-app:\n      ...", "configFile": "dynamic.yml", "proto": "http" }
```

`404` if no config file contains that router.

---

### `POST /api/routes/{route_id}/raw`

Replace that route's YAML. A backup is taken first, and Go templates in your content are preserved.

```json
{ "content": "http:\n  routers:\n    my-app:\n      rule: Host(`app.example.com`)" }
```

Returns `400` for empty content or invalid YAML, `404` if the route cannot be located.

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
| `mwProtocol` | `http` (default) or `tcp` |
| `configFile` | Target config file |
| `agent_id` | Write to this agent instead of the Host |
| `isMwEdit` | `true` when updating |
| `originalMwId` | Original ID when renaming |
| `originalMwProtocol` | Original protocol when moving between `http` and `tcp` |

---

### `POST /delete-middleware/{name}`

Delete a middleware by name. Accepts `application/x-www-form-urlencoded`.

| Param | Description |
|---|---|
| `name` | Middleware name (path) |
| `configFile` | Config file basename (body, multi-config only) |
| `agent_id` | Delete on this agent instead of the Host (body) |
| `force` | Remove the middleware from the routes using it, then delete it (body) |

Refused with `409` while a router still references it. The response carries `inUseBy` with the
router names. Send `force` to remove it from them and delete it.

---

## Traefik

These endpoints proxy read-only data from the Traefik API. They require a valid Traefik API URL in settings.

### `GET /api/traefik/overview`

Router, service, and middleware counts plus Traefik feature flags. Passes through the Traefik dashboard overview object.

---

### `GET /api/traefik/routers`

All routers across HTTP, TCP, and UDP, following Traefik's pagination.

```json
{ "http": [...], "tcp": [...], "udp": [...], "reachable": true }
```

`reachable` is `false` when no protocol could be fetched, which separates an unreachable Traefik from one with no routers.

---

### `GET /api/traefik/services`

All services across HTTP, TCP, and UDP, in the same `{http, tcp, udp, reachable}` shape as
`GET /api/traefik/routers`, plus two lists naming what Traefik Manager manages:

| Field | Meaning |
|---|---|
| `ownedServices` | Composite services Traefik Manager manages, so they can be edited rather than being read only |
| `ownedChildren` | The `<name>-backend-<n>` services it generated. Clients hide these from the list and show them on their parent |

---

### `GET /api/traefik/middlewares`

All middlewares across HTTP and TCP.

```json
{ "http": [...], "tcp": [...] }
```

Returns `502` with `{"error": "Traefik API unreachable"}` if the Traefik API cannot be reached. Earlier versions returned `200` with empty lists.

---

### `GET /api/traefik/entrypoints`

All configured entrypoints.

```json
[{ "name": "websecure", "address": ":443" }]
```

Returns `502` with `{"error": "Traefik API unreachable"}` if the Traefik API cannot be reached. Earlier versions returned `200` with an empty list.

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

Returns `503` with `{ "ok": false, "latency_ms": null }` when the ping fails.

---

### `GET /api/traefik/plugins`

List plugins defined under `experimental.plugins` in the static config.

```json
{ "plugins": [{ "name": "crowdsec", "moduleName": "github.com/org/repo", "version": "v1.4.5", "settings": null }] }
```

Returns `200` with an `error` string and an empty list when no static config path is configured or the file is missing.

---

### `GET /api/plugins/catalog`

Latest known version per plugin module, as `{ "plugins": { "github.com/org/repo": "vX.Y.Z" } }`. Module paths are lowercased. Fetched from the Traefik plugin catalog and cached for 24 hours; returns an empty map when the catalog is unreachable, and retries after 15 minutes.

---

### `GET /api/traefik/certs`

List TLS certificates from ACME (`acme.json`) and from `tls.certificates` entries in the loaded dynamic config files. ACME entries need an `acme.json` path, from `ACME_JSON_PATH` or Settings; it can be a comma-separated list or a directory.

```json
{ "certs": [ ... ] }
```

| Field | Description |
|---|---|
| `resolver` | ACME resolver name, or `file` for file-provider certificates |
| `main` | Primary domain |
| `sans` | Subject alternative names |
| `not_after` | Expiry timestamp (ISO 8601), `null` if the certificate cannot be parsed |
| `source` | acme.json file the certificate came from (ACME entries) |
| `certFile` | Certificate path (file-provider entries) |

When nothing could be read, the response also carries an `error` string.

---

### `GET /api/traefik/logs`

Tail Traefik access logs. Requires an access log path, from `ACCESS_LOG_PATH` or Settings.

| Query param | Default | Max |
|---|---|---|
| `lines` | `100` | `1000` |

```json
{ "lines": ["..."] }
```

---

### `GET /api/diagnostics/client-ip`

Read-only diagnostic for the current request: the client as seen after `ProxyFix`, the raw socket peer, the forwarding headers as received, the trusted proxy hop count (`PROXY_FIX_HOPS`), and a scope class (`public`, `private`, `cgnat`, `loopback`, `link-local` or `unknown`) per observed IP.

```json
{
  "effective_ip": "203.0.113.5",
  "effective_class": "public",
  "socket_peer": "172.20.0.1",
  "socket_peer_class": "private",
  "headers": {
    "X-Forwarded-For": "203.0.113.5",
    "X-Real-IP": "",
    "CF-Connecting-IP": "",
    "X-Forwarded-Proto": "https",
    "X-Forwarded-Host": "example.com"
  },
  "forwarded_for_chain": ["203.0.113.5"],
  "proxy_hops": 1,
  "classes": { "203.0.113.5": "public", "172.20.0.1": "private" }
}
```

---

## Dashboard

### `GET /api/dashboard/config`

Get saved dashboard configuration - custom groups and per-route icon, name, link and hidden overrides.

Pass `?server=<agent-id>` to read an agent's configuration. Without it you get the Host's. Each server keeps its own groups and overrides.

```json
{
  "custom_groups": [{ "name": "Media" }],
  "route_overrides": {
    "dynamic.yml::jellyfin": {
      "display_name": "Jellyfin",
      "icon_type": "slug",
      "icon_slug": "jellyfin",
      "icon_url": "",
      "group": "Media",
      "url": "https://jellyfin.example.com",
      "hidden": false,
      "link_disabled": false
    }
  },
  "tm_route_name": "traefik-manager"
}
```

Keys of `route_overrides` are route ids (`<config-file>::<router-name>`, or just the router name on a single-file install). `tm_route_name` is read-only and names the router that points at Traefik Manager itself, so a client can give it TM's own icon.

---

### `POST /api/dashboard/config`

Save dashboard configuration. Replaces that server's section of `dashboard.yml`, leaving the other servers untouched.

Pass `?server=<agent-id>`, or a `server` key in the body, to write an agent's configuration. Without it the Host's is written.

```json
{
  "custom_groups": [{ "name": "Media" }],
  "route_overrides": {
    "plex": { "display_name": "Plex", "icon_type": "slug", "icon_slug": "plex", "group": "Media",
              "url": "https://plex.example.com", "link_disabled": false }
  }
}
```

`icon_type` is `auto`, `slug`, or `url`. `url` overrides the URL the dashboard card opens and must start with `http://` or `https://` - anything else is dropped on save. `link_disabled: true` makes the card non-clickable.

---

### `GET /api/dashboard/icon/{slug}`

Serve a cached app icon by slug (e.g. `plex`, `grafana`). On a cache miss it fetches the [selfh.st](https://selfh.st/icons/) icon set from jsDelivr and stores the PNG on disk, with `Cache-Control: max-age=86400`.

Misses are cached too: a slug with no icon returns `404` at once on later requests. Prefer this over the CDN directly - a client hitting the CDN itself makes one request per route on every render and loses the negative cache.

The slug is lowercased and stripped to `a-z0-9-`; anything else returns `404`.

#### Resolving a route's icon

The dashboard resolves icons client-side. To match it:

1. `icon_type: "url"` - use `icon_url` as-is.
2. `icon_type: "slug"` - use `icon_slug`.
3. Route name equals `tm_route_name` - use Traefik Manager's own icon.
4. Otherwise (`icon_type: "auto"`, or no override) - derive the slug from `service_name`, falling back to the route name:
   - drop anything from `@` onward, then strip a trailing `:port`
   - strip one trailing `-service`, `-svc`, `-router`, `-app`, `-container` or `-pod`, with an optional `s`, separated by `-` or `_`
   - lowercase, then remove every character that is not `a-z`, `0-9` or `-`

So `Jellyfin-Service` and `jellyfin` both resolve to `jellyfin`. Fall back to a monogram of the route's first letters when the request returns `404`.

---

## Settings

### `GET /api/settings`

Get current application settings. Every secret is stripped. Five come back as a `*_set` boolean - `traefik_api_password_set`, `oidc_client_secret_set`, `crowdsec_api_key_set`, `crowdsec_machine_password_set`, `git_backup_token_set`; `password_hash` becomes `has_password`; `webhook_password` and `otp_secret` are removed with no replacement. The `agents` list is stripped too - use `GET /api/agents`.

| Field                      | Description                                        |
| ----------------------------| ----------------------------------------------------|
| `domains`                  | Allowed domains list                               |
| `cert_resolver`            | Default ACME resolver name(s)                      |
| `traefik_api_url`          | Traefik API base URL                               |
| `acme_json_path`           | Path to `acme.json` inside the container           |
| `access_log_path`          | Path to Traefik access log                         |
| `static_config_path`       | Path to `traefik.yml`                              |
| `auth_enabled`             | Password auth on/off                               |
| `auth_env_forced`          | `true` when `AUTH_ENABLED` disables auth from the environment |
| `oidc_enabled`             | OIDC on/off                                        |
| `no_auth`                  | `true` when neither password auth nor OIDC is active |
| `has_password`             | `true` if a login password is set                  |
| `visible_tabs`             | Tab visibility map                                 |
| `ui_prefs`                 | Display preferences, see `GET /api/settings/ui`    |
| `webhook_url`              | Notification webhook URL                           |
| `traefik_api_user`         | Traefik API username for basic auth                |
| `traefik_api_password_set` | `true` if a Traefik API password is saved          |
| `crowdsec_lapi_url`        | CrowdSec LAPI URL                                  |
| `crowdsec_api_key_set`     | `true` if a CrowdSec API key is saved              |
| `crowdsec_alert_limit`     | Alert row limit, blank falls back to `CROWDSEC_ALERT_LIMIT` |
| `crowdsec_enabled`         | `true` when a LAPI URL is set plus either a bouncer API key or machine credentials |

---

### `POST /api/settings`

Update settings. Full replace, not a patch: `domains` is required (`400` without it) and any omitted field resets to its default, so send the current values you want to keep.

Exceptions: `git_backup_*`, `backup_keep_count`, `default_theme` and `notification_channels` are updated only when present, and blank `traefik_api_password`, `crowdsec_api_key`, `crowdsec_machine_password`, `webhook_password` and `git_backup_token` keep the stored secret.

Returns `{ "success": true, "settings": { ... } }` with secrets stripped. `400` for a missing domain, an invalid `traefik_api_url`, an unsupported `git_backup_repo` scheme, a `crowdsec_alert_limit` that is not a whole number ("Alert limit must be a whole number") or one outside 0-100000 ("Alert limit must be between 0 and 100000").

---

### `POST /api/settings/webhook-test`

Send a test payload to a webhook URL without saving it. Also accepts `webhook_type`, `username` and `password`.

```json
{ "url": "https://discord.com/api/webhooks/..." }
```

Returns `400` for a URL that is not `http(s)` or that fails the SSRF guard.

---

### `GET /api/settings/self-route`

Get the saved self-route domain. If none is saved and `?hostname=<host>` is supplied, TM scans the config files for an existing route pointing to the TM service. The response always includes `default_entry_point`.

---

### `POST /api/settings/self-route`

Save or remove the self-route. An empty `domain` deletes the self-route file. `router_name` defaults to `traefik-manager` and is what `tm_route_name` reports; `entry_point` defaults to the best entrypoint TM can find.

```json
{ "domain": "manager.example.com", "service_url": "http://traefik-manager:5000",
  "router_name": "traefik-manager", "entry_point": "websecure" }
```

---

### `POST /api/settings/tabs`

Show or hide optional UI tabs. Send the tab keys at the top level; anything that is not a known tab key is ignored.

```json
{ "dashboard": true, "routemap": true, "docker": false }
```

Known keys: `dashboard`, `routemap`, `docker`, `kubernetes`, `swarm`, `nomad`, `ecs`, `consulcatalog`, `redis`, `etcd`, `consul`, `zookeeper`, `http_provider`, `file_external`, `certs`, `tls`, `crowdsec`, `plugins`, `logs`, `static`.

---

### `POST /api/settings/test-connection`

Test connectivity to a Traefik API URL before saving. Accepts optional credentials for auth-protected dashboards.

```json
{ "url": "http://traefik:8080", "user": "admin", "password": "secret" }
```

---

### `GET /api/settings/ui`

Display preferences stored server-side, so they follow the user across browsers and devices.

```json
{ "ok": true, "ui_prefs": { "showApiLink": true, "svcViewMode": "list" } }
```

---

### `POST /api/settings/ui`

Update one or more preferences. Keys not sent keep their current value. A bare object without the `ui_prefs` wrapper is also accepted.

```json
{ "ui_prefs": { "showDocsLink": false, "mwViewMode": "list" } }
```

| Key | Values |
|---|---|
| `showStatCards`, `compactStatCards`, `showEntrypoints`, `showDocsLink`, `showApiLink`, `showShortcutsBtn`, `showIpDiagBtn`, `showTraefikBadge`, `showTmBadge`, `showRouteIcons`, `logsAutoRefresh` | boolean |
| `routeViewMode`, `mwViewMode`, `svcViewMode` | `grid` or `list` |
| `statBarScope` | `all` (stat cards on every tab) or `dashboard` |
| `layoutMode` | `fluid` or `fixed` (`modern`/`classic` still accepted as aliases) |
| `dashPodDensity` | `list` or `icons` |
| `staticPlacement` | `off`, `settings` or `tab` - where the Static Config editor appears |
| `staticOpenSections`, `settingsOpenSections` | string arrays of accordion section names |

Anything else is dropped rather than stored. Returns `400` if `ui_prefs` is not an object.

---

### `POST /api/settings/theme`

Set the default theme for new browsers. One of `dark`, `light`, `system`.

```json
{ "default_theme": "system" }
```

`400` for any other value.

---

### `POST /api/settings/geoip`

Enable GeoIP and set the database path. Omitted keys keep their current value.

```json
{ "geoip_enabled": true, "geoip_db_path": "/app/config/geoip/dbip-city-lite.mmdb" }
```

Returns `{ "success": true, "status": { } }` carrying the same payload as `GET /api/geoip/status`.

---

## TLS Options

All three endpoints accept `?server=<agent-id>` to act on an agent's config files instead of the Host's.

### `GET /api/tls-options`

List all `tls.options` profiles from every mounted config file.

**Response** - array of profiles:

| Field | Type | Description |
|---|---|---|
| `name` | string | Profile key (e.g. `modern`, `default`) |
| `configFile` | string | Source config file basename, empty on a single-file install |
| `configFilePath` | string | Full path of the source file |
| `minVersion` | string | Minimum TLS version (e.g. `VersionTLS12`) |
| `maxVersion` | string | Maximum TLS version |
| `sniStrict` | boolean | SNI strict mode enabled |
| `cipherSuites` | string[] | Cipher suite list |
| `curvePreferences` | string[] | ECDH curve list |
| `alpnProtocols` | string[] | ALPN protocol list |
| `clientAuthType` | string | Client auth type |
| `clientAuthCAs` | string[] | CA file paths, from `clientAuth.caFiles` |
| `yaml` | string | Raw YAML block for display |

---

### `POST /api/tls-options`

Pass `originalName` to rename a profile, which moves every router using it to the new name.

Create or update a TLS options profile. JSON body. Empty fields are left out of the written YAML, and `clientAuthType: NoClientCert` writes no `clientAuth` block. `400` without a `name`.

| Field | Type | Description |
|---|---|---|
| `name` | string | Profile name (required) |
| `configFile` | string | Target config file basename (multi-config only) |
| `minVersion` | string | e.g. `VersionTLS12` |
| `maxVersion` | string | Optional upper bound |
| `sniStrict` | boolean | Enable SNI strict |
| `cipherSuites` | string[] | Cipher suite list |
| `curvePreferences` | string[] | Curve list |
| `alpnProtocols` | string[] | ALPN list |
| `clientAuthType` | string | Client auth type |
| `clientAuthCAs` | string[] | CA file paths |

---

### `DELETE /api/tls-options/{name}`

Delete a TLS options profile by name. `404` if the profile does not exist, `409` while a router
still uses it, with `inUseBy` naming the routers.

| Query param | Description |
|---|---|
| `configFile` | Config file basename (multi-config only) |

---

## Backups

### `GET /api/backups`

List all backup files, newest first. `kind` is `static` for backups of `traefik.yml`, `routes` for everything else.

```json
[{ "name": "dynamic.yml.20260324_220000.bak", "size": 1024, "modified": "2026-03-24 22:00:00", "kind": "routes" }]
```

---

### `POST /api/backup/create`

Create a manual backup of every loaded config file. Returns `{ "success": true, "names": ["dynamic.yml.20260324_220000.bak"], "count": 1 }`, or `400` when there is nothing to back up.

---

### `POST /api/restore/{filename}`

Restore configuration from a backup file. Rate-limited to 10/min. The current file is backed up first. `404` if the backup is missing, `400` if its name matches no loaded config file or the static config.

---

### `POST /api/backup/delete/{filename}`

Delete a backup file.

---

### `POST /api/static/backup/create`

Create a backup of `traefik.yml` on demand. `POST /api/backup/static/create` is an alias for the same handler.

```json
{ "success": true, "name": "traefik.yml.20260812_051500.bak" }
```

Returns `400` if no static config path is configured or the file is missing.

---

### `POST /api/settings/backup-retention`

Set how many backups to keep per file. `0` keeps all of them.

```json
{ "backup_keep_count": 20 }
```

---

## Git backup

Every endpoint here accepts an optional `?agent_id=<agent-id>` to act on an agent's repository instead of the Host's.

### `GET /api/backup/git/status`

```json
{ "enabled": true, "configured": true, "last_sha": "a1b2c3d4", "last_push": "2026-08-12 05:15:00 +0000" }
```

`last_sha` is the short form. Agent requests also return `branch`.

---

### `POST /api/backup/git/push`

Commit and push the current config. An optional `message` overrides the configured commit template for this push only. Returns `400` with the git error on failure.

```json
{ "message": "before the entrypoint change" }
```

---

### `POST /api/backup/git/test`

Test repository credentials without pushing, via `git ls-remote`. Falls back to the saved settings when the body is empty, so it can verify an existing configuration.

```json
{ "repo_url": "https://github.com/you/configs", "username": "you", "token": "ghp_..." }
```

Returns `{ "ok": true }`, or `400` with the git error. Tokens are redacted from the message.

---

### `GET /api/backup/git/commits`

The 50 most recent commits. Returns `[]` rather than an error when git backup is not configured.

```json
[{ "sha": "a1b2...", "sha_short": "a1b2c3d4", "timestamp": "2026-08-12 05:15:00 +0000", "message": "Update dynamic config" }]
```

---

### `GET /api/backup/git/commit/{sha}/diff`

The diffstat plus the old and new content of every file in that commit, which is what the UI's diff viewer renders.

```json
{ "stat": " dynamic/app.yml | 4 ++--", "files": [{ "filename": "dynamic/app.yml", "status": "M", "old": "...", "new": "..." }] }
```

`400` if `sha` is not a hex SHA of 7 to 40 characters.

---

### `POST /api/backup/git/restore/{sha}`

Restore the config from a commit. On the Host, every config file and the static config are backed up locally first; on an agent the files are pushed back through the agent instead.

---

### `DELETE /api/backup/git/repo`

Delete the local clone. The next push re-initialises it. Use this when the repository or credentials change and the clone is stale.

---

## Notifications

### `GET /api/notifications`

List stored notifications, newest first. The last 200 are kept. The response is a
plain array, not an object.

```json
[{ "id": 412, "at": 1776112503, "ts": "2026-04-13 20:25:03",
   "type": "success", "msg": "Route my-app saved", "category": "config" }]
```

| Field | Meaning |
|---|---|
| `id` | Stable, increasing, never reused. Use it to delete or to mark read |
| `at` | Unix epoch seconds, UTC. Convert to the reader's own timezone |
| `ts` | Server-local time as a string, kept for older clients |
| `category` | `config`, `backup`, `security`, `traefik`, `certs`, `crowdsec`, `agent`, `update` |

::: tip Added in v1.12.0
`id`, `at` and `category` are new. Rows written by an earlier version are given an
`id` and an `at` the first time the file is read; a `ts` that will not parse gets
`at: 0` rather than being dropped.
:::

---

### `POST /api/notifications/delete`

Delete a single notification. Prefer `id`, which removes exactly that row.

```json
{ "id": 412 }
```

`ts` is still accepted and behaves as it always has, removing the first row with
that timestamp. Because `ts` is only second-resolution, two notifications logged
in the same second cannot be told apart that way.

```json
{ "ts": "2026-04-13 20:25:03" }
```

Returns `404` when no row carries that `id`.

---

### `POST /api/notifications/read`

Set the shared read marker, so the web bell and every phone agree on what has
been read. Send an `id`, or `all` to mark everything read.

```json
{ "id": 412 }
{ "all": true }
```

---

### `GET /api/notifications/state`

The read marker and what is still unread.

```json
{ "read_until": 412, "count": 200, "unread": 4 }
```

Counting unread from the array length breaks once the 200-entry cap is reached,
because the length stops changing. Use this instead.

---

### `POST /api/notifications/clear`

Clear all notifications.

::: tip Changed in v1.10.1
`add`, `delete` and `clear` enforced CSRF unconditionally, so an API key request was rejected with `403` even though API keys are meant to skip CSRF. All three now honour the key. On v1.10.0 and earlier, they are session-only.
:::

---

### `POST /api/notifications/add`

Add a notification. Unlike `/log`, this also fires the configured webhook. `category` is one of the eight channel categories and falls back to `config`.

```json
{ "type": "info", "message": "Deployment finished", "category": "config" }
```

---

### `POST /api/notifications/log`

Record a UI toast in the notification history without firing a webhook. `type` is one of `info`, `success`, `warning`, `error` and falls back to `info`; `category` is one of the eight channel categories and falls back to `config`. The message is truncated to 300 characters.

```json
{ "ok": true, "stored": true }
```

`stored` is `false` when the message is identical to one recorded in the last 8 seconds (duplicate suppression). An empty message returns `400`.

---

### `POST /api/notifications/update`

Record an "update available" notification. `product` is `manager` for Traefik Manager, anything else means Traefik.

```json
{ "version": "1.10.1", "product": "manager" }
```

---

## Notification channels

Channels are where notifications are delivered. Each one has a `kind`, a category filter, a
severity floor and an optional quiet window. Secrets (`token`, `token2`, `password`) read back
as `***`, and for `discord`, `slack`, `ntfy` and `generic` the `url` reads back as
`scheme://host/***`. A `url` still containing `***` is ignored on write, so a channel can be
echoed back unchanged.

| Field | Values |
| --- | --- |
| `kind` | `discord`, `slack`, `ntfy`, `unifiedpush`, `generic`, `gotify`, `pushover`, `pushbullet`, `telegram` |
| `categories` | any of `config`, `backup`, `security`, `traefik`, `certs`, `crowdsec`, `agent`, `update` |
| `min_severity` | `info`, `success`, `warning`, `error` |
| `digest` | `immediate`, `hourly`, `daily` |
| `quiet_hours` | `HH:MM-HH:MM`, or `""` for none |
| `break_through` | `true` sends `error` events during quiet hours |

An unknown `kind`, category, `min_severity`, `digest` or a malformed `quiet_hours` returns `400`.

### `GET /api/notifications/channels`

List every channel, secrets redacted.

```json
{ "channels": [{ "id": "ch_1a2b3c4d", "name": "Ops Discord", "kind": "discord", "enabled": true,
  "url": "https://discord.com/***", "token": "", "token2": "", "password": "",
  "categories": ["certs", "crowdsec"], "min_severity": "warning", "digest": "immediate",
  "quiet_hours": "23:00-07:00", "break_through": true }] }
```

---

### `POST /api/notifications/channels`

Create a channel. `kind` is required. The `id` is generated server-side and returned. An empty
`name` falls back to the kind. Omitted fields take their defaults: enabled, every category,
`min_severity` `info`, `digest` `immediate`, no quiet hours.

```json
{ "kind": "gotify", "name": "Phone", "url": "https://gotify.example.com", "token": "A1b2C3" }
```

---

### `PUT /api/notifications/channels/{id}`

Update a channel. Omitted fields keep their value. Send a secret as `***` to keep the stored one,
or any other string to replace it. `404` if the id is unknown.

```json
{ "min_severity": "error", "token": "***" }
```

---

### `DELETE /api/notifications/channels/{id}`

Delete a channel. `404` if the id is unknown.

---

### `POST /api/notifications/channels/{id}/test`

Send a test notification through the channel now, ignoring its category, severity, digest and
quiet-hour filters. A channel missing a required field for its kind returns `400` naming the
field, without attempting delivery. A delivery failure returns `200` with `ok: false`.

```json
{ "ok": true, "detail": "" }
```

---

## Authentication endpoints

### `POST /api/auth/change-password`

Change the login password. Rate-limited to 10/min. The new password must be at least 8 characters and at most 72 bytes, which is the bcrypt limit. `403` if `current_password` is wrong.

```json
{ "current_password": "...", "new_password": "...", "confirm_password": "..." }
```

---

### `POST /api/auth/toggle`

Enable or disable password authentication. The response carries `reauth_required` when the change means the current session must log in again.

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

Generate a new API key. `device_name` is required and truncated to 50 characters. Up to 10 keys can exist. Rate-limited to 5/hour. The full key is returned once - store it securely.

```json
{ "device_name": "My Phone" }
```

Response: `{ "ok": true, "key": "8Kv2v1s...URL-safe token" }`

---

### `POST /api/auth/apikey/revoke`

Revoke an API key by its preview string.

```json
{ "preview": "abcd1234...ef56" }
```

---

### `GET /api/auth/oidc`

Get current OIDC configuration. The client secret is replaced by `oidc_client_secret_set`.

---

### `POST /api/auth/oidc`

Save OIDC configuration. This is a full replace: omitted fields fall back to their defaults. Leave `oidc_client_secret` blank to keep the existing secret.

| Field | Description |
|---|---|
| `oidc_enabled` | Enable or disable OIDC |
| `oidc_provider_url` | Provider base URL (without `/.well-known/...`) |
| `oidc_client_id` | Client ID |
| `oidc_client_secret` | Client secret (omit to keep existing) |
| `oidc_display_name` | Login button label (default `OIDC`) |
| `oidc_allowed_emails` | Comma-separated allowed emails |
| `oidc_allowed_groups` | Comma-separated allowed groups |
| `oidc_allow_any_authenticated` | Accept any user the provider authenticates |
| `oidc_groups_claim` | Claim name containing groups (default `groups`) |
| `oidc_auto_login` | Send the login page straight to the provider |

---

### `POST /api/auth/oidc/test`

Test connectivity to an OIDC provider's discovery endpoint. Credentials are not verified.

```json
{ "provider_url": "https://accounts.google.com" }
```

---

### `POST /api/auth/external-ack`

Acknowledge that an external provider (a Traefik forward-auth middleware, for example) already protects this instance, which hides the "no authentication" banner.

```json
{ "auth_external_ack": true }
```

```json
{ "success": true, "auth_external_ack": true }
```

Returns `400` if a password or OIDC is active, since there is then nothing to acknowledge. This changes only what the UI reports - it never changes what is enforced. Setting and clearing it are both logged.

---

## Static Config

Requires a static config path, from `STATIC_CONFIG_PATH` or Settings. See [Enable Static Config](/static-enable).

### `GET /api/static/available`

Check whether the static config editor is available.

```json
{ "available": true }
```

---

### `GET /api/static/config`

Read and parse the current static config file. Pass `?server=<agent-id>` to read an agent's instead.

```json
{ "raw": "...", "parsed": { ... }, "path": "/app/traefik.yml" }
```

`404` when the file is missing or no path is configured.

---

### `POST /api/static/config`

Validate and write an updated static config. A timestamped backup is created before writing. The key `raw` is accepted as an alias for `content`.

```json
{ "content": "entryPoints:\n  web:\n    address: ':80'\n" }
```

Returns `400` with `{ "error": "..." }` for empty content, invalid YAML or no configured path, and `403` if the path resolves outside the allowed directories.

---

### `POST /api/static/restart`

Trigger a Traefik restart using the configured `RESTART_METHOD`. Returns `500` with the reason when the restart could not be triggered.

---

### `GET /api/static/status`

Check whether Traefik is currently up. Used by the reconnect overlay after a restart.

```json
{ "up": true }
```

---

### `POST /api/static/section`

Edit one named section of the static config without writing raw YAML. **Nothing is saved**: the endpoint returns the rewritten document and the client persists it with [`POST /api/static/config`](#post-api-static-config), which is why it works the same on the Host and on a remote agent.

```json
{
  "action": "add",
  "section": "entrypoints",
  "name": "websecure",
  "data": { "address": ":443" },
  "current_raw": ""
}
```

`current_raw` is the document to edit; empty reads the file on disk. `old_name` renames an entry on `action: "edit"`.

**Supported sections and actions**

| Section | Actions | Main `data` fields |
|---|---|---|
| `entrypoints` | `add`, `edit`, `remove` | `address`, `redirect_to`, `http3`, `as_default`, `middlewares`, `tls_enabled`, `tls_cert_resolver`, `tls_options`, `trusted_ips`, `proxy_trusted_ips`, `read_timeout`, `write_timeout`, `idle_timeout`, `underscore_headers`, `headers_strategy_key` |
| `resolvers` | `add`, `edit`, `remove` | `email`, `storage`, `challenge_type`, `provider`, `http_entrypoint`, `ca_server`, `key_type`, `eab_kid`, `eab_hmac`, `dns_resolvers`, `dns_delay`, `dns_disable_checks` |
| `plugins` | `add`, `edit`, `remove` | `moduleName`, `version`, `local` |
| `api` | `set` | `enabled`, `dashboard`, `insecure`, `debug` |
| `log` | `set` | `level`, `log_format`, `log_file`, `log_max_size`, `log_max_backups`, `log_max_age`, `log_compress`, `accessLog`, `accessLogPath`, `al_format`, `al_buffering`, `al_status_codes`, `al_min_duration`, `al_headers_mode` |
| `providers` | `set` | `docker`, `dockerEndpoint`, `dockerExposedByDefault`, `dockerWatch`, `file`, `fileDirectory`, `fileWatch`, `providers_throttle` |
| `providers` | `add`, `edit`, `remove` | `name` = provider type key, `yaml_config` = YAML body |
| `observability` | `set` | `ping`, `prometheus`, `prom_ep_labels`, `prom_router_labels`, `prom_svc_labels` |
| `system` | `set` | `check_new_version`, `send_usage`, `rule_syntax`, `st_insecure`, `st_root_cas`, `st_max_idle`, `st_dial`, `st_resp_header`, `st_idle_conn` |

Returns `{ "ok": true, "raw": "...", "parsed": { } }`. `400` for an unknown section, a missing field, or an invalid duration, CIDR or number.

On `entrypoints`, `headers_strategy_key` selects which key `underscore_headers` is written to: `aliasHeadersStrategy` (Traefik 3.7.12+) or `underscoreHeadersStrategy` (3.7.6 to 3.7.11). Anything else falls back to the older name. Only one is ever written, and saving removes the other. See [Traefik Hardening](hardening.md).

---

### `POST /api/static/trusted-ips/preview`

Compute the result of adding `forwardedHeaders.trustedIPs` to an entrypoint, without writing anything to disk. Backs the **Trusted IPs** helper in the Static Config editor.

Trusting a proxy's IP makes Traefik believe its `X-Forwarded-For`, which then feeds the access logs, CrowdSec, `ipAllowList`, and the login rate-limiter. Only trust proxies you control.

The merge is **additive with dedup**: existing entries are kept, and ranges already covered are skipped by normalized network (so `10.5.5.5/8` will not re-add `10.0.0.0/8`). Sibling keys under `forwardedHeaders`, other entrypoints and YAML comments are preserved. As with `POST /api/static/section`, the client persists the returned `raw` through [`POST /api/static/config`](#post-api-static-config).

Called in two modes.

**Inspect** (no `entrypoint`) - lists entrypoints and the presets:

```json
{ "current_raw": "entryPoints:\n  websecure:\n    address: ':443'\n" }
```

**Preview** (with `entrypoint`) - also returns the merge:

```json
{
  "current_raw": "entryPoints:\n  websecure:\n    address: ':443'\n",
  "entrypoint": "websecure",
  "cloudflare": true,
  "private": false,
  "custom_cidrs": "203.0.113.10, 198.51.100.0/24"
}
```

| Field | Type | Description |
|---|---|---|
| `current_raw` | string | Static config YAML to operate on. Falls back to the file on disk when empty. |
| `entrypoint` | string | Target entrypoint. Omit for inspect mode. |
| `cloudflare` | boolean | Include the built-in Cloudflare edge ranges. |
| `private` | boolean | Include the private-range preset (`10/8`, `172.16/12`, `192.168/16`, `fc00::/7`). |
| `custom_cidrs` | string \| string[] | Extra CIDRs or IPs, comma/whitespace-separated or an array. Invalid entries are returned in `invalid` and skipped. |

Inspect mode returns `ok`, `entrypoints` (each with `name`, `address`, `trusted_ips`), `cloudflare_captured`, `cloudflare_ranges`, and `private_ranges`. Preview mode adds `entrypoint`, `existing`, `added`, `invalid`, `final`, the merged `raw` YAML, and the `parsed` object.

Returns `400` if the named entrypoint is absent or the config is not a mapping, and `404` if there is no static config on disk and no `current_raw` was supplied.

---

## Utility

### `GET /api/manager/version`

Get the deployed Traefik Manager version.

```json
{
  "version": "1.13.0", "repo": "chr0nzz/traefik-manager", "static_config_configured": true,
  "latest": "1.13.0", "release_url": "https://github.com/chr0nzz/traefik-manager/releases/tag/v1.13.0",
  "release_notes": "...", "release_error": "",
  "traefik_latest": "v3.6.25", "traefik_release_url": "https://github.com/traefik/traefik/releases/tag/v3.6.25",
  "traefik_running": "v3.6.25"
}
```

---

### `GET /api/manager/router-names`

Router names across every protocol, from the default config file only. Useful for autocomplete.

```json
["my-app", "api"]
```

---

### `POST /api/setup/test-connection`

Test connectivity to a Traefik API URL during first-time setup. Accepts optional `user` and `password`. Requires authentication like every other `/api/` endpoint, and returns `403` once setup is complete.

```json
{ "url": "http://traefik:8080" }
```

---

### `POST /setup/test-crowdsec`

Test a CrowdSec LAPI URL and credentials during first-time setup. `404` once setup is complete, rate limited to 10/min.

```json
{ "url": "http://crowdsec:8080", "key": "..." }
```

---

### `POST /setup/test-git`

Test a git backup remote during first-time setup by running `git ls-remote`. `404` once setup is complete, rate limited to 10/min. Restricted by URL scheme (`https`, `http`, `ssh`, `git`) rather than by destination address.

```json
{ "repo_url": "https://github.com/you/traefik-backups.git", "username": "you", "token": "..." }
```

---

### `GET /api/ping`

Send a `HEAD` request to a route's domain from the TM server and return latency. Backs the route health check in the Routes tab.

| Query param | Description |
|---|---|
| `url` | Full URL to ping (must start with `http://` or `https://`) |
| `fallback` | Optional second URL, tried when the first attempt fails |

```json
{ "ok": true, "latency_ms": 42, "status_code": 200 }
```

On failure: `{ "ok": false, "error": "Timeout", "latency_ms": null }`

A URL pointing at TM's own hostname, or at the configured self-route domain, short-circuits to `{ "ok": true, "latency_ms": 0, "status_code": 200, "self": true }` without a request. A successful fallback adds `"via_target": true`. Targets that fail the SSRF guard return `400`.

---

### `POST /api/services`

Create or update a composite service without going through a route.

```json
{
  "name": "api-pool",
  "type": "weighted",
  "children": [
    { "kind": "manual",  "address": "10.0.0.10:80", "scheme": "http", "weight": 9 },
    { "kind": "service", "name": "canary-svc", "weight": 1 }
  ]
}
```

Each `manual` backend becomes its own child service named `<name>-backend-<n>`, so every row can
carry its own weight. A `service` backend is referenced by name and never copied, so changes to it
follow automatically.

`type` is `loadBalancer`, `weighted`, `mirroring` or `failover`. For `mirroring` use `percent`
instead of `weight`; the first backend is the one that serves. `failover` takes exactly two
backends and refuses a third with `400`. Pass `originalName` to rename a managed service, which
moves its children with it, along with every router and parent service that referenced the old
name, across all config files. `configFile` picks the file for a new service; an existing service is
always rewritten in the file it already lives in.

Pass `agent_id` to author on a remote agent instead of the Host. The service is written to that
agent's config files and its ownership is recorded against that server, so the same name can be
managed independently on the Host and on each agent.

Refuses with `409` if a service of that name exists and Traefik Manager does not manage it, if one
of its generated children is still used elsewhere, or if that child name already belongs to another
service; with `403` when renaming something it does not manage; and with `400` for an invalid name,
type, or a name that belongs to a TCP or UDP service.

---

### `DELETE /api/services/{name}`

Delete a managed composite service and the child services it owns.

Refuses with `409` while a router still points at it, while another service still lists it as a
backend, or while one of its generated children is still used elsewhere; `403` if Traefik Manager
does not manage it, and `404` if it does not exist.

Pass `?agent_id=<id>` to delete on a remote agent.

---

### `POST /api/services/{name}/ownership`

Take over or release management of a composite service.

```json
{ "adopt": true }
```

Pass `?agent_id=<id>` to manage a service on a remote agent.

Records a ledger entry only. **No YAML is written**, so adopting a hand-written service leaves the
config file byte for byte unchanged. Once managed, routes pointing at the service can edit their
backends from the route form instead of being read only.

Settings inside the type block that Traefik Manager does not author, such as `sticky` and
`healthCheck` on a weighted service, are preserved on later saves.

Only `weighted`, `mirroring`, `failover` and `highestRandomWeight` services can be managed. Anything
else returns `400`, and an unknown name returns `404`.

```json
{ "ok": true, "owned": true }
```

---

### `GET /api/storage/status`

Whether the directories Traefik Manager writes to are writable. It writes and removes a temporary file
in the configuration, backup and dynamic config directories, so it reports what a real save would do
rather than what the permission bits claim. The result is cached for 30 seconds.

```json
{ "problems": [] }
```

An empty array means everything is writable. Otherwise each entry names the directory and the error:

```json
{ "problems": [
  { "label": "Configuration", "path": "/app/config", "error": "read-only file system" }
] }
```

---

### `GET /api/health`

Liveness probe. The only `/api/` endpoint that needs no authentication, so it can be used as a container healthcheck.

```json
{ "ok": true }
```

---

### `GET /api/traefik/runtime`

How Traefik Manager expects to reach Traefik in order to restart it. The Static Config editor uses it to tailor its "new entrypoints need a port mapping" guidance.

```json
{ "method": "proxy", "runtime": "docker", "container": "traefik" }
```

`runtime` is `docker`, `native` or `unknown`. With `RESTART_METHOD=poison-pill` it probes the Docker API and reports `native` when the container cannot be seen.

---

### `POST /api/tools/htpasswd`

Generate an APR1 hash for a basicauth middleware.

```json
{ "username": "admin", "password": "secret" }
```

```json
{ "ok": true, "hash": "admin:$apr1$..." }
```

---

### `POST /api/tools/digestauth`

Generate an MD5 hash for a digestauth middleware. `realm` is required as well.

```json
{ "username": "admin", "realm": "traefik", "password": "secret" }
```

```json
{ "ok": true, "hash": "admin:traefik:5f4dcc3b..." }
```

---

### `GET /api/geoip/status`

Whether GeoIP is enabled, whether a database is readable, and its vintage.

---

### `POST /api/geoip/lookup`

Resolve a batch of IPs. Set `aggregate` to get per-country counts instead of per-IP detail, which is what the Logs and CrowdSec maps use.

```json
{ "ips": ["1.2.3.4", "5.6.7.8"], "aggregate": false }
```

Per-IP: `{ "enabled": true, "available": true, "results": { "1.2.3.4": { "country": "...", "country_code": "..." } } }`

Aggregated: `{ "enabled": true, "available": true, "counts": { "US": { "count": 2, "country": "United States" } }, "codes": { "1.2.3.4": "US" } }`

Duplicate and unresolvable addresses are skipped. When GeoIP is off, returns `{ "enabled": false, "available": false, "results": {} }` rather than an error.

---

### `POST /api/geoip/update`

Download the current DB-IP city-lite database. Rate-limited to 6/hour.

```json
{ "success": true, "db_month": "2026-08", "status": { } }
```

Returns `502` if the download fails.

---

### `POST /api/plugins/install`

Install a Traefik plugin by pasting the YAML from its plugin page. `static_yaml` must contain an `experimental.plugins` (or top-level `plugins`) block and is merged into the static config. `middleware_yaml` optionally creates the middleware that uses it.

| Field | Description |
|---|---|
| `static_yaml` | Required. The `experimental.plugins` snippet |
| `middleware_yaml` | Optional middleware to create alongside it |
| `middleware_file` | Dynamic config file for the middleware (default `plugin-middlewares.yml`) |
| `server` | Agent id, or empty for the Host |

```json
{ "static_yaml": "experimental:\n  plugins:\n    ...", "middleware_yaml": "...", "middleware_file": "dynamic.yml", "server": "" }
```

Returns `{ "ok": true, "plugins": ["name"] }`, plus `middleware_file` when one was written and `warning` when the plugin saved but the middleware did not. `400` for invalid YAML, no plugins block, or a middleware snippet that still contains `{{ }}` placeholders; `404` for an unknown agent or a missing static config.

---

## Middleware templates

Templates are reusable middleware snippets shown in the middlewares toolbar. They are stored on the Host and are not per-server.

### `GET /api/mw/templates`

```json
{ "templates": [{ "id": "uuid", "name": "Secure headers", "yaml": "headers:\n  ..." }] }
```

---

### `POST /api/mw/templates`

Create a template. `name` is required and truncated to 100 characters.

```json
{ "name": "Secure headers", "yaml": "headers:\n  sslRedirect: true" }
```

Returns `{ "ok": true, "template": { "id": "uuid", "name": "...", "yaml": "..." } }`.

---

### `PUT /api/mw/templates/{template_id}`

Update a template. `name` and `yaml` are both optional; only what you send is changed. `404` if the id is unknown.

---

### `DELETE /api/mw/templates/{template_id}`

Delete a template. Succeeds even if the id does not exist.

---

## CrowdSec

### `GET /api/crowdsec/decisions`

List active CrowdSec decisions (bans, captchas, bypasses). Expired ones are filtered out. Pass `?full=1` to force a full stream refresh instead of an incremental one.

`503` when no LAPI URL is configured, or when there is no bouncer API key and no client certificate - `/v1/decisions` refuses the machine token. `502` when the LAPI cannot be reached.

**Response**

```json
[
  {
    "id": 1,
    "value": "1.2.3.4",
    "type": "ban",
    "duration": "3h59m",
    "scenario": "crowdsecurity/http-bf",
    "origin": "CAPI"
  }
]
```

---

### `GET /api/crowdsec/alerts`

List recent CrowdSec alerts. The default cap is 500, configurable with the `crowdsec_alert_limit` setting or `CROWDSEC_ALERT_LIMIT`; the applied cap is returned in the `X-CS-Alert-Limit` header, and `X-CS-Alert-Capped` is `1` when the result hit it.

**Response**

```json
[
  {
    "startAt": "2026-05-28T10:00:00Z",
    "source": { "ip": "1.2.3.4" },
    "scenario": "crowdsecurity/http-bf",
    "decisions": [{ "type": "ban", "duration": "4h" }]
  }
]
```

---

### `POST /api/crowdsec/decisions`

Add a decision - ban, captcha or bypass an address or range. Written to the LAPI as an alert, using the machine
credentials when configured, otherwise the bouncer API key.

| Field | Type | Notes |
|-------|------|-------|
| `value` | string | **Required.** IP or CIDR range |
| `type` | string | `ban` (default), `captcha` or `bypass` |
| `duration` | string | Go duration, default `24h` |
| `reason` | string | Defaults to `manual ban from Traefik Manager` |

```json
{ "value": "203.0.113.10", "type": "ban", "duration": "24h", "reason": "brute force" }
```

Returns `{ "ok": true }`. Errors: `400` when `value` is missing or `type` is not one of the three,
`503` when CrowdSec is not configured, `502` when the LAPI call fails (commonly missing write permission).

### `DELETE /api/crowdsec/decisions/{id}`

Unban / remove a decision by ID.

**Response**

```json
{ "ok": true }
```

Returns `503` with `{"error": "CrowdSec not configured"}` when CrowdSec is not configured, and `500` with `{"error": "Failed to delete decision"}` when the LAPI call fails.

---

## Agents

Manage remote TMA agents registered in TM.

### `GET /api/agents`

List all registered agents. The agent API key, the Traefik API password, the CrowdSec secrets and the git token are redacted to `***`.

**Response**

```json
{
  "agents": [
    {
      "id": "uuid",
      "name": "Server 2",
      "url": "https://server2.example.com:8090",
      "api_key": "***",
      "created_at": "2026-01-01T00:00:00+00:00",
      "traefik_api_url": "http://traefik:8080",
      "config_path": "/app/config"
    }
  ]
}
```

---

### `POST /api/agents`

Register a new agent. `name` and `url` are required, and most other agent fields can be set here. `traefik_api_user`, `traefik_api_password`, `traefik_insecure_skip_verify`, `backup_dir`, `domains`, `visible_tabs`, `git_host_backup`, `git_host_branch`, `tma_port` and `tma_rate_limit` are `PUT`-only; everything not sent takes its default. TM generates the API key and returns it once as `api_key_raw` - store it immediately, it is never returned again.

`install_method` records which path added the agent: `"cli"` for the tm CLI install, `"manual"` for the compose generator. Anything else is stored as `"manual"`.

**Request body**

```json
{
  "name": "Server 2",
  "url": "https://server2.example.com:8090",
  "install_method": "cli"
}
```

`400` when `name` or `url` is missing, when the URL has no `http://` or `https://` scheme, or when it has a scheme but no host. The message names which of the three it is.

**Response**

```json
{
  "ok": true,
  "agent": {
    "id": "uuid",
    "name": "Server 2",
    "url": "https://server2.example.com:8090",
    "api_key_raw": "the-plaintext-key-shown-once",
    "api_key": "***"
  }
}
```

---

### `PUT /api/agents/{id}`

Update an agent's config fields (name, URL, paths, restart method, Traefik API basic auth, CrowdSec, git backup, visible tabs, `install_method`). Send only the fields you want to change. Secrets sent as `""` or `"***"` keep their stored value, including `traefik_api_password`. `name` is trimmed to 100 characters.

`404` for an unknown id. `400` for an empty `name`, for a `url` with no scheme or no host, or if the git branch collides with the Host's or another agent's.

::: warning
`traefik_api_password` is stored unencrypted in `agents.yml`. The agent API key, CrowdSec API key, CrowdSec machine password and git token are all encrypted; this one is not.
:::

---

### `DELETE /api/agents/{id}`

Remove an agent from TM, along with the Host's per-agent git clone at `{BACKUP_DIR}/git-agent-<id>` and that agent's `disabled_routes` and `managed_middlewares` entries in `manager.yml`. Does not stop the agent service on the remote server.

Idempotent: an unknown id returns `200` with `{"ok": true}`, not `404`.

---

### `GET /api/agents/{id}/health`

Check connectivity to an agent by calling its `/health`.

**Response**

```json
{ "ok": true, "latency_ms": 12, "version": "1.5.1", "status": 200 }
```

If the agent is unreachable, `ok` is `false` and `latency_ms` is `-1`. A TLS failure returns `ok: false` with `error` naming the untrusted agent certificate, so a certificate problem is distinguishable from a refused connection.

---

### `POST /api/agents/{id}/rotate-key`

Generate a new API key for an agent. The new key is returned once as `api_key_raw`.

```json
{ "ok": true, "agent": { "id": "uuid", "api_key": "***", "api_key_raw": "the-new-key" } }
```

The old key stops working immediately, so the agent is unreachable until its `TMA_API_KEY` is updated and it is restarted.

---

### `GET /api/agents/{id}/routes`

Routes and middlewares on that agent, in the same shape as [`GET /api/routes`](#get-api-routes) - built from the agent's config files and enriched from its Traefik API. Route objects are identical to the Host's, so a client can render either without special-casing.

```json
{
  "apps": [ /* Route[] */ ],
  "middlewares": [ /* Middleware[] */ ],
  "configErrors": [ { "file": "Agent Traefik API", "error": "..." } ],
  "services": { "http": [], "tcp": [], "udp": [] }
}
```

If the agent's Traefik API is unreachable, routes from its config files are still returned and the failure appears in `configErrors`.

---

### `GET /api/agents/{id}/cert-resolvers`

Cert resolver names to offer in the route form for that server.

```json
{ "resolvers": ["letsencrypt", "cloudflare"] }
```

Collected from the resolvers already used by that server's routers (via its Traefik API), anything in its static config when mounted, and the agent's optional `cert_resolver` field. An agent therefore does not need its static config mounted to offer resolvers.

---

### `/api/agents/proxy/{id}/{path}`

Proxy a request to the agent's API. TM injects the `X-Api-Key` header, so a browser or the mobile app reaches an agent without ever holding its key.

Accepts `GET`, `POST`, `PUT`, `DELETE` and `PATCH`. Method, query string and body are forwarded; the agent's status code and body come back as-is.

The agent's `X-*` response headers are passed back too, except `x-api-key`, `x-csrf-token`, `x-frame-options` and `x-powered-by`. This is how `X-CS-Alert-Limit` and `X-CS-Alert-Capped` reach the browser.

For example, `GET /api/agents/proxy/abc123/traefik/routers` proxies to `GET https://agent-host:8090/api/traefik/routers`.

A successful write to the agent's config, route, middleware, static or backup paths also triggers that agent's git backup push, when configured.

Returns `404` for an unknown agent, `502` if the agent refuses the connection or if its TLS certificate is not trusted by TM, `504` if it times out, and `500` for any other proxy error.

See the [Agent API Reference](api-agent.md) for every endpoint an agent exposes.

---

## OpenAPI spec

The raw OpenAPI 3.1 spec is available from your instance at:

```
https://your-tm-url/openapi.yaml
```
