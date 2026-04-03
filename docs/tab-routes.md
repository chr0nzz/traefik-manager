# Routes Tab

The **Routes** tab (also called Services) is the main management interface. It displays all routes defined in `dynamic.yml` and lets you create, edit, and delete them.

## What it shows

- Route name, rule, target host:port, protocol
- TLS / cert resolver status
- Entry points and attached middlewares
- Status badge from the Traefik API (enabled / warning / error)
- Full detail view via the info button - shows live Traefik status, service health, and raw config

## Views

Toggle between **grid** (default) and **list** view using the button in the filter bar. List view shows a compact table with Status, Protocol, Name, Domain/Rule, Target, Entry Points, and action buttons.

## Creating a route 

Click **Add Route** in the top bar. Fill in:

| Field | Description |
|---|---|
| Protocol | HTTP, TCP, or UDP |
| Name | Unique identifier (used as the router and service key in `dynamic.yml`) |
| Subdomain + Domain | Combined to form the `Host()` rule (HTTP only) |
| Target IP / Port | Backend server to forward to |
| Entry Points | Traefik entry points (e.g. `https`, `websecure`) |
| Middlewares | Comma-separated list of middleware names (e.g. `auth@file`) |
| Backend Scheme | `HTTP` or `HTTPS` - the scheme Traefik uses to connect to your backend. Use `HTTPS` when the backend serves TLS internally. |
| Pass Host Header | Enabled by default. Disable if the backend needs to see its own hostname instead of the original request `Host` header. Writes `passHostHeader: false` to the service in `dynamic.yml`. |
| Cert Resolver | Shown for HTTP and TCP routes. Select which ACME cert resolver to use. Defaults to the first resolver configured in Settings. Only appears when at least one resolver is configured. |
| Config File | Shown when multiple config files are mounted (`CONFIG_DIR` / `CONFIG_PATHS`). Select an existing file or choose **+ New file...** to type a filename - the file is created automatically in `CONFIG_DIR`. Auto-suggests `app-<name>.yml`. |

For TCP routes, enter a raw SNI rule (`HostSNI(\`*\`)` for passthrough). UDP routes route by entry point only - no rule needed.

## Editing a route

Click the pencil icon on any route card, or open the detail panel and click **Edit**.

## Deleting a route

Click the trash icon on the route card. The corresponding service entry in `dynamic.yml` is removed automatically.

## Enabling and disabling routes

Each route card has a toggle icon (green when active, grey when inactive). Clicking it:

- **Disable** - removes the router and service from `dynamic.yml` (Traefik immediately stops routing traffic) and saves the full config in `manager.yml`. The card is greyed out.
- **Enable** - restores the router and service to `dynamic.yml`. Traefik picks it up instantly.

A backup is created before each toggle operation. Disabled routes persist across restarts.

## Backups

A backup of `dynamic.yml` is created automatically before every create, edit, delete, or toggle operation. Access backups via **Settings → Backups**.

## How it works

Routes are stored in Traefik dynamic config files (the file provider config). traefik-manager reads and writes these files directly using `ruamel.yaml` to preserve comments and formatting. When multiple config files are mounted, each route card shows a small badge with its source file. The Routes tab shows the combined list from all config files plus live status from the Traefik API.
