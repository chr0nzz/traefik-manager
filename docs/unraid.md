# Running on Unraid

Traefik Manager can be installed on Unraid using a custom template hosted at [unraid.xyzlab.dev/tm](https://unraid.xyzlab.dev/tm).

---

## Install via Community Applications

1. Open the **Apps** tab in your Unraid dashboard
2. Click the **Settings** icon (top right) and go to **Template Repositories**
3. Add the following URL to your repository list:
   ```
   https://unraid.xyzlab.dev/tm
   ```
4. Click **Save** and then **Done**
5. Search for **Traefik Manager** in the Apps tab
6. Click **Install**


---

## Configuration

### Required

| Field | Description |
|---|---|
| **Web UI Port** | Port to access the UI - default `5000` |
| **Config Directory** | Persistent storage for settings, password, and session key. Default: `/mnt/user/appdata/traefik-manager/config` |
| **Dynamic Config File** | Path to your Traefik dynamic config file on the Unraid host. Map this to `/app/config/dynamic.yml` inside the container |
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
| **Config Directory Path** | Use instead of the single config file field when managing multiple `.yml` files in a directory (`CONFIG_DIR`) |
| **Config Paths** | Comma-separated list of config file paths for 2-5 named files (`CONFIG_PATHS`) |
| **Settings File Path** | Custom path to `manager.yml` if you want it separate from the config directory |
| **Inactivity Timeout** | Minutes before a non-remembered session is logged out - default `120` |
| **OTP Encryption Key** | Fernet key for encrypting the 2FA secret at rest. Auto-generated if not set |
| **Secret Key** | Session signing key. Auto-generated if not set. Set this to survive a full config wipe |

---

## Multi-config file setup

If you manage multiple Traefik dynamic config files, use **Config Directory Path** instead of the single file field:

1. Mount your Traefik config directory to a path inside the container, e.g.:
   - Host: `/mnt/user/appdata/traefik/config`
   - Container: `/app/config/traefik`
2. Set **Config Directory Path** to `/app/config/traefik`
3. Leave the **Dynamic Config File** field empty

All `.yml` files in that directory will be loaded. A file picker appears in the Add/Edit Route and Middleware modals.

---

## Optional monitoring mounts

To enable optional tabs, add path mappings in the Unraid template:

| Tab | Host path | Container path | Mode |
|---|---|---|---|
| Certs | `/mnt/user/appdata/traefik/acme.json` | `/app/acme.json` | Read-only |
| Plugins | `/mnt/user/appdata/traefik/traefik.yml` | `/app/traefik.yml` | Read-only |
| Plugins + Static Config | `/mnt/user/appdata/traefik/traefik.yml` | `/app/traefik.yml` | Read-write |
| Logs | `/mnt/user/appdata/traefik/logs/access.log` | `/app/logs/access.log` | Read-only |

Mount `traefik.yml` read-write if you want to use the Static Config editor. Read-only enables only the Plugins tab. Then enable each tab in **Settings → System Monitoring**.

---

## Static config editor

The Static Config tab lets you edit `traefik.yml` directly from the UI - entrypoints, certificate resolvers, plugins, providers, API settings, and log level. After saving, Traefik Manager restarts Traefik automatically.

### Requirements

1. Mount `traefik.yml` with **read/write** access (not read-only) in the template
2. Set the restart method via environment variables

### Method 1: Socket proxy (recommended)

Run a Docker socket proxy container (e.g. `ghcr.io/tecnativa/docker-socket-proxy`) and point Traefik Manager at it:

| Variable | Value |
|---|---|
| `RESTART_METHOD` | `proxy` |
| `DOCKER_HOST` | `tcp://socket-proxy:2375` |
| `TRAEFIK_CONTAINER` | `traefik` |

Both containers must be on the same Docker network. In the socket proxy container, set `CONTAINERS=1` and `POST=1`.

### Method 2: Poison pill

Traefik Manager writes a signal file. A watcher sidecar container monitors it and restarts Traefik. No socket access needed for Traefik Manager itself.

| Variable | Value |
|---|---|
| `RESTART_METHOD` | `poison-pill` |
| `SIGNAL_FILE_PATH` | `/signals/restart.sig` |

Create a shared Docker volume named `traefik-signals` and mount it to `/signals` in both Traefik Manager and the watcher container.

### Method 3: Direct socket

Mount the Docker socket directly into Traefik Manager:

| Variable | Value |
|---|---|
| `RESTART_METHOD` | `socket` |
| `TRAEFIK_CONTAINER` | `traefik` |

Add an extra path mapping: host `/var/run/docker.sock` → container `/var/run/docker.sock` (read-only).

---

## First start

1. Open the Unraid dashboard and click the Traefik Manager container icon to open the WebUI
2. Check the container log for the temporary password if you did not set **Admin Password**
3. Complete the setup wizard - it configures your domains, Traefik API connection, and initial password

::: tip Set COOKIE_SECURE if using HTTPS
If you access Traefik Manager through a Traefik reverse proxy with TLS, set **Cookie Secure** to `true`. Without it, session cookies will not work correctly over HTTPS.
:::

---

## Networking

Traefik Manager needs to reach the Traefik API. The simplest way on Unraid is to add both containers to the same custom Docker network:

1. In Unraid go to **Settings → Docker → Add Network** and create a network (e.g. `traefik-net`)
2. Set the **Network** field to `traefik-net` in both the Traefik and Traefik Manager templates
3. Use `http://traefik:8080` as the **Traefik API URL**

---

## Updating

Click **Check for Updates** in the Unraid Docker tab. Traefik Manager follows semantic versioning - patch releases are safe to apply immediately. Check the [release notes](https://github.com/chr0nzz/traefik-manager/releases) before applying minor or major updates.
