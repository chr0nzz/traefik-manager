# Consul KV Tab

The **Consul KV** tab shows all routes stored in Traefik's Consul KV provider in read-only mode.

> **Note:** This tab covers the Consul *KV store* provider (`consul`), which reads Traefik configuration from Consul's key-value store. This is different from the Consul Catalog provider which discovers services registered in Consul's service catalog.

## What it shows

- Route name, rule, status (enabled/disabled/error)
- Protocol (HTTP / TCP / UDP)
- TLS indicator
- Service name
- Entry points
- Full detail view via the info button

Routes are **read-only** - edit them directly in the Consul KV store.

## Enabling the tab

### During setup wizard
Toggle **Consul KV** on in the "Optional monitoring" step.

### After setup
Go to **Settings → Optional Tabs** and enable Consul KV.

## Requirements

Traefik must be configured with the Consul KV provider in your `traefik.yml`:

```yaml
providers:
  consul:
    endpoints:
      - "consul:8500"
```

No extra file mounts into the traefik-manager container are needed - data is pulled live from the Traefik API.
