# HTTP Provider Tab

The **HTTP Provider** tab shows all routes sourced from Traefik's HTTP provider in read-only mode.

## What it shows

- Route name, rule, status (enabled/disabled/error)
- Protocol (HTTP / TCP / UDP)
- TLS indicator
- Service name
- Entry points
- Full detail view via the info button

Routes are **read-only** - edit them at the source HTTP endpoint Traefik is polling.

## Enabling the tab

### During setup wizard
Toggle **HTTP Provider** on in the "Optional monitoring" step.

### After setup
Go to **Settings → Optional Tabs** and enable HTTP Provider.

## Requirements

Traefik must be configured with the HTTP provider in your `traefik.yml`:

```yaml
providers:
  http:
    endpoint: "https://my-config-server/traefik-config"
    pollInterval: "5s"
```

No extra file mounts into the traefik-manager container are needed - data is pulled live from the Traefik API.
