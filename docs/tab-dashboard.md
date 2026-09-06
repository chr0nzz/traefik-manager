# Dashboard Tab

The **Dashboard** tab shows all your Traefik routes grouped by category, with app icons, per-route editing and custom groups. Rows and tiles are clickable, so the Dashboard doubles as a homepage-style launcher for your services.

## Enabling the tab

Enable this tab via **Settings - Interface - Tabs - Dashboard**, or in the setup wizard. The preference is saved to `manager.yml` and persists across restarts.

---

## Groups view

Routes are automatically grouped into categories by name - Media, Monitoring, Infrastructure, Security, Home, Files & Data, Network, Dev, Servers, and Other. Each group is a pod: a flat header of icon, name and count, a hairline rule, then its routes. **Other** always sorts last, custom groups sit between the built-ins and Other, and routes inside a pod are sorted alphabetically by the name you see.

Pod headers and healthy rows are neutral. Colour is spent only where something needs attention.

### Route rows

A healthy, launchable route is a single flat line: icon plate, name, host. A row grows a second line **only** when there is a reason it cannot be launched or is not working, so "this row is two lines tall" is itself the signal.

Each route row shows:

- **App icon plate with a status dot** - the icon comes from the selfh.st icon set. When no icon matches, the plate shows a two-letter monogram of the display name instead of an empty box. Images are lazy-loaded, and only the visible rows are built
- **Name** - display name (customisable) or route name. The whole row is the launch target, so middle-click, ctrl-click and "open in new tab" work anywhere on it
- **Protocol tag** - a flat, muted `TCP` or `UDP` for non-HTTP routes
- **Host** - the launch host at the right of the name line, in monospace. The scheme is printed only when it is not `https`, so `http://plex.lan:32400` reads as such and everything else reads as a bare host. Unlaunchable routes show the backend target here instead. The host is dropped on very narrow pods so the name never truncates first
- **Note** - the exception line: `backend unreachable 0/2 servers`, `backend degraded 1/2 servers`, `router error, missing middleware authelia`, `disabled, not served by Traefik`, `stream route, nothing to open`, `no launch URL, wildcard host. Set one in edit`, `declared here, not reported by Traefik`

Everything else the tab knows - backend target, provider, entry points, server count, middleware names, cert resolver, config file - is in the row's tooltip; full detail stays in the route panel.

### The status dot

The dot on the icon plate has these states:

| Dot | Meaning |
|-----|---------|
| Green square | Every backend server up, where Traefik reports backend health |
| Quiet grey square | Router loaded, but Traefik reports no backend health for the service |
| Hollow square | Route disabled, loaded but not enabled, or the Traefik API did not answer |
| Hollow circle | Traefik is answering but has never reported this router |
| Yellow | Backend degraded, some servers up and some down |
| Red with a glow | Router errored, or every backend server down |

Backend health comes from `serverStatus` in the Traefik API. Traefik only reports it for services that have a health check configured. Without one the dot stays grey rather than green, because Traefik cannot tell us whether the app behind the route is actually answering.

Every dot carries a full-sentence tooltip. When the Traefik API cannot be read at all, the tab says so once above the pods rather than drawing an unexplained ring on every route, so "Traefik answered with no routers" and "Traefik did not answer" stay distinguishable.

Disabled routes are shown dimmed, with a `disabled, not served by Traefik` note. They sort to the end of their category so they never push a live app behind **N more**.

### Failure at a glance

A pod with a failing route gets a red left spine, a red-tinted border, and a `2 down` flag in its header. The flag is a button: clicking it expands the pod and jumps to the first failing route. A pod whose only trouble is a degraded backend gets the same treatment in yellow. A healthy pod shows none of this.

### Icons view

Under **Settings - Interface - Dashboard** you can switch **Dashboard categories** from **Rows** to **Icons**. Tiles are not shrunken rows: a grid of 40px icon plates with the app name under each, and nothing else. The column count follows the pod's own width rather than the viewport, so a narrow pod gets four across and a wide one gets more.

Icons view keeps the same plate, the same monogram fallback, and the same status dot with the same tooltip. A failing tile also takes a coloured ring, since a 7px dot is too weak at tile scale. Tiles with nothing to launch are dimmed and inert.

Each tile has two corner buttons, revealed on hover and always visible on touch: an info button top-left that opens the route detail panel, and a pencil top-right that opens the card editor.

### Launching apps

Clicking a row or tile opens the service in a new tab. The URL is derived from the route itself: the first usable `Host` in the rule, `https` when the router has TLS enabled and `http` otherwise, with the `PathPrefix` **from the same `||` branch as that host** appended. A rule like ``Host(`a.com`) || (Host(`b.com`) && PathPrefix(`/x`))`` therefore opens `https://a.com`, not `https://a.com/x`.

Hovering a row reveals two buttons at its right: an info button that opens the route detail panel, and the pencil that opens the card editor. Both are real buttons, so Enter and Space work. On touch they are permanently visible at a larger size instead of hidden behind a hover.

Rows and tiles for routes with nothing to open stay unlinked, and say why: TCP and UDP routes, `HostSNI` and regex rules, rules without a `Host`, wildcard hosts, and cards with the link disabled. A link override that is not an `http://` or `https://` URL is treated the same way, whether it was typed into the editor or written straight into `dashboard.yml` by hand.

### Expand / collapse

Groups with more than 6 routes (24 in Icons view) show only the first few. Click **N more** at the bottom of the pod to expand, **show less** to collapse. Only the visible rows are built, so a 200-route category does not fire 200 icon requests for content you cannot see.

The expander reports the health of what it is hiding: when the hidden set contains a failure it takes a red spine and appends `· 1 down`, so a red dot can never sit silently behind a neutral grey button. Expansion survives a re-render, so typing in the search box or saving a group edit does not re-collapse every pod.

---

## Per-card editing

Click the pencil that appears on a route row when you hover it, or in the corner of an icon tile, to open the **Card settings** panel. It slides in from the right like the other editors.

Everything here changes how the app looks on the dashboard. None of it touches the route itself, so nothing you do in this panel affects how traffic is served.

### Display name

Override the route name shown in the card. Leave blank to use the original route name.

### Icon

Three modes:

- **Auto** - icon is auto-detected from the route or service name
- **selfh.st slug** - enter a slug directly (e.g. `plex`, `grafana`) - see [selfh.st/icons](https://selfh.st/icons/) for available icons
- **Custom URL** - enter any direct image URL to use as the icon

Icons are requested by the browser from jsDelivr (`cdn.jsdelivr.net/gh/selfhst/icons`), so the browser needs to reach it. If a slug does not resolve, the plate falls back to a two-letter monogram of the display name. (A server-side caching endpoint exists at `/api/dashboard/icon/<slug>` but the frontend does not use it yet.)

If a self route is configured for Traefik Manager (**Settings - Connection - Self route**), its dashboard card automatically shows the Traefik Manager icon instead of a CDN lookup.

These per-route icon overrides are also used by the [Routes tab](tab-routes.md#app-icons) when its **Show app icons** option is enabled, so an icon you set here appears there too.

### Group assignment

Override which group the route belongs to. Select **Auto-detect** to let the keyword matching decide, or pick any built-in or custom group.

### Link URL

Override the URL the card opens, for cards where the route's URL is not the right landing page - for example a route that serves an API while the UI lives elsewhere. Only `http://` and `https://` URLs are accepted, on save, on read and again at render time. The **Do not make this card clickable** checkbox turns the card back into a plain informational row.

---

## Custom groups

Click the sliders button in the filter bar to open the **Dashboard settings** panel. It slides in from the right and manages both custom groups and hidden apps.

Routes not matched by any built-in category go into **Other**. Custom groups let you catch specific routes and give them their own card instead.

To add a group: enter a name. Routes are assigned to it via the pencil on each route row or icon tile - select the group in the Group assignment field. Custom groups appear at the top of the group dropdown in Card settings.

A custom group with no routes assigned yet still renders as an empty pod with a line telling you how to fill it, so a group you just created is never invisible. It is hidden while a search or filter is active.

Custom groups are saved to `/app/config/dashboard.yml` (next to `manager.yml`) and persist across restarts.

Groups and every per-card override are stored **per server**. A group you create while an agent is selected belongs to that agent alone and does not appear on the Host or on your other agents, and two servers with a route of the same name keep separate icons, names and links.

---

## Hiding apps

Tick **Hide from the dashboard** in Card settings to drop an app from the dashboard. It disappears from both the list and icon views straight away.

Hiding is a dashboard-view setting only. The route keeps running, keeps serving traffic, and still appears on the [Routes](tab-routes.md) tab and everywhere else. Nothing is disabled.

Hidden apps are listed under **Hidden apps** in the Dashboard settings panel, each with a **show** button to put it back. The section header carries the count.

Useful for routes that are real but not things you launch: API-only routers, health endpoints, internal services, or the second and third hostname of an app you already have a card for.

---

## Group detection

Groups are assigned automatically by matching the route or service name against a built-in keyword list. The list is checked **in table order** and the first match wins, so a keyword that appears in an earlier group is never reached by a later one. Routes that match nothing go into **Other**.

| Group | Matches |
|-------|---------|
| Media | jellyfin, sonarr, radarr, immich, qbittorrent, plex, prowlarr, ... |
| Monitoring | grafana, prometheus, uptime, kuma, glances, speedtest, ... |
| Infrastructure | traefik, portainer, gitea, gitlab, forgejo, drone, jenkins, proxmox, cockpit, n8n, komodo, ... |
| Security | authentik, authelia, vaultwarden, crowdsec, wireguard, ... |
| Home | home-assistant, node-red, esphome, zigbee2mqtt, frigate, ... |
| Files & Data | nextcloud, paperless, mealie, bookstack, syncthing, ... |
| Network | pihole, adguard, unifi, tailscale, ... |
| Dev | code-server, coder, argocd, harbor, sonar, jupyter, woodpecker, airflow, ... |
| Servers | idrac, ipmi, esxi, truenas, freenas, opnsense, pfsense, unraid, synology, ... |
| Other | everything else |

Because Infrastructure is checked before Dev and Servers, the git and CI keywords (`gitea`, `gitlab`, `forgejo`, `drone`, `jenkins`) and the hypervisor keywords (`proxmox`, `cockpit`) always land in Infrastructure. Use the pencil on a route to move it elsewhere.

---

## Filtering

- **Search** - matches the display name, the route name, the service name, the backend target, and the hosts in the rule, so searching for what you can see works even when a route is renamed. Debounced, so typing does not rebuild the grid on every keystroke
- **Protocol** - show only HTTP, TCP, or UDP routes
- **Provider** - filter by Traefik provider (file, docker, kubernetes, etc.). Only appears when routes from more than one provider are present

When a filter matches nothing, the tab names the filters responsible and offers **clear search** and **reset all filters**. That is a different panel from the one shown when there are genuinely no routes yet.

On a phone the protocol buttons, the provider buttons and the Dashboard settings button collapse behind the filter bar's **more filters** control instead of being clipped off the edge of the screen.

---

## Providers

Routes from all Traefik providers are shown - not just file-based routes. Docker, Kubernetes, Consul Catalog, and other dynamic provider routes appear alongside file routes.

Routes from non-file providers are read-only: the per-card pencil lets you customise the display name and icon, but the route config itself (rule, service, entry points) can only be changed through the provider that manages it. The route detail panel's Edit button is hidden for these routes.

---

## Data source

Fetches from:

- `/api/routes/all` - routes from all providers (file-managed + live from Traefik API); `/api/agents/<id>/routes` when a remote agent is selected
- `/api/traefik/entrypoints` - entry point names from the Traefik API
- `/api/dashboard/config` - custom groups and per-route overrides from `dashboard.yml`
- `/api/traefik/routers` - live router state for the status dot
- `/api/traefik/services` - `serverStatus` per backend server, for the degraded and unreachable dot states

Router and service state is keyed on the full `name@provider`, so `whoami@docker` and `whoami@file` do not collapse into one entry and show each other's status.

Data is cached for 30 seconds and shared with the Route Map tab. Opening the tab re-renders it, and refetches once the cache is older than that, so config changes made outside this browser tab (another session, the static config editor, or a direct file edit) appear without a page reload. Adding, editing, deleting, or toggling a route refreshes it immediately.

If the route list itself cannot be read, the tab shows a panel explaining that with a **retry** button, rather than a filter bar over an empty screen. If only the Traefik API calls fail, the pods still render from your config with one line above them saying live status is unavailable.
