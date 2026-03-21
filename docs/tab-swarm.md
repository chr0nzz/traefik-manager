# Swarm Tab

The **Swarm** tab shows all routes discovered by Traefik's Docker Swarm provider in read-only mode.

## What it shows

- Route name, rule, status (enabled/disabled/error)
- Protocol (HTTP / TCP / UDP)
- TLS indicator
- Service name
- Entry points
- Full detail view via the info button

Routes are **read-only** - edit them via your Docker Swarm service labels.

## Enabling the tab

### During setup wizard
Toggle **Swarm** on in the "Optional monitoring" step.

### After setup
Go to **Settings → Optional Tabs** and enable Swarm.

## Requirements

Traefik must be configured with the Docker Swarm provider in your `traefik.yml`:

```yaml
providers:
  swarm:
    endpoint: "unix:///var/run/docker.sock"
```

No extra file mounts into the traefik-manager container are needed - data is pulled live from the Traefik API.
