# etcd Tab

The **etcd** tab shows all routes stored in Traefik's etcd KV provider in read-only mode.

## What it shows

- Route name, rule, status (enabled/disabled/error)
- Protocol (HTTP / TCP / UDP)
- TLS indicator
- Service name
- Entry points
- Full detail view via the info button

Routes are **read-only** - edit them directly in your etcd instance.

## Enabling the tab

### During setup wizard
Toggle **etcd** on in the "Optional monitoring" step.

### After setup
Go to **Settings → Optional Tabs** and enable etcd.

## Requirements

Traefik must be configured with the etcd provider in your `traefik.yml`:

```yaml
providers:
  etcd:
    endpoints:
      - "etcd:2379"
```

No extra file mounts into the traefik-manager container are needed - data is pulled live from the Traefik API.
