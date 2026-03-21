# Routes Tab

The **Routes** tab (also called Services) is the main management interface. It displays all routes defined in `dynamic.yml` and lets you create, edit, and delete them.

## What it shows

- Route name, rule, target host:port, protocol
- TLS / cert resolver status
- Entry points and attached middlewares
- Status badge from the Traefik API (enabled / warning / error)
- Full detail view via the info button - shows live Traefik status, service health, and raw config

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

For TCP routes, enter a raw SNI rule (`HostSNI(\`*\`)` for passthrough). UDP routes route by entry point only - no rule needed.

## Editing a route

Click the pencil icon on any route card, or open the detail panel and click **Edit**.

## Deleting a route

Click the trash icon on the route card. The corresponding service entry in `dynamic.yml` is removed automatically.

## Backups

A backup of `dynamic.yml` is created automatically before every create, edit, or delete operation. Access backups via **Settings → Backups**.

## How it works

Routes are stored in `dynamic.yml` (the Traefik file provider config). traefik-manager reads and writes this file directly using `ruamel.yaml` to preserve comments and formatting. The Routes tab shows the full list from the app's config combined with live status from the Traefik API.
