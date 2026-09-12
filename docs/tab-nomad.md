# Nomad Tab

The **Nomad** tab lists the routes Traefik discovered through its HashiCorp Nomad provider.

## What it shows

- One card per route: status, name, rule, protocol, TLS state, service, entry points, middlewares
- Summary strip: route counts per protocol, the provider's middleware count, any route not serving, and a read-only marker
- Middlewares from the Nomad provider, listed under the routes, when the provider has at least one route
- Search, protocol filter, refresh

Click a card for its detail panel.

Routes are **read-only** - edit them via your Nomad job definitions.

## Enabling the tab

This tab switches itself on the first time Traefik reports routers from this provider, and the setup wizard pre-selects it when the provider is already running. Turn it off and it stays off.

| Where | Path |
|---|---|
| Setup wizard | Monitoring step → Provider tabs → Nomad |
| Later | Settings → Route Monitoring → Nomad |

## Requirements

Traefik must be configured with the Nomad provider in your `traefik.yml`:

```yaml
providers:
  nomad:
    endpoint:
      address: "http://localhost:4646"
```

No mounts into traefik-manager needed - data comes live from the Traefik API.
