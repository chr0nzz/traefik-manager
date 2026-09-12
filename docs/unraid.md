# Running on Unraid

Traefik Manager ships an Unraid template. It is not in Community Applications yet, so install it as a user template.

::: warning Template Repositories is gone
Older guides tell you to paste a repository URL into **Apps - Settings - Template Repositories**. Unraid removed that field in favour of Community Applications, so there is nowhere to paste it. Use the steps below instead.
:::

---

## Install the template

Open a terminal on your Unraid server and run:

```bash
wget -O /boot/config/plugins/dockerMan/templates-user/my-traefik-manager.xml \
  https://raw.githubusercontent.com/chr0nzz/traefik-manager/main/unraid/traefik-manager.xml
```

Then:

1. Open the **Docker** tab and click **Add Container**
2. Pick **traefik-manager** from the **Template** dropdown, under *User templates*
3. Fill in the fields below and click **Apply**

The template survives reboots and array stops because it lives on the flash drive. To update it later, run the same command again.


---

## Configuration

### Required

| Field | Description |
|---|---|
| **Web UI Port** | Port for the UI - default `5000` |
| **Config Directory** | Persistent storage for settings, password and session key. Default: `/mnt/user/appdata/traefik-manager/config` |
| **Config File Path (single file)** | Container-side path to your Traefik dynamic config (`CONFIG_PATH`, default `/app/config/dynamic.yml`). Add a path mapping so the host file lands there |
| **Traefik API URL** | URL of the Traefik API - usually `http://traefik:8080` if on the same Docker network |
| **Domains** | Comma-separated base domains for the Add Route form - e.g. `example.com,home.lab` |

### Optional

| Field | Description |
|---|---|
| **Backups Directory** | Where timestamped config backups are saved. Default: `/mnt/user/appdata/traefik-manager/backups` |
| **Cert Resolver** | Default ACME cert resolver name from your `traefik.yml` |
| **Admin Password** | Set a fixed password. If left empty a temporary password is printed to the container log on first start |
| **Cookie Secure** | Set to `true` if accessing via HTTPS (e.g. behind a Traefik reverse proxy with TLS) |

### Advanced

| Field | Description |
|---|---|
| **Auth Enabled** | Set to `false` to disable built-in login when using an external provider like Authentik |
| **Traefik API Username / Password** | Basic-auth credentials, if the Traefik API sits behind a `basicAuth` middleware |
| **Config Directory Path (multi-file)** | Use instead of the single config file field when managing multiple config files in a directory (`CONFIG_DIR`) |
| **Config Paths (explicit list)** | Comma-separated list of config file paths to manage (`CONFIG_PATHS`). Any number of files. |
| **Settings File Path** | Custom path to `manager.yml` (`SETTINGS_PATH`). Its parent directory becomes the config directory: `agents.yml`, `templates.yml`, `notifications.yml`, `dashboard.yml`, the cache, the GeoIP database, `.otp_key` and `.secret_key` all live beside it, so that directory must be persistent |
| **Inactivity Timeout** | Minutes before a non-remembered session is logged out - default `120` |
| **OTP Encryption Key** | Fernet key for encrypting the 2FA secret at rest. Auto-generated if not set |
| **Secret Key** | Session signing key. Auto-generated if not set. Set this to survive a full config wipe |
| **Trusted Proxy Hops** | How many reverse-proxy hops to trust for `X-Forwarded-For`. Default `1` is right with Traefik alone; use `2` when Cloudflare or another proxy sits in front of Traefik as well, so the audit log records the real client |
| **Skip Traefik API TLS Verification** | Set `true` when the Traefik API URL is https with a self-signed or Origin certificate |
| **acme.json Path** | Only needed when it is not at the default location. Accepts several files comma-separated, or a directory, for setups with one storage file per cert resolver |
| **Access Log Path** | Only needed when the access log is not at the default location |
| **Plugins Directory** | Traefik's local plugins directory, for the Plugins tab |
| **CrowdSec LAPI URL, API Key, Machine ID, Machine Password** | Credentials for the CrowdSec tab |
| **Backup Retention** | Keep only the last N backups per config file. `0` keeps everything |
| **GeoIP Database Path** | Custom MaxMind-format `.mmdb`. Leave empty to use the free DB-IP Lite database, downloaded on demand under the config directory once GeoIP is enabled in Settings |
| **Backup Directory Path** | Container-side backup directory (`BACKUP_DIR`), when it is not the default `/app/backups` |
| **Static Config Path** | Container-side path to `traefik.yml` (`STATIC_CONFIG_PATH`), for the Static Config and Plugins tabs |
| **Restart Method** | How Traefik is restarted after a static config change - see [Static config editor](#static-config-editor) below |
| **Traefik Container Name**, **Docker Host (socket proxy)**, **Signal File Path (poison pill)** | The settings each restart method needs |

Four path mappings are optional and only needed for the tabs that read those files: **Certs Tab - acme.json**, **Static Config / Plugins Tab - traefik.yml** (mount read-write), **Logs Tab - access.log**, and **Docker Socket (direct)** for the Docker restart method.

Every field maps to an environment variable - see [Environment Variables](env-vars.md) for the full reference and defaults.

---

## Multi-config file setup

To manage multiple Traefik dynamic config files, use **Config Directory Path (multi-file)** instead of the single file field:

1. Mount your Traefik config directory into the container, e.g.:
   - Host: `/mnt/user/appdata/traefik/config`
   - Container: `/app/config/traefik`
2. Set **Config Directory Path (multi-file)** to `/app/config/traefik`
3. Leave **Config File Path (single file)** as it is - `CONFIG_DIR` takes precedence over it

Every `.yml` and `.yaml` file in that directory is loaded, subdirectories included. A file picker appears in the Add/Edit Route, Middleware and TLS Option forms.

---

## Optional monitoring mounts

To enable the optional tabs, add path mappings in the Unraid template:

| Tab | Host path | Container path | Mode |
|---|---|---|---|
| Certs | `/mnt/user/appdata/traefik/acme.json` | `/app/acme.json` | Read-only |
| Plugins + Static Config | `/mnt/user/appdata/traefik/traefik.yml` | `/app/traefik.yml` | Read-write |
| Logs | `/mnt/user/appdata/traefik/logs/access.log` | `/app/logs/access.log` | Read-only |

For `traefik.yml` also set **Static Config Path** (`STATIC_CONFIG_PATH`) to `/app/traefik.yml` - unlike acme.json and access.log, that path has no built-in default. A read-only mount still lists plugins, but saving the static config or installing a plugin fails with a write error.

Then switch Certs, Plugins and Logs on in **Settings → System Monitoring**. The Static Config editor is placed separately, in **Settings → Interface → Tabs**.

---

## Static config editor

Edit `traefik.yml` from the UI: entrypoints, certificate resolvers, providers, plugins, API and dashboard, logging, observability and system options. After saving, click **Restart Traefik** to apply the change with your configured restart method.

### Requirements

1. Mount `traefik.yml` **read-write** (not read-only) in the template
2. Set the restart method below
3. Set **Settings → Interface → Tabs → Static Config** to `Settings` (inside the settings window) or `Tab` (its own side-nav entry)

### Method 1: Socket proxy (recommended)

Run a Docker socket proxy container (e.g. `ghcr.io/tecnativa/docker-socket-proxy`) and point Traefik Manager at it:

| Variable | Value |
|---|---|
| `RESTART_METHOD` | `proxy` |
| `DOCKER_HOST` | `tcp://socket-proxy:2375` |
| `TRAEFIK_CONTAINER` | `traefik` |

Both containers must be on the same Docker network. In the socket proxy container, set `CONTAINERS=1` and `POST=1`.

### Method 2: Poison pill

Traefik Manager writes a signal file. A watcher sidecar container sees it and restarts Traefik. No socket access for Traefik Manager itself.

| Variable | Value |
|---|---|
| `RESTART_METHOD` | `poison-pill` |
| `SIGNAL_FILE_PATH` | `/signals/restart.sig` |

Create a shared Docker volume named `traefik-signals` and mount it at `/signals` in both Traefik Manager and the watcher container.

### Method 3: Direct socket

Mount the Docker socket into Traefik Manager:

| Variable | Value |
|---|---|
| `RESTART_METHOD` | `socket` |
| `TRAEFIK_CONTAINER` | `traefik` |

Add an extra path mapping: host `/var/run/docker.sock` → container `/var/run/docker.sock` (read-only).

---

## First start

1. Open the Unraid dashboard and click the Traefik Manager container icon to open the WebUI
2. Check the container log for the temporary password if you did not set **Admin Password**
3. Complete the setup wizard - it configures your domains, Traefik API connection and password

::: tip Set COOKIE_SECURE if using HTTPS
To serve Traefik Manager under a path rather than its own hostname, set [`BASE_PATH`](env-vars.md#base-path).

If you reach Traefik Manager through a Traefik reverse proxy with TLS, set **Cookie Secure** to `true`. This marks the session cookie `Secure` so it is never sent over plain HTTP, and enables the HSTS response header. Sessions still work without it, but the cookie is not protected.
:::

---

## Networking

Traefik Manager needs to reach the Traefik API. The simplest way on Unraid is to put both containers on the same custom Docker network:

1. Go to **Settings → Docker → Add Network** and create a network (e.g. `traefik-net`)
2. Set the **Network** field to `traefik-net` in both the Traefik and Traefik Manager templates
3. Use `http://traefik:8080` as the **Traefik API URL**

---

## Updating

Click **Check for Updates** in the Unraid Docker tab. That updates the image, not the template: to pick up new fields added to the template, re-run the `wget` above and the Docker tab will offer them on the next edit. Traefik Manager follows semantic versioning - patch releases are safe to apply immediately. Check the [release notes](https://github.com/chr0nzz/traefik-manager/releases) before applying minor or major updates.
