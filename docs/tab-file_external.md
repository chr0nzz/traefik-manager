# File (external) Tab

The **File (external)** tab lists routes from Traefik's file provider that traefik-manager does **not** manage. Routes it does manage (stored in `dynamic.yml`) appear in the Routes tab instead.

## What it shows

- One card per route: status, name, rule, protocol, TLS state, service, entry points, middlewares
- Summary strip: route counts per protocol, the provider's middleware count, any route not serving, and a read-only marker
- Middlewares from the file provider, listed under the routes, when the provider has at least one route
- Search, protocol filter, refresh

Click a card for its detail panel.

Routes are **read-only** - edit them in the file provider configuration they come from.

## Enabling the tab

This tab switches itself on the first time Traefik reports routers from this provider, and the setup wizard pre-selects it when the provider is already running. Turn it off and it stays off.

| Where | Path |
|---|---|
| Setup wizard | Monitoring step → Provider tabs → File (external) |
| Later | Settings → Route Monitoring → File (external) |

## Requirements

Traefik must be configured with the file provider, pointing at a directory or a single file in your `traefik.yml`:

```yaml
providers:
  file:
    directory: "/etc/traefik/conf.d"
    watch: true
```

or:

```yaml
providers:
  file:
    filename: "/etc/traefik/extra-routes.yml"
```

No mounts into traefik-manager needed - data comes live from the Traefik API.

> **Note:** traefik-manager's own `dynamic.yml` also uses the file provider, so its routers are excluded here to avoid duplication. The exclusion reads the first config file only, so with several files mounted (`CONFIG_DIR` / `CONFIG_PATHS`) managed routes from the additional files can still appear in this tab.
