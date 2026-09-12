# HTTP Provider Tab

The **HTTP Provider** tab lists the routes Traefik fetches from its HTTP provider.

## What it shows

- One card per route: status, name, rule, protocol, TLS state, service, entry points, middlewares
- Summary strip: route counts per protocol, the provider's middleware count, any route not serving, and a read-only marker
- Middlewares from the HTTP provider, listed under the routes, when the provider has at least one route
- Search, protocol filter, refresh

Click a card for its detail panel.

Routes are **read-only** - edit them at the endpoint Traefik polls.

## Enabling the tab

This tab switches itself on the first time Traefik reports routers from this provider, and the setup wizard pre-selects it when the provider is already running. Turn it off and it stays off.

| Where | Path |
|---|---|
| Setup wizard | Monitoring step → Provider tabs → HTTP Provider |
| Later | Settings → Route Monitoring → HTTP Provider |

## Requirements

Traefik must be configured with the HTTP provider in your `traefik.yml`:

```yaml
providers:
  http:
    endpoint: "https://my-config-server/traefik-config"
    pollInterval: "5s"
```

No mounts into traefik-manager needed - data comes live from the Traefik API.
