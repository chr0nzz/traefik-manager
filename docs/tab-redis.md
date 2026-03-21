# Redis Tab

The **Redis** tab shows all routes stored in Traefik's Redis KV provider in read-only mode.

## What it shows

- Route name, rule, status (enabled/disabled/error)
- Protocol (HTTP / TCP / UDP)
- TLS indicator
- Service name
- Entry points
- Full detail view via the info button

Routes are **read-only** - edit them directly in your Redis KV store.

## Enabling the tab

### During setup wizard
Toggle **Redis** on in the "Optional monitoring" step.

### After setup
Go to **Settings → Optional Tabs** and enable Redis.

## Requirements

Traefik must be configured with the Redis provider in your `traefik.yml`:

```yaml
providers:
  redis:
    endpoints:
      - "redis:6379"
```

No extra file mounts into the traefik-manager container are needed - data is pulled live from the Traefik API.
