# Environment Variables

All supported environment variables for Traefik Manager.

::: info Override variables vs env-only
Variables marked ✅ **override** the corresponding `manager.yml` field on every restart - the env var always wins. Variables marked **-** are **env-only** and never written to `manager.yml`. To manage a setting through the UI instead, remove the env var and the value saved in `manager.yml` will be used.
:::

---

## Quick Reference

### Connection & Traefik

| Variable | Default | Override | Description |
|---|---|---|---|
| `TRAEFIK_API_URL` | `http://traefik:8080` | ✅ `traefik_api_url` | Traefik API URL |

### Authentication

| Variable | Default | Override | Description |
|---|---|---|---|
| `COOKIE_SECURE` | `false` | - | Mark session cookie as `Secure` - required for HTTPS |
| `AUTH_ENABLED` | `true` | ✅ `auth_enabled` | Set to `false` to disable built-in login entirely |
| `ADMIN_PASSWORD` | _(unset)_ | ✅ `password_hash` | Admin password in plain text (hashed at runtime) |

### Routes & Domains

| Variable | Default | Override | Description |
|---|---|---|---|
| `DOMAINS` | `example.com` | ✅ `domains` | Comma-separated base domains for the Add Route form |
| `CERT_RESOLVER` | `cloudflare` | ✅ `cert_resolver` | Default ACME resolver name. Use `none` for external certs |

### Config Files

| Variable | Default | Override | Description |
|---|---|---|---|
| `CONFIG_DIR` | _(unset)_ | - | Directory - all `.yml` files loaded automatically |
| `CONFIG_PATHS` | _(unset)_ | - | Comma-separated list of config file paths |
| `CONFIG_PATH` | `/app/config/dynamic.yml` | - | Single config file (default) |
| `BACKUP_DIR` | `/app/backups` | - | Directory for timestamped config backups |
| `SETTINGS_PATH` | `/app/config/manager.yml` | - | Path to the TM settings file |

### Static Config & Restart

| Variable | Default | Override | Description |
|---|---|---|---|
| `STATIC_CONFIG_PATH` | `/app/traefik.yml` | - | Traefik static config - required for Plugins tab and Static Config editor |
| `RESTART_METHOD` | _(unset)_ | - | `proxy`, `socket`, or `poison-pill` |
| `TRAEFIK_CONTAINER` | `traefik` | - | Container name for `proxy` and `socket` restart methods |
| `DOCKER_HOST` | _(unset)_ | - | Docker socket URL - set to `tcp://socket-proxy:2375` for proxy method |
| `SIGNAL_FILE_PATH` | `/signals/restart.sig` | - | Signal file path for `poison-pill` method |

### Monitoring

| Variable | Default | Override | Description |
|---|---|---|---|
| `ACME_JSON_PATH` | `/app/acme.json` | - | Path to `acme.json` for the Certificates tab |
| `ACCESS_LOG_PATH` | `/app/logs/access.log` | - | Path to access log for the Logs tab |

### Security

| Variable | Default | Override | Description |
|---|---|---|---|
| `SECRET_KEY` | _(auto-generated)_ | - | Flask session signing key |
| `OTP_ENCRYPTION_KEY` | _(auto-generated)_ | - | Fernet key for encrypting TOTP secrets |

---

## Connection & Traefik

### `TRAEFIK_API_URL`

**Default:** `http://traefik:8080`
**Overrides:** `traefik_api_url` in `manager.yml`

The URL of the Traefik API. Must be reachable from the host running Traefik Manager.

:::tabs
== Docker / Podman
```yaml
environment:
  - TRAEFIK_API_URL=http://traefik:8080
```
== Linux (systemd)
```ini
Environment=TRAEFIK_API_URL=http://localhost:8080
```
:::

---

## Authentication

### `COOKIE_SECURE`

**Default:** `false`
**env-only** - not stored in `manager.yml`.

Set to `true` when Traefik Manager is served over HTTPS.

:::tabs
== Docker / Podman
```yaml
environment:
  - COOKIE_SECURE=true
```
== Linux (systemd)
```ini
Environment=COOKIE_SECURE=true
```
:::

::: warning
If you are behind a reverse proxy with HTTPS and do not set this, logins will fail silently.
:::

---

### `AUTH_ENABLED`

**Default:** `true`
**Overrides:** `auth_enabled` in `manager.yml`

Set to `false` to disable the built-in login entirely. Use when TM is protected by an external auth provider (Authentik, Authelia, Traefik `basicAuth`, etc.).

:::tabs
== Docker / Podman
```yaml
environment:
  - AUTH_ENABLED=false
```
== Linux (systemd)
```ini
Environment=AUTH_ENABLED=false
```
:::

::: danger
When disabled, the UI is fully open. Only use this behind another authentication layer.
:::

---

### `ADMIN_PASSWORD`

**Default:** _(unset)_
**Overrides:** `password_hash` in `manager.yml`

Set the admin password in plain text. Hashed with bcrypt at runtime. Useful for scripted deployments.

:::tabs
== Docker / Podman
```yaml
environment:
  - ADMIN_PASSWORD=mysecretpassword
```
== Linux (systemd)
```ini
Environment=ADMIN_PASSWORD=mysecretpassword
```
:::

::: info
When set, the in-UI password change and `flask reset-password` have no effect. Remove the variable to switch back to `manager.yml`-managed passwords.
:::

---

## Routes & Domains

### `DOMAINS`

**Default:** `example.com`
**Overrides:** `domains` in `manager.yml`

Comma-separated list of base domains shown in the Add Route form.

:::tabs
== Docker / Podman
```yaml
environment:
  - DOMAINS=example.com,home.lab
```
== Linux (systemd)
```ini
Environment=DOMAINS=example.com,home.lab
```
:::

---

### `CERT_RESOLVER`

**Default:** `cloudflare`
**Overrides:** `cert_resolver` in `manager.yml`

One or more ACME cert resolver names, comma-separated. The first is the default for new routes. Each route can override this individually in the Add/Edit Route form.

Set to `none` if you manage certificates externally (cert files, internal CA, `tls.yml`). Routes will use `tls: {}` with no `certResolver`.

:::tabs
== Docker / Podman
```yaml
environment:
  - CERT_RESOLVER=letsencrypt

  - CERT_RESOLVER=letsencrypt, cloudflare

  - CERT_RESOLVER=none
```
== Linux (systemd)
```ini
Environment=CERT_RESOLVER=letsencrypt, cloudflare
```
:::

---

## Config Files

### `CONFIG_DIR`, `CONFIG_PATHS`, `CONFIG_PATH`

**env-only** - not stored in `manager.yml`.

Traefik Manager can manage one or many dynamic config files. Three variables control this in priority order:

```
CONFIG_DIR  >  CONFIG_PATHS  >  CONFIG_PATH
```

Only one should be set. When multiple config files are loaded, a **Config File** dropdown appears in the Add/Edit Route and Middleware modals. `CONFIG_DIR` also includes a **+ New file...** option to create files on the fly.

---

### `CONFIG_DIR`

**Default:** _(unset)_

Point to a directory and every `.yml` file inside it is loaded automatically.

:::tabs
== Docker / Podman
```yaml
environment:
  - CONFIG_DIR=/app/config/traefik
volumes:
  - /host/traefik/config:/app/config/traefik
```
:::

---

### `CONFIG_PATHS`

**Default:** _(unset)_

Comma-separated list of full config file paths. Good for 2-5 named files.

:::tabs
== Docker / Podman
```yaml
environment:
  - CONFIG_PATHS=/app/config/routes.yml,/app/config/services.yml
volumes:
  - /host/routes.yml:/app/config/routes.yml
  - /host/services.yml:/app/config/services.yml
```
:::

---

### `CONFIG_PATH`

**Default:** `/app/config/dynamic.yml`

Single config file. Default for most setups.

:::tabs
== Docker / Podman
```yaml
environment:
  - CONFIG_PATH=/data/traefik/dynamic.yml
volumes:
  - /path/to/traefik/dynamic.yml:/data/traefik/dynamic.yml
```
== Linux (systemd)
```ini
Environment=CONFIG_PATH=/etc/traefik/dynamic.yml
```
:::

---

### `BACKUP_DIR`

**Default:** `/app/backups`

Directory where timestamped backups are stored before every config save.

:::tabs
== Docker / Podman
```yaml
environment:
  - BACKUP_DIR=/data/backups
volumes:
  - /path/to/backups:/data/backups
```
== Linux (systemd)
```ini
Environment=BACKUP_DIR=/var/lib/traefik-manager/backups
```
:::

---

### `SETTINGS_PATH`

**Default:** `/app/config/manager.yml`

Path to the Traefik Manager settings file.

:::tabs
== Docker / Podman
```yaml
environment:
  - SETTINGS_PATH=/data/manager.yml
volumes:
  - /path/to/manager.yml:/data/manager.yml
```
== Linux (systemd)
```ini
Environment=SETTINGS_PATH=/var/lib/traefik-manager/manager.yml
```
:::

---

## Static Config & Restart

### `STATIC_CONFIG_PATH`

**Default:** `/app/traefik.yml`

Path to Traefik's static config (`traefik.yml` or `traefik.toml`). Required for the **Plugins** tab and **Static Config** editor. Mount **read-write** (no `:ro`) to allow editing. Can also be set via **Settings → System Monitoring → File Paths** without a restart.

:::tabs
== Docker / Podman
```yaml
environment:
  - STATIC_CONFIG_PATH=/app/traefik.yml
volumes:
  - /path/to/traefik.yml:/app/traefik.yml
```
== Linux (systemd)
```ini
Environment=STATIC_CONFIG_PATH=/etc/traefik/traefik.yml
```
:::

---

### `RESTART_METHOD`

**Default:** _(unset)_

How TM restarts Traefik after static config changes. Required for the Restart button in the Static Config editor.

| Value | Description |
|---|---|
| `proxy` | Via a Docker socket proxy sidecar (recommended) |
| `socket` | Via a directly mounted Docker socket |
| `poison-pill` | Writes a signal file; Traefik's healthcheck detects it and restarts |

:::tabs
== Docker / Podman
```yaml
environment:
  - RESTART_METHOD=proxy
```
== Linux (systemd)
```ini
Environment=RESTART_METHOD=poison-pill
```
:::

See [Static Config](static.md#restart-methods) for full compose snippets for each method.

---

### `TRAEFIK_CONTAINER`

**Default:** `traefik`

The name of the Traefik container to restart. Used by the `proxy` and `socket` restart methods.

:::tabs
== Docker / Podman
```yaml
environment:
  - TRAEFIK_CONTAINER=traefik
```
:::

---

### `DOCKER_HOST`

**Default:** _(unset - uses `/var/run/docker.sock`)_

Docker socket URL. Set to `tcp://socket-proxy:2375` when using the `proxy` restart method.

:::tabs
== Docker / Podman
```yaml
environment:
  - DOCKER_HOST=tcp://socket-proxy:2375
```
:::

---

### `SIGNAL_FILE_PATH`

**Default:** `/signals/restart.sig`

Signal file path for the `poison-pill` restart method. Must be on a shared volume between TM and Traefik.

:::tabs
== Docker / Podman
```yaml
environment:
  - SIGNAL_FILE_PATH=/signals/restart.sig
```
== Linux (systemd)
```ini
Environment=SIGNAL_FILE_PATH=/var/lib/traefik-manager/signals/restart.sig
```
:::

---

## Monitoring

### `ACME_JSON_PATH`

**Default:** `/app/acme.json`

Path to Traefik's `acme.json`. Required for the **Certificates** tab. Can also be set via **Settings → System Monitoring → File Paths** without a restart.

:::tabs
== Docker / Podman
```yaml
environment:
  - ACME_JSON_PATH=/letsencrypt/acme.json
volumes:
  - /path/to/acme.json:/letsencrypt/acme.json:ro
```
== Linux (systemd)
```ini
Environment=ACME_JSON_PATH=/etc/traefik/acme.json
```
:::

---

### `ACCESS_LOG_PATH`

**Default:** `/app/logs/access.log`

Path to Traefik's access log. Required for the **Logs** tab. Enable access logging in your Traefik static config first:

```yaml
accessLog:
  filePath: /var/log/traefik/access.log
```

:::tabs
== Docker / Podman
```yaml
environment:
  - ACCESS_LOG_PATH=/logs/access.log
volumes:
  - /path/to/access.log:/logs/access.log:ro
```
== Linux (systemd)
```ini
Environment=ACCESS_LOG_PATH=/var/log/traefik/access.log
```
:::

---

## Security

### `SECRET_KEY`

**Default:** _(auto-generated and persisted as `.secret_key` alongside `SETTINGS_PATH`)_

Flask session signing key. Set this to keep sessions alive across container restarts without re-login.

:::tabs
== Docker / Podman
```yaml
environment:
  - SECRET_KEY=your-random-32-byte-hex-string
```
== Linux (systemd)
```ini
Environment=SECRET_KEY=your-random-32-byte-hex-string
```
:::

::: tip Generating a key
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```
:::

---

### `OTP_ENCRYPTION_KEY`

**Default:** _(auto-generated and stored as `.otp_key` alongside `SETTINGS_PATH`)_

Fernet key for encrypting TOTP secrets at rest in `manager.yml`.

:::tabs
== Docker / Podman
```yaml
environment:
  - OTP_ENCRYPTION_KEY=your-32-byte-url-safe-base64-key
```
== Linux (systemd)
```ini
Environment=OTP_ENCRYPTION_KEY=your-32-byte-url-safe-base64-key
```
:::

::: tip Generating a key
```bash
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```
:::

::: warning
If you lose this key, existing TOTP secrets become unreadable and 2FA must be re-enrolled. Back up `.otp_key` alongside your config volume.
:::
