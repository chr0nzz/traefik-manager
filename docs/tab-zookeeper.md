# ZooKeeper Tab

The **ZooKeeper** tab shows all routes stored in Traefik's ZooKeeper KV provider in read-only mode.

## What it shows

- Route name, rule, status (enabled/disabled/error)
- Protocol (HTTP / TCP / UDP)
- TLS indicator
- Service name
- Entry points
- Full detail view via the info button

Routes are **read-only** - edit them directly in your ZooKeeper instance.

## Enabling the tab

### During setup wizard
Toggle **ZooKeeper** on in the "Optional monitoring" step.

### After setup
Go to **Settings → Optional Tabs** and enable ZooKeeper.

## Requirements

Traefik must be configured with the ZooKeeper provider in your `traefik.yml`:

```yaml
providers:
  zooKeeper:
    endpoints:
      - "zookeeper:2181"
```

No extra file mounts into the traefik-manager container are needed - data is pulled live from the Traefik API.
