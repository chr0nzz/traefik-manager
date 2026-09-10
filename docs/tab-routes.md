# Routes Tab

The **Routes** tab is the main management interface. It lists every route defined in your dynamic config files and lets you create, edit, and delete them.

## What it shows

- Route name, rule, target host:port, protocol
- TLS / cert resolver status
- Entry points and attached middlewares
- A status dot: red or yellow when Traefik reports a router error or warning, otherwise the result of the background reachability check (green up, yellow degraded or unconfirmed, red down, grey not checked yet). Hover for the reason and when it was checked
- Hosts and targets, each with a copy button
- A detail panel with the traffic flow, router, TLS, middleware and service data

## Empty state

With no routes yet the tab shows an **Add Route** prompt instead of a blank grid. When a search or filter matches nothing, it shows "No routes match your filters".

## Filtering

| Filter | Values |
|---|---|
| Search | Route name |
| Domain | Every domain found in your route rules |
| Status | All / Active / Inactive |
| Protocol | All / HTTP / TCP / UDP |

The heartbeat button pings every enabled HTTP route that has a concrete host right now and sets each card's status dot from the answer. A route with more than one backend server has each server checked, so one dead member reads as degraded rather than online. The next background check replaces it. The schedule is set under Settings - Notifications - Route checks.

## Views

Toggle between **grid** (default) and **list** view with the button in the filter bar. List view is a compact table: Status, Protocol, Name, Service, Domain / Rule, Target, Entry Points, Middlewares, Actions.

In grid view the name sits on the top line with small glyphs for anything worth flagging - a padlock for TLS, an open amber padlock without it, a cube for provider-managed routes, a pause for disabled ones, and a warning shield for `insecureSkipVerify`. Below it are the route's hosts and its backend target, each with a copy button; a route matching several hosts shows the first two and a `+N` you can hover for the rest, and a load-balanced route marks its target with the extra backend count. Entry points, middlewares, and the service name run along the footer. **More**, **Edit**, and an enable/disable toggle appear as a rail in the top right on hover, and clicking anywhere else on the card opens the detail panel.

The config file chip appears in the footer only when your routes span more than one file.

## Detail panel

**Use a service** lists services from every provider, not just your own config files, the same way
the middleware picker already does. Your own services come first under `This config`; the rest are
grouped by provider and marked read only, since Traefik Manager cannot edit them. Picking one writes
the qualified name, for example `whoami@docker`, and the route stops resolving if that provider ever
stops publishing it.

`noop@internal` is in that list for HTTP routes. Use it for a router whose whole job is a middleware,
such as a redirect: Traefik answers these itself, so there is no backend to check and the route is
not health checked. Traefik has no noop service for TCP or UDP.

Route, service and middleware names accept anything Traefik does, except `@ / , : { }` and names over 100 characters. Spaces and brackets are fine.

Click a card, or **More - View Details**. The panel shows a traffic flow diagram (entry points, router, service), then Router Details, TLS, Middlewares and Service sections, filled from the Traefik API where it is reachable. Middleware chips open the middleware they name.

When Traefik is not serving the route, a banner says why: the API is unreachable, Traefik has loaded nothing at all from the file provider (usually the two containers do not share the config path, or `providers.file` is not watching it), or Traefik is serving other file routes but not this one.

If the routes cannot be loaded for the selected server at all, the Routes and Middlewares grids are emptied and a banner names that server and the error, so nothing left on screen belongs to the server you switched away from.

**More** also offers **Open** (for a simple `Host()` route), **Clone**, **Raw YAML**, and **Delete**.

## App icons

Enable **Settings - Interface - Routes - Show app icons** to put an app icon next to each route name, in grid and list view. It is **off by default** and stored server-side in `manager.yml` under `ui_prefs`, so it applies to every browser and session, on the Host and on agents.

Icons use the same source and per-route overrides as the [Dashboard](tab-dashboard.md#icon): the slug is auto-detected from the route or service name and served from jsDelivr's mirror of the selfh.st icon set, and any custom icon you set on a Dashboard card (a slug or a Custom URL) is used here too. An icon that cannot be resolved falls back to a two-letter monogram in grid view, and to nothing in list view.

## Creating a route

Click **Add Route** in the top bar. Fields marked with a protocol apply to that protocol only.

| Field | Description |
|---|---|
| Protocol | HTTP, TCP, or UDP |
| Route / Service Name | Unique identifier, used as the router and service key in the config file |
| Rule Mode | *(HTTP)* **Simple** (default) builds a `Host()` rule from the Subdomain + Domain chips. **Advanced rule** takes any valid Traefik rule (`PathPrefix`, `HostRegexp`, compound rules with `&&` / `\|\|`). A route with a complex rule opens in Advanced automatically. |
| Subdomain + Domain(s) | *(HTTP, Simple mode)* The chip list combines the Domains from Settings - Connection with domains auto-detected from your existing routes, and a **+** chip takes any other domain on the spot. Several domains generate a multi-host rule: ``Host(`sub.d1.com`) \|\| Host(`sub.d2.com`)``. A Subdomain containing a dot is used as the full hostname. The domain list is a form convenience - it never affects your Traefik configuration. |
| Rule (SNI) | *(TCP)* A raw SNI rule, e.g. ``HostSNI(`db.example.com`)``. Use ``HostSNI(`*`)`` to match all TLS, or leave it empty for passthrough. |
| Backend | **Build backends** (default) - backend rows for a service this route owns. **Use a service** - point the router straight at a service already defined in your config, with no service of its own; see [Shared services](#shared-services) |
| Backends | *(HTTP)* One row per backend: its kind (**IP : Port** or **Service**), its scheme, the address or service, and a weight once there is more than one row |
| Target IP / Host + Port | *(TCP, UDP)* Backend server to forward to |
| Entry Points | Chips fetched from the Traefik API - click to toggle. `websecure` (or `https`) is pre-selected for HTTP. UDP is single-select. Falls back to a text input if the API returns no entry points. |
| Middlewares | Chips from the Traefik API and your config files - click to toggle. HTTP routes offer HTTP middlewares; TCP routes offer TCP middlewares (`ipAllowList`, `inFlightConn`). Falls back to a text input only when neither source yields any. |
| Scheme | `HTTP` or `HTTPS` - the scheme Traefik uses to reach your backend. Use `HTTPS` when the backend serves TLS itself. On HTTP routes it sits on each backend row; on TCP and UDP it is a single field. |
| Pass Host Header | *(HTTP)* Enabled by default. Disable if the backend needs to see its own hostname instead of the original `Host` header; writes `passHostHeader: false` on the service. |
| TLS Mode | *(TCP)* **No TLS**, **TLS** (reveals Cert Resolver), or **Passthrough**, which writes `tls.passthrough: true` |
| Cert Resolver | *(HTTP, TCP)* **No TLS** (default, HTTP) omits the `tls` key; a **named resolver** issues a certificate via ACME; **None (external / custom cert)** writes `tls: {}` for certificates managed in `tls.yml` or elsewhere. Named resolvers come from the Cert Resolver field in Settings plus your static config's `certificatesResolvers`, so a custom resolver needs no re-typing. A remote agent contributes its own resolvers. |
| Request wildcard certificate | Appears once TLS is on. Adds a `tls.domains` block with `main: yourdomain.com` and `sans: *.yourdomain.com` from the selected domain. Use with DNS challenge resolvers (Cloudflare, Route 53, etc.). |
| TLS Options Profile | Appears once TLS is on. Assigns a named `tls.options` profile from the [TLS Options tab](tab-tls-options.md) to this router. Leave blank for Traefik's defaults. |
| Skip TLS Verification | *(HTTP)* Adds `insecureSkipVerify: true` on a `<service>-transport` serversTransport, for backends with self-signed certificates (Proxmox, Kasm). Flags the card with a warning shield. |
| Security headers preset | *(HTTP)* Generates a tool-managed `<route>-headers` middleware and attaches it. See [Security headers preset](#security-headers-preset). |
| Optimize for streaming | *(HTTP)* Sets long `forwardingTimeouts` and forces `passHostHeader`, for media servers. See [Streaming preset](#streaming-preset). |
| Config File | Shown when multiple config files are mounted (`CONFIG_DIR` / `CONFIG_PATHS`). Pick an existing file, or **+ New file...** to name one - it is created in `CONFIG_DIR`, with `.yml` added if you omit it. |

UDP routers have no rule: they route by entry point only.

## Editing a route

Click the pencil icon on any route card, or open the detail panel and click **Edit**.

Saving rewrites only the parts the form owns: the rule, entry points, service reference, middlewares and TLS on the router, and the backends, `passHostHeader` and the insecure-TLS transport on the service. Sticky sessions, health checks and router `priority` are written when the form manages them - see [Multiple backends and load balancing](#multiple-backends-and-load-balancing). Anything else you wrote by hand is preserved, including your own `serversTransport`, and an existing route keeps the service name it already points at rather than being renamed to `<name>-service`.

::: warning Advanced service types
If a router points at a `weighted`, `mirroring`, `failover` or `highestRandomWeight` service that Traefik Manager does not manage, that service is left untouched, so editing the target field in the route form has no effect on it. Edit it on the [Services tab](tab-services.md), which can also take over managing it. A composite Traefik Manager wrote itself is editable straight from this form. A service referenced by a composite, whether or not a router also points at it, is never removed when a route is deleted or disabled.
:::

## Security headers preset

The **Security headers preset** toggle in the HTTP route form generates a middleware that sets a `Permissions-Policy` and the common security headers, so you don't have to hand-write one. It works on the Host and on remote agents alike - on an agent the middleware is written to that agent's config. When enabled on save it:

- creates a middleware named `<route>-headers` under `http.middlewares` and attaches it to the router, and
- records ownership in `manager.yml` under [`managed_middlewares`](./manager-yml#managed-middlewares) so the tool knows it created it.

The generated middleware is a **normal, visible, editable file middleware** - it appears in the [Middlewares tab](./tab-middlewares) like any other and you can hand-tune it there.

**Toggles:**

- **Permissions-Policy** - each browser feature (`geolocation`, `camera`, `microphone`, `fullscreen`, `autoplay`, `payment`, `usb`, `display-capture`, `accelerometer`, `gyroscope`, `magnetometer`) can be set to **self** (only your site), **all** (any site), or **block**. The default allows `self` for the first five and blocks the rest, written via `customResponseHeaders` so it stays version-independent.
- **HSTS** - `stsSeconds: 31536000` + `stsIncludeSubdomains` (force HTTPS for a year).
- **Content-Type nosniff**, **Frame deny** (anti-clickjacking), and a **Referrer-Policy** selector, defaulting to `strict-origin-when-cross-origin`.

**Round-trip and safety:**

- Re-opening the route reads the middleware back into the toggles. If you have hand-edited `<route>-headers` beyond what the toggles can represent, the form shows it as **custom** and leaves your content untouched - change any toggle to regenerate it, or turn the preset off to remove it.
- Turning the preset off removes the `<route>-headers` middleware, detaches it from the router, and clears the ledger entry - but only if the tool created it.
- If a middleware named `<route>-headers` already exists and was **not** created by the preset, the save is refused with a clear message so a hand-authored middleware is never overwritten. Rename or remove it first.
- Renaming a route moves its `<route>-headers` middleware to match the new name.

The preset is driven entirely by the route form. Clients that do not send its fields - the mobile app, your own API calls - leave the middleware exactly as it is.

## Streaming preset

The **Optimize for streaming** toggle tunes an HTTP route for media servers (Jellyfin, Emby, Plex), where long transcodes otherwise time out and seeking breaks. Available on the Host and on remote agents. On save it:

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

Like the headers preset, streaming is written only from the route form; other clients leave the transport untouched.

## Multiple backends and load balancing

An HTTP, TCP, or UDP route can point at more than one backend. Click **Add backend** under the target fields to add another server; Traefik load-balances across them (`loadBalancer.servers`). Route cards show a **+N** badge when a route has more than one backend.

For HTTP routes, each backend row is either an **IP : Port** or an existing **Service**. With only
IP:Port rows the route keeps a plain `loadBalancer`, byte for byte as before. The moment any row
references a service, and there is more than one row, a weight field appears on every row and a
**Combine backends as** selector picks how they combine - Weighted, Mirroring or Failover. Each IP:Port row then becomes its own
child service named `<route>-backend-<n>`, so a 90/10 split between two raw addresses works, and a
referenced service is stored by name, never copied. Removing the service rows again reverts the
route to a plain `loadBalancer` and removes the generated children.

For HTTP routes, the **Load balancing** section adds:

| Option | Writes | Notes |
|---|---|---|
| Sticky sessions | `loadBalancer.sticky.cookie` | Pins a client to one backend via a cookie. Cookie name, `secure` and `httpOnly` are optional. |
| Health check | `loadBalancer.healthCheck` | Path is required; interval and timeout take a number plus `ms`, `s`, `m` or `h`. A bare number is read as seconds. |
| Router priority | `router.priority` | Higher wins when several routers match the same request. Negative values are allowed, which is how you make a wildcard catchall lose against every explicit route. `0` means unset and is not written. Also available for TCP routes. |

These round-trip on edit, so reopening a route shows the backends and settings it already has.

Every route needs at least one backend host. A save that does not supply one is rejected rather than written, so a route can never end up pointing at an empty address.

::: tip Older clients are safe
The mobile app and older cached pages post only a single target. Saving from one of those updates the first backend only - additional backends, sticky sessions, health checks, and priority are preserved rather than wiped.
:::

## Shared services

Several routers can point at the same service - a native Traefik pattern, useful when one backend needs different middlewares per hostname (an internal name with no auth, an external one behind Authelia) or when an edge Traefik fans several domains into the same downstream instance (#125).

Switch the **Backend** toggle to **Use a service** and pick any service from your config files. The route then writes only a router with `service: <name>`; that route never creates, modifies, or deletes the service block. The picker lists file-provider services for the active server across all config files.

Behavior worth knowing:

- Deleting or disabling a route never removes a service another router still references.
- Deleting the route that originally created a shared service keeps the service as long as another router points at it.
- Editing a route that references a shared service keeps the reference; backends, sticky sessions and health checks are managed where the service is defined - through the route that owns it, or in YAML.
- Older clients editing a referenced route cannot convert it into an owned service - the reference is preserved server-side.
- Hand-written cross-provider references such as `service: whoami@docker` are preserved on edit, but the picker does not create them.

## Deleting a route

Open **More - Delete** on the route card and type `DELETE` to confirm. The route's service entry is removed with it, unless another router still references it. The `<service>-transport` `serversTransport` that traefik-manager generated for that service goes too, unless another service or a disabled route still points at it.

## Entrypoint middlewares

When a static config is readable (`STATIC_CONFIG_PATH`, or the path set under **Settings - System Monitoring - File Paths**), traefik-manager reads `entryPoints[name].http.middlewares` and lists those middlewares on the cards of every route bound to that entry point, marked `ep` with an "Applied via entrypoint" tooltip. They are read-only here and managed in the static config.

## Bulk actions

Click the **selection icon** in the filter bar to enter bulk mode. Each route card shows a checkbox - tick the ones you want to act on. A sticky action bar appears at the bottom with:

- **Enable** - enables all selected routes
- **Disable** - disables all selected routes
- **Delete** - deletes all selected routes, confirmed by typing `DELETE`

Click the X in the action bar or the selection button again to exit bulk mode.

## Enabling and disabling routes

Each route card has a toggle in its hover rail. Clicking it:

- **Disable** - removes the router and service from the config file (Traefik immediately stops routing traffic) and saves the full config in `manager.yml`. The card is greyed out.
- **Enable** - restores the router and service to the config file. Traefik picks it up instantly.

A shared service is left in place when a route that references it is disabled. A backup is created before each toggle. Disabled routes persist across restarts.

## Backups

A backup is created automatically before every create, edit, delete, or toggle operation. Access backups via **Settings - Backups**.

## How it works

Routes are stored in Traefik dynamic config files (the file provider config). traefik-manager reads and writes these files directly using `ruamel.yaml` to preserve comments and formatting. The tab shows the combined list from all config files plus live status from the Traefik API.
