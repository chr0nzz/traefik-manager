# ECS Tab

The **ECS** tab shows all routes discovered by Traefik's Amazon ECS provider in read-only mode.

## What it shows

- Route name, rule, status (enabled/disabled/error)
- Protocol (HTTP / TCP / UDP)
- TLS indicator
- Service name
- Entry points
- Full detail view via the info button

Routes are **read-only** - edit them via your ECS task definitions and Traefik labels.

## Enabling the tab

### During setup wizard
Toggle **ECS** on in the "Optional monitoring" step.

### After setup
Go to **Settings → Optional Tabs** and enable ECS.

## Requirements

Traefik must be configured with the ECS provider in your `traefik.yml`:

```yaml
providers:
  ecs:
    region: us-east-1
    clusters:
      - my-cluster
```

No extra file mounts into the traefik-manager container are needed - data is pulled live from the Traefik API.
