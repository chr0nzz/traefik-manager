# Docker Tab

The **Docker** tab lists the routes Traefik discovered through its Docker provider.

## What it shows

- One card per route: status, name, rule, protocol, TLS state, service, entry points, middlewares
- Summary strip: route counts per protocol, the provider's middleware count, any route not serving, and a read-only marker
- Middlewares from the Docker provider, listed under the routes, when the provider has at least one route
- Search, protocol filter, refresh

Click a card for its detail panel, which adds the container address and the route's `traefik.*` labels.

Routes are **read-only** - edit them via your container's Docker labels.

## Enabling the tab

This tab switches itself on the first time Traefik reports routers from this provider, and the setup wizard pre-selects it when the provider is already running. Turn it off and it stays off.

| Where | Path |
|---|---|
| Setup wizard | Monitoring step → Provider tabs → Docker |
| Later | Settings → Route Monitoring → Docker |

## Requirements

Traefik must be configured with the Docker provider and have access to the Docker socket:

```yaml
providers:
  docker:
    exposedByDefault: false
```

With `exposedByDefault: false`, only containers labelled `traefik.enable=true` appear.

No mounts into traefik-manager needed - data comes live from the Traefik API.
