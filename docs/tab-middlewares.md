# Middlewares Tab

The **Middlewares** tab manages the middleware definitions in your dynamic config files. Middlewares attach to routes to add auth, rate limiting, redirects, header injection, and more.

## What it shows

- Middleware name and Traefik type
- Protocol badge (HTTP / TCP)
- How many routes reference it
- Edit and delete controls

## Filtering and views

The filter bar has a name search, an All / HTTP / TCP protocol filter, the templates panel, and the view toggle.

**Grid** view (default) shows a type glyph, the middleware name with its Traefik type below it, the first lines of its YAML, and a footer reading `used by N routes`, `used in a chain`, or `unused` in amber. Edit and delete sit in a hover rail in the card's top right; clicking anywhere else opens the detail panel. The config file chip appears only when your middlewares span more than one file.

**List** view is a compact table: Protocol, Name, Config File, Actions.

## Creating a middleware

Click **Middleware** in the top bar.

| Field | Description |
|---|---|
| Protocol | **HTTP** (default) or **TCP**. TCP middlewares are written to `tcp.middlewares` and support `ipAllowList`, `inFlightConn` and the deprecated `ipWhiteList` - the template selector and wizard are HTTP-only, so TCP uses the YAML editor. |
| Name | Unique identifier - referenced in routes as `name@file` |
| Template | Pick a preset or choose Custom to write raw YAML |
| Config File | Shown when multiple config files are mounted (`CONFIG_DIR` / `CONFIG_PATHS`). Select an existing file or choose **+ New file...** to type a filename - the file is created automatically in `CONFIG_DIR`. Auto-suggests `middlewares-<name>.yml`. |

Paste the middleware body (e.g. `ipAllowList: ...`). A full `http:` or `tcp:` block wrapping a single middleware is also accepted and unwrapped for you; a block holding several middlewares, or a `udp:` block, is rejected.

### Wizard mode

Every template switches to **Wizard** mode - a structured form with labeled fields instead of raw YAML. Click **YAML** to switch back to the editor at any time. When you save in wizard mode the YAML is generated automatically.

### Available templates

| Category | Templates |
|---|---|
| Auth | Basic Auth, Digest Auth, Forward Auth, Forward Auth (Authentik), Forward Auth (Authelia), Forward Auth (Gatekeeper), OIDC Auth (traefik-oidc-auth) |
| Security | IP Allow List, IP Allow List (Private Ranges), Rate Limit, Secure Headers, CORS Headers, Encoded Characters (Traefik 3.7+) |
| Routing | Redirect to HTTPS, Redirect Regex, Strip Prefix, Strip Prefix Regex, Add Prefix, Replace Path, Replace Path Regex |
| Advanced | Gzip Compress, Retry, Circuit Breaker, Buffering, Middleware Chain, In-Flight Limit, Custom Error Pages, Content Type, gRPC-Web, Pass TLS Client Cert |

The Forward Auth wizards (including Authentik, Authelia, and Gatekeeper) fill **Max Response Body Size** (`maxResponseBodySize`, Traefik 3.7+) with `4096` to cap the auth server's response. Traefik warns on every forward auth middleware without it. An existing middleware missing the limit shows a warning icon on its card; clicking it opens the editor with the line added for you to review and save. See [Traefik Security Hardening](hardening.md) for the recommended hardening middlewares and options.

The **Custom Error Pages** wizard picks the service that serves the page from the services already
defined in your config, so create that service first. Use `{status}` in the query to substitute the
response code.

The **Pass TLS Client Cert** wizard covers the whole certificate (`pem`) and the four most used
`info` fields. Traefik supports more, use YAML mode for the rest.

The **IP Allow List** wizard includes a **Client IP source** (`ipStrategy`) selector. When Traefik is exposed directly, leave it on **Direct connection**. When a reverse proxy (Cloudflare, another Traefik, nginx) sits in front, the allow-list would otherwise match the proxy's IP on every request - pick **trusted hop depth** to set `ipStrategy.depth` (the number of proxies in front), or **exclude proxy IPs** to set `ipStrategy.excludedIPs` when the proxy's own addresses vary. Depth and excluded IPs are mutually exclusive, matching Traefik's own constraint.

### Custom templates

For YAML you reuse across servers, save it as a custom template: click the templates icon in the filter bar to open the **Middleware Templates** panel, then **Add Template**. Give it a name and the middleware body, without the name line above it.

Saved templates appear in the form's **Template** dropdown under **My Templates**, below the built-ins. Selecting one loads its YAML into the editor, ready to edit - a template is a starting point, not a link, so changing it later does not alter middlewares already created from it.

Templates are stored in `templates.yml` and are shared across every server. They are not per-agent, so one saved on the Host is available when an agent is selected too.

### Middleware ordering in routes

Order matters - Traefik processes middlewares left to right. The chip selector in the route form shows selected middlewares first, numbered by position, with a divider before the unselected ones.

At twelve middlewares or more the selector gains a filter box. Typing narrows the unselected pool and reports how many are hidden; already-selected middlewares always stay visible, so the form never hides what is actually attached to the route.

## Editing a middleware

Click the pencil icon on any middleware card. Editing always opens the YAML editor, even for a middleware you created through a wizard.

Renaming one moves every route that uses it to the new name, including routes in other config files.

## Deleting a middleware

Deleting one a route still uses is refused, and the message names the routes. Confirm and Traefik Manager removes it from those routes and deletes it.

## Attaching a middleware to a route

In the route form, click a chip in the **Middlewares** selector to attach or detach it. The chips come from the Traefik API and your config files; the form falls back to a comma-separated text field only when neither yields any. The `@file` suffix tells Traefik the middleware is defined in the file provider.

TCP routes have their own **Middlewares** chip selector in the route form, offering the TCP middlewares defined in your config; HTTP routes only offer HTTP middlewares.

## How it works

Middleware definitions are written to the dynamic config under `http.middlewares` or `tcp.middlewares`, in the config file you choose. Every save backs the file up first. The tab lists what is in those files; middlewares that Traefik discovers from other providers appear on that provider's own tab instead.
