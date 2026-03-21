# Consul Catalog Tab

The **Consul Catalog** tab shows all routes discovered by Traefik's Consul Catalog provider in read-only mode.

> **Note:** This tab covers the Consul *service catalog* provider (`consulcatalog`), which discovers services registered in Consul. This is different from the Consul KV provider which stores configuration in Consul's key-value store.

## What it shows

- Route name, rule, status (enabled/disabled/error)
- Protocol (HTTP / TCP / UDP)
- TLS indicator
- Service name
- Entry points
- Full detail view via the info button

Routes are **read-only** - edit them via your Consul service registrations and Traefik tags.

## Enabling the tab

### During setup wizard
Toggle **Consul Catalog** on in the "Optional monitoring" step.

### After setup
Go to **Settings → Optional Tabs** and enable Consul Catalog.

## Requirements

Traefik must be configured with the Consul Catalog provider in your `traefik.yml`:

```yaml
providers:
  consulCatalog:
    endpoint:
      address: "http://localhost:8500"
```

No extra file mounts into the traefik-manager container are needed - data is pulled live from the Traefik API.
