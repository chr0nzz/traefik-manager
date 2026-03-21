# Plugins Tab

The **Plugins** tab shows Traefik plugins declared in the static `traefik.yml` configuration.

## What it shows

- Plugin name (your local alias)
- Module name (the plugin's Go module path)
- Version
- Settings (if any are configured)

Plugins are **read-only** here - they must be declared in `traefik.yml` under `experimental.plugins` and cannot be added or removed from the UI.

## Enabling the tab

### During setup wizard
Toggle **Plugins** on in the "Optional monitoring" step.

### After setup
Go to **Settings → Optional Tabs** and enable Plugins.

## Requirements

Mount your Traefik static config file into the traefik-manager container at `/app/traefik.yml`:

```yaml
volumes:
  - /path/to/traefik/traefik.yml:/app/traefik.yml:ro
```

Plugins must be declared in your `traefik.yml`:

```yaml
experimental:
  plugins:
    my-plugin:
      moduleName: "github.com/example/my-plugin"
      version: "v1.2.3"
```

If `traefik.yml` is not mounted, the Plugins tab will display an error message with the exact volume line to add to your compose file.

> **Note:** The Plugins tab reads `experimental.plugins` from the static config. It shows what is *declared*, not what Traefik has loaded at runtime.
