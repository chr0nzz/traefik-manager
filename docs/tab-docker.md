# Docker Tab

The **Docker** tab shows all routes discovered by Traefik's Docker provider in read-only mode.

## What it shows

- Route name, rule, status (enabled/disabled/error)
- Protocol (HTTP / TCP / UDP)
- TLS indicator
- Service name
- Entry points
- Full detail view via the info button

Routes are **read-only** - edit them via your container's Docker labels.

## Enabling the tab

### During setup wizard
Toggle **Docker** on in the "Optional monitoring" step.

### After setup
Go to **Settings → Optional Tabs** and enable Docker.

## Requirements

Traefik must be configured with the Docker provider. No extra file mounts into the traefik-manager container are needed - data is pulled live from the Traefik API.

Traefik itself needs access to the Docker socket:

```yaml
providers:
  docker:
    exposedByDefault: false
```

Routes appear for any container with `traefik.enable=true` labels set.
