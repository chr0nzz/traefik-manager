# File (external) Tab

The **File (external)** tab lists routes from Traefik's file provider that traefik-manager does **not** manage. Routes it does manage (stored in `dynamic.yml`) appear in the Routes tab instead.

## What it shows

- One card per route: status, name, rule, protocol, TLS state, service, entry points, middlewares
- Summary strip: route counts per protocol, the provider's middleware count, any route not serving, and a read-only marker
- Middlewares from the file provider, listed under the routes, when the provider has at least one route
- Search, protocol filter, refresh

Click a card for its detail panel.

Routes are **read-only** - edit them in the file provider configuration they come from.

## When it is empty

With a single dynamic file that Traefik Manager manages, this tab has nothing to show, and says so: every file provider route is on the Routes tab. The empty state names which case you are in, and the count reads `0` once the tab has loaded:

| Message | Means |
|---|---|
| Every file provider route is managed here | Traefik loads file provider routes, and all of them come from a file Traefik Manager manages |
| Traefik reports no file provider routes | Traefik is not loading any routes through its file provider |

Turn the tab off in **Settings - Route Monitoring** if you have no other file provider files.

## Enabling the tab

The tab is off until you switch it on. Traefik Manager's own routes also come from the file provider, so a file provider being present says nothing about whether there is anything external to show, and the tab is never switched on for you.

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
