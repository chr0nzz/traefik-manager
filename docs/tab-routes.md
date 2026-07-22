# Routes Tab

The **Routes** tab (also called Services) is the main management interface. It displays all routes defined in `dynamic.yml` and lets you create, edit, and delete them.

## What it shows

- Route name, rule, target host:port, protocol
- TLS / cert resolver status
- Entry points and attached middlewares
- Status badge from the Traefik API (enabled / warning / error)
- Multi-domain routes show each domain as a separate pill badge; clicking a domain or target copies it to the clipboard
- Full detail view via the info button - shows live Traefik status, service health, and raw config

## Empty state

When no routes exist yet - such as on a fresh install - the tab shows a prompt with an **Add Route** button instead of a blank grid. When a search or filter matches nothing, it shows a "No routes match your filters" message instead.

## Filtering

The filter bar above the grid lets you narrow routes by:

- **Search** - matches against route name
- **Domain** - dropdown of all unique domains extracted from route rules
- **Status** - All / Active / Inactive. Inactive routes are disabled (greyed out) and can be shown or hidden independently of other filters
- **Protocol** - All / HTTP / TCP / UDP

## Views

Toggle between **grid** (default) and **list** view using the button in the filter bar. List view shows a compact table with Status, Protocol, Name, Domain/Rule, Target, Entry Points, and action buttons.

## App icons

Enable **Settings - Interface - Routes - Show app icons** to display an app icon next to each route name, in both grid and list view. The toggle is **off by default** and is a per-browser preference (it applies to the Host and to remote agents).

Icons use the same source and per-route overrides as the [Dashboard](tab-dashboard.md#icon): the slug is auto-detected from the route or service name via the selfh.st CDN. Any custom icon you set on a Dashboard card (a selfh.st slug or a Custom URL, for apps the name match does not recognize) is read from the dashboard config and shown on the Routes tab too. If an icon cannot be resolved it is hidden - no broken-image placeholder.

## Creating a route 

Click **Add Route** in the top bar. Fill in:

| Field | Description |
|---|---|
| Protocol | HTTP, TCP, or UDP |
| Name | Unique identifier (used as the router and service key in `dynamic.yml`) |
| Rule Mode | **Simple** (default) - use the Subdomain + Domain chip builder to generate a `Host()` rule. **Advanced rule** - type any valid Traefik rule directly (`PathPrefix`, `HostRegexp`, compound rules with `&&` / `\|\|`, etc.). Switch modes with the Simple / Advanced rule toggle at the top of the HTTP section. When editing a route with a complex rule, the form automatically opens in Advanced mode. |
| Subdomain + Domain(s) | *(Simple mode only)* Subdomain field plus one or more domain chips. The chip list combines the Domains from Settings - Connection with domains **auto-detected from your existing routes**, and a **+** chip lets you type any other domain on the spot - no Settings trip required. With multiple domains selected, generates a multi-host rule: `Host(\`sub.d1.com\`) \|\| Host(\`sub.d2.com\`)`. Entering a full hostname (with dots) in the Subdomain field uses it as-is. The domain list is a form convenience only - it never affects your Traefik configuration. Long domain names are truncated in the chip display. |
| Target IP / Port | Backend server to forward to |
| Entry Points | Selectable chips fetched from the Traefik API - click to toggle. `websecure` is pre-selected for HTTP routes. UDP entry points are single-select. Falls back to a text input if the API returns no entry points. |
| Middlewares | Selectable chips fetched from the Traefik API - click to toggle. Falls back to a text input if the API returns no middlewares. HTTP routes offer HTTP middlewares; the TCP form has its own Middlewares chips offering TCP middlewares (`ipAllowList`, `inFlightConn`). |
| Backend Scheme | `HTTP` or `HTTPS` - the scheme Traefik uses to connect to your backend. Use `HTTPS` when the backend serves TLS internally. |
| Pass Host Header | Enabled by default. Disable if the backend needs to see its own hostname instead of the original request `Host` header. Writes `passHostHeader: false` to the service in `dynamic.yml`. |
| Cert Resolver | Shown for HTTP and TCP routes. Three options: **No TLS** (default) - omits the `tls` key entirely; **named resolver** - uses ACME to issue a certificate; **None (external / custom cert)** - writes `tls: {}` without a resolver, for certificates managed via `tls.yml` or another external source. Named resolvers are detected automatically from your static config's `certificatesResolvers` (and from the Cert Resolver field in Settings), so a custom resolver shows up in the dropdown without re-typing it. When a remote agent is active, the agent's static config is read for its resolvers. |
| Request wildcard certificate | Appears when a cert resolver is selected. Check this to add a `tls.domains` block with `main: yourdomain.com` and `sans: *.yourdomain.com` auto-filled from the selected domain. Use with DNS challenge resolvers (Cloudflare, Route 53, etc.) to request a wildcard certificate that covers all subdomains. |
| TLS Options Profile | Appears when a cert resolver is selected. Select a named `tls.options` profile from the TLS Options tab to assign it to this router (e.g. `modern`, `strict`). Leave blank to use Traefik's default TLS settings. |
| Skip TLS Verification | Adds `insecureSkipVerify: true` via a named `serversTransport` entry. Use for backends with self-signed certificates (e.g. Proxmox, Kasm). A yellow **TLS skip** badge appears on the route card. |
| Security headers preset | *(HTTP only)* Generates a tool-managed `<route>-headers` middleware with a `Permissions-Policy` and common security headers, and attaches it to the router. See [Security headers preset](#security-headers-preset) below. |
| Optimize for streaming | *(HTTP only)* Sets long `forwardingTimeouts` on the service's `serversTransport` and forces `passHostHeader`, for media servers (Jellyfin/Emby/Plex). See [Streaming preset](#streaming-preset) below. |
| Config File | Shown when multiple config files are mounted (`CONFIG_DIR` / `CONFIG_PATHS`). Select an existing file or choose **+ New file...** to type a filename - the file is created automatically in `CONFIG_DIR`. The `.yml` extension is added automatically if omitted. |

For TCP routes, enter a raw SNI rule (`HostSNI(\`*\`)` for passthrough). UDP routes route by entry point only - no rule needed.

## Editing a route

Click the pencil icon on any route card, or open the detail panel and click **Edit**.

Saving only rewrites the parts of the route the form owns: the rule, entry points, service reference, middlewares and TLS on the router, and the first server address, `passHostHeader` and the insecure-TLS transport on the service. Anything else you have written by hand is preserved - router `priority`, sticky sessions, health checks, additional servers, and your own `serversTransport`. An existing route also keeps the service name it already points at, rather than being renamed to `<name>-service`.

::: warning Advanced service types
If a router points at a `weighted`, `mirroring` or `failover` service instead of a `loadBalancer`, that service is left untouched, so editing the target field in the modal has no effect on it. Edit those services directly in the config file.
:::

## Security headers preset

The **Security headers preset** toggle in the HTTP route form generates a middleware that sets a `Permissions-Policy` and the common security headers, so you don't have to hand-write one. When enabled on save it:

- creates a middleware named `<route>-headers` under `http.middlewares` and attaches it to the router, and
- records ownership in `manager.yml` under [`managed_middlewares`](./manager-yml#managed-middlewares) so the tool knows it created it.

The generated middleware is a **normal, visible, editable file middleware** - it appears in the [Middlewares tab](./tab-middlewares) like any other and you can hand-tune it there.

**Toggles:**

- **Permissions-Policy** - each browser feature (`geolocation`, `camera`, `microphone`, `fullscreen`, `autoplay`, `payment`, `usb`, `display-capture`, `accelerometer`, `gyroscope`, `magnetometer`) can be set to **self** (only your site), **all** (any site), or **block**. The default allows `self` for the first five and blocks the rest, written via `customResponseHeaders` so it stays version-independent.
- **HSTS** - `stsSeconds: 31536000` + `stsIncludeSubdomains` (force HTTPS for a year).
- **Content-Type nosniff**, **Frame deny** (anti-clickjacking), and a **Referrer-Policy** selector.

**Round-trip and safety:**

- Re-opening the route reads the middleware back into the toggles. If you have hand-edited `<route>-headers` beyond what the toggles can represent, the form shows it as **custom** and leaves your content untouched - change any toggle to regenerate it, or turn the preset off to remove it.
- Turning the preset off removes the `<route>-headers` middleware, detaches it from the router, and clears the ledger entry - but only if the tool created it.
- If a middleware named `<route>-headers` already exists and was **not** created by the preset, the save is refused with a clear message so a hand-authored middleware is never overwritten. Rename or remove it first.
- Renaming a route moves its `<route>-headers` middleware to match the new name.

The preset is available for local (file-provider) HTTP routes; routes on a remote agent are unaffected.

## Streaming preset

The **Optimize for streaming** toggle tunes an HTTP route for media servers (Jellyfin, Emby, Plex), where long transcodes otherwise time out and seeking breaks. On save it:

- sets `forwardingTimeouts` on the service's `<service>-transport` serversTransport (`responseHeaderTimeout: 0s` - unlimited, so long transcodes aren't cut off - plus a `dialTimeout` and `idleConnTimeout`), and
- forces `passHostHeader` on.

```yaml
serversTransports:
  jellyfin-transport:
    forwardingTimeouts:
      dialTimeout: "30s"
      responseHeaderTimeout: "0s"
      idleConnTimeout: "90s"
```

It shares the same `<service>-transport` as [Skip TLS Verification](#creating-a-route), so the two compose: turning one off leaves the other's key in place, and the transport is removed only when both are off. Turning streaming off removes just the `forwardingTimeouts` key.

Streaming works best **without response buffering** - if a `buffering` or `compress` middleware is attached to the route, the form warns you to remove it. Entry-point `respondingTimeouts` are global and static, so they are not changed here; adjust them in the [Static Config editor](./static) if long transcodes still cut off.

Like the headers preset, streaming is managed only through the route modal for local HTTP routes; API, agent and other saves leave the transport untouched.

## Deleting a route

Click the trash icon on the route card. The corresponding service entry in `dynamic.yml` is removed automatically.

## Entrypoint middlewares

When `STATIC_CONFIG_PATH` is set, traefik-manager reads `entryPoints[name].http.middlewares` from the static config and shows those middlewares as grey **ep** chips on route cards - one chip per middleware inherited from a matched entry point. Hovering the chip shows "Applied via entrypoint". These are read-only and managed in the static config, not the dynamic config.

## Bulk actions

Click the **selection icon** in the filter bar to enter bulk mode. Each route card shows a checkbox - tick the ones you want to act on. A sticky action bar appears at the bottom with:

- **Enable** - enables all selected routes
- **Disable** - disables all selected routes
- **Delete** - deletes all selected routes after a confirmation prompt

Click the X in the action bar or the selection button again to exit bulk mode.

## Enabling and disabling routes

Each route card has a toggle icon (green when active, grey when inactive). Clicking it:

- **Disable** - removes the router and service from `dynamic.yml` (Traefik immediately stops routing traffic) and saves the full config in `manager.yml`. The card is greyed out.
- **Enable** - restores the router and service to `dynamic.yml`. Traefik picks it up instantly.

A backup is created before each toggle operation. Disabled routes persist across restarts.

## Backups

A backup of `dynamic.yml` is created automatically before every create, edit, delete, or toggle operation. Access backups via **Settings → Backups**.

## How it works

Routes are stored in Traefik dynamic config files (the file provider config). traefik-manager reads and writes these files directly using `ruamel.yaml` to preserve comments and formatting. When multiple config files are mounted, each route card shows a small badge with its source file. The Routes tab shows the combined list from all config files plus live status from the Traefik API.
