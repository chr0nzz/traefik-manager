# Nomad Tab

The **Nomad** tab shows all routes discovered by Traefik's HashiCorp Nomad provider in read-only mode.

## What it shows

- Route name, rule, status (enabled/disabled/error)
- Protocol (HTTP / TCP / UDP)
- TLS indicator
- Service name
- Entry points
- Full detail view via the info button

Routes are **read-only** - edit them via your Nomad job definitions.

## Enabling the tab

### During setup wizard
Toggle **Nomad** on in the "Optional monitoring" step.

### After setup
Go to **Settings → Optional Tabs** and enable Nomad.

## Requirements

Traefik must be configured with the Nomad provider in your `traefik.yml`:

```yaml
providers:
  nomad:
    endpoint:
      address: "http://localhost:4646"
```

No extra file mounts into the traefik-manager container are needed - data is pulled live from the Traefik API.
