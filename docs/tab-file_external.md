# File (external) Tab

The **File (external)** tab shows routes from Traefik's file provider that are **not** managed by traefik-manager. Routes that traefik-manager manages (stored in `dynamic.yml`) are shown in the main Routes tab instead.

## What it shows

- Route name, rule, status (enabled/disabled/error)
- Protocol (HTTP / TCP / UDP)
- TLS indicator
- Service name
- Entry points
- Full detail view via the info button

Routes are **read-only** - edit them directly in the relevant file provider configuration.

## Enabling the tab

### During setup wizard
Toggle **File (external)** on in the "Optional monitoring" step.

### After setup
Go to **Settings → Optional Tabs** and enable File (external).

## Requirements

Traefik must be configured with the file provider pointing to one or more external configuration files in your `traefik.yml`:

```yaml
providers:
  file:
    directory: "/etc/traefik/conf.d"
    watch: true
```

or:

```yaml
providers:
  file:
    filename: "/etc/traefik/extra-routes.yml"
```

No extra file mounts into the traefik-manager container are needed - data is pulled live from the Traefik API.

> **Note:** traefik-manager's own `dynamic.yml` also uses the file provider. Routes from that file are shown in the main Routes tab and are automatically excluded from this tab to avoid duplication.
