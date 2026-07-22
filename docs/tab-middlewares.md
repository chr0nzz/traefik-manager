# Middlewares Tab

The **Middlewares** tab manages all middleware definitions stored in `dynamic.yml`. Middlewares can be attached to HTTP routes to add auth, rate limiting, redirects, header injection, and more.

## What it shows

- Middleware name and type
- Live status from the Traefik API (enabled / warning / error)
- Protocol badge (HTTP / TCP)
- Edit and delete controls

## Views

Toggle between **grid** (default) and **list** view using the button in the filter bar. List view shows Protocol, Name, Config File, and action buttons in a compact table.

## Creating a middleware 

Click **Add Middleware** in the top bar.

| Field | Description |
|---|---|
| Protocol | **HTTP** (default) or **TCP**. TCP middlewares are written to `tcp.middlewares` and support only `ipAllowList` and `inFlightConn` - the template selector and wizard are HTTP-only, so TCP uses the YAML editor. |
| Name | Unique identifier - referenced in routes as `name@file` |
| Template | Pick a preset or choose Custom to write raw YAML |
| Config File | Shown when multiple config files are mounted (`CONFIG_DIR` / `CONFIG_PATHS`). Select an existing file or choose **+ New file...** to type a filename - the file is created automatically in `CONFIG_DIR`. Auto-suggests `middlewares-<name>.yml`. |

Paste only the middleware configuration body (e.g. `ipAllowList: ...`) - a full `http:`/`tcp:` config block is rejected with an error.

### Wizard mode

Every template switches to **Wizard** mode - a structured form with labeled fields instead of raw YAML. Click **YAML** to switch back to the editor at any time. When you save in wizard mode the YAML is generated automatically.

### Available templates

| Category | Templates |
|---|---|
| Auth | Basic Auth, Digest Auth, Forward Auth, Forward Auth (Authentik), Forward Auth (Authelia), Forward Auth (Gatekeeper) |
| Security | IP Allow List, IP Allow List (Private Ranges), Rate Limit, Secure Headers, CORS Headers, Encoded Characters (Traefik 3.7+) |
| Routing | Redirect to HTTPS, Redirect Regex, Strip Prefix, Add Prefix, Replace Path |
| Advanced | Gzip Compress, Retry, Circuit Breaker, Buffering, Middleware Chain, In-Flight Limit |

The Forward Auth wizards (including Authentik, Authelia, and Gatekeeper) expose an optional **Max Response Body Size** field (`maxResponseBodySize`, Traefik 3.7+) to cap the auth server's response. See [Traefik Security Hardening](hardening.md) for the recommended hardening middlewares and options.

The **IP Allow List** wizard includes a **Client IP source** (`ipStrategy`) selector. When Traefik is exposed directly, leave it on **Direct connection**. When a reverse proxy (Cloudflare, another Traefik, nginx) sits in front, the allow-list would otherwise match the proxy's IP on every request - pick **trusted hop depth** to set `ipStrategy.depth` (the number of proxies in front), or **exclude proxy IPs** to set `ipStrategy.excludedIPs` when the proxy's own addresses vary. Depth and excluded IPs are mutually exclusive, matching Traefik's own constraint.

### Middleware ordering in routes

When attaching middlewares to a route, order matters - Traefik processes them left to right. The middleware chip selector in the route form shows selected middlewares first (numbered by position) with a divider before unselected ones, so you can see the processing order at a glance.

## Editing a middleware

Click the pencil icon on any middleware card.

## Attaching a middleware to a route

When creating or editing a route, enter middleware names in the **Middlewares** field as a comma-separated list, e.g. `auth@file, redirect-https@file`. The `@file` suffix tells Traefik the middleware is defined in the file provider.

TCP routes have their own **Middlewares** chip selector in the route form, offering the TCP middlewares defined in your config; HTTP routes only offer HTTP middlewares.

## How it works

Middleware definitions are written to the dynamic config under `http.middlewares`. When multiple config files are mounted, each middleware card shows a small badge with its source file. traefik-manager reads the live status for each from the Traefik API (`/api/http/middlewares`).
