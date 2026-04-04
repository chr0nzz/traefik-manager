# Running on Unraid

Traefik Manager is available as a Community Applications template for Unraid.

---

## Install via Community Applications

1. Open the **Apps** tab in your Unraid dashboard
2. Search for **Traefik Manager**
3. Click **Install**

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
