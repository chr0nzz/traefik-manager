# Plugins Tab

The **Plugins** tab lists the Traefik plugins declared under `experimental.plugins` in your static `traefik.yml`, the middlewares using each one, and whether a newer version is out.

## What it shows

One card per plugin: name (your local alias), version, module path, and a footer reading `used by N middlewares` or `not referenced`. The GitHub link, details, edit and remove actions sit in a hover rail; clicking anywhere else on the card opens the detail panel, which adds the middlewares using the plugin as clickable chips and the plugin's settings block if the declaration has one.

Versions are compared against the [Traefik plugin catalog](https://plugins.traefik.io/), refreshed once a day. A plugin behind the catalog gets an amber flag with the newer version on the card and in the panel, and the summary strip above the grid counts how many plugins are in use, unused and updatable. Updating means changing the version here (or in `traefik.yml`) and restarting Traefik.

It shows what is *declared*, not what Traefik has loaded at runtime.

## Installing a plugin

Click **Add Plugin** and paste the snippets from the plugin's page in the [Traefik plugin catalog](https://plugins.traefik.io/):

1. **Static config snippet** - the `experimental.plugins` block. TM backs up `traefik.yml` and merges the plugin's `moduleName` and `version` into it.
2. **Middleware snippet** *(optional)* - the plugin's example middleware. Replace every `{{ }}` template placeholder with a real value; the save is rejected while any remain, because Traefik would crash on them.
3. **Config file** - which dynamic config file the middleware is written to, an existing one or a new one (default `plugin-middlewares.yml`). The selector appears when a config directory or several config files are in use, and lists the agent's own files when an agent is selected.

Writing the middleware needs a config directory (`CONFIG_DIR`) on the Host, or a selected agent. Without one the plugin is still saved to `traefik.yml` and TM warns that the middleware was not written.

After installing, a banner prompts you to restart Traefik so the plugin is downloaded and loaded. **Restart now** in that banner uses the configured `RESTART_METHOD`.

## Editing and removing

With the static config path set and the file present, the tab gains **Add Plugin**, **Edit** and **Remove**. Edit changes the name, module and version of an existing declaration. Mount the file read-write for those writes to succeed; with a read-only mount the buttons appear but saving fails. Without a path, plugins are read-only and must be managed by hand in `traefik.yml`.

## Enabling the tab

### During setup wizard
Toggle **Plugins** on in the **Monitoring** step, under System.

### After setup
Go to **Settings - System Monitoring - Tab Visibility** and enable Plugins.

## Requirements

Point traefik-manager at your Traefik static config file via the `STATIC_CONFIG_PATH` environment variable (no default - the tab stays inactive until it is set, or until the path is filled in under **Settings - System Monitoring - File Paths**). The compose example below mounts it at `/app/traefik.yml`, so set `STATIC_CONFIG_PATH=/app/traefik.yml` to match.

:::tabs
== Docker / Podman
```yaml
volumes:
  - /path/to/traefik/traefik.yml:/app/traefik.yml:ro
```

== Linux (systemd)
```ini
Environment=STATIC_CONFIG_PATH=/etc/traefik/traefik.yml
```
:::

Plugins live in your `traefik.yml` like this:

```yaml
experimental:
  plugins:
    my-plugin:
      moduleName: "github.com/example/my-plugin"
      version: "v1.2.3"
```

If the file is not found, the tab explains that the static config is not configured and shows the env var and the volume line to add.

## Renaming and removing

Renaming a plugin moves every middleware using it to the new name. Removing one a middleware still uses is refused, and the message names the middlewares.
