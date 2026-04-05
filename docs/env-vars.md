# Environment Variables

All supported environment variables for Traefik Manager. Variables marked **Override** take priority over the corresponding [`manager.yml`](manager-yml.md) field.

---

## Quick reference

| Variable | Default | Override | Description |
|----------|---------|----------|-------------|
| `COOKIE_SECURE` | `false` | - | Mark session cookie as `Secure` (required for HTTPS) |
| `AUTH_ENABLED` | `true` | ✅ `auth_enabled` | Disable built-in login entirely |
| `ADMIN_PASSWORD` | _(unset)_ | ✅ `password_hash` | Admin password in plain text (hashed at runtime) |
| `DOMAINS` | `example.com` | ✅ `domains` | Comma-separated base domains |
| `CERT_RESOLVER` | `cloudflare` | ✅ `cert_resolver` | Default ACME resolver name |
| `TRAEFIK_API_URL` | `http://traefik:8080` | ✅ `traefik_api_url` | Traefik API URL |
| `CONFIG_DIR` | _(unset)_ | - | Directory - load all `.yml` files in it as config files |
| `CONFIG_PATHS` | _(unset)_ | - | Comma-separated list of config file paths |
| `CONFIG_PATH` | `/app/config/dynamic.yml` | - | Single config file (legacy, backwards-compatible) |
| `BACKUP_DIR` | `/app/backups` | - | Directory for timestamped config backups |
| `SETTINGS_PATH` | `/app/config/manager.yml` | - | Path to the Traefik Manager settings file |
| `ACME_JSON_PATH` | `/app/acme.json` | - | Path to Traefik's `acme.json` file for the Certificates tab |
| `STATIC_CONFIG_PATH` | `/app/traefik.yml` | - | Path to Traefik's static config file for the Plugins tab |
| `ACCESS_LOG_PATH` | `/app/logs/access.log` | - | Path to Traefik's access log file for the Logs tab |
| `OTP_ENCRYPTION_KEY` | _(auto-generated)_ | - | Fernet key for encrypting the TOTP secret at rest |

---

## Reference

### `COOKIE_SECURE`

**Default:** `false`

Set to `true` when Traefik Manager is served over HTTPS. Marks the session cookie as `Secure`, which is required by browsers for cookies on HTTPS origins.

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
If you are behind a reverse proxy with HTTPS and do not set this, logins will fail silently - the session cookie will not be sent by the browser.
:::

---

### `AUTH_ENABLED`

**Default:** `true`
**Overrides:** `auth_enabled` in `manager.yml`

Set to `false` to disable the built-in login entirely. Use this when Traefik Manager is protected by an external auth provider (Authentik, Authelia, Traefik `basicAuth`, etc.).

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

Set the admin password in plain text. It is hashed with bcrypt at runtime. Useful for scripted deployments where you do not want to pre-generate a hash.

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
When this variable is set, the CLI `flask reset-password` command and the in-UI password change have no effect - the password always comes from this variable. Remove the variable to switch back to `manager.yml`-managed passwords.
:::

---

### `DOMAINS`

**Default:** `example.com`
**Overrides:** `domains` in `manager.yml`

Comma-separated list of base domains shown in the **Add Route** form.

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

One or more ACME cert resolver names, comma-separated. The first resolver is used as the default for new routes. Each route can override this individually in the Add/Edit Route form.

:::tabs
== Docker / Podman
```yaml
environment:
  - CERT_RESOLVER=letsencrypt

  - CERT_RESOLVER=letsencrypt, cloudflare
```

== Linux (systemd)
```ini
Environment=CERT_RESOLVER=letsencrypt, cloudflare
```
:::

---

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

### Multi-config: `CONFIG_DIR`, `CONFIG_PATHS`, `CONFIG_PATH`

Traefik Manager can manage one or many dynamic config files. Three variables control this in priority order:

```
CONFIG_DIR  >  CONFIG_PATHS  >  CONFIG_PATH
```

Only one should be set. When multiple config files are loaded, a **Config File** dropdown appears in the Add/Edit Route and Middleware modals, and each route card shows a small file badge. When `CONFIG_DIR` is set, the dropdown also includes a **+ New file...** option - type a filename and the app creates the file automatically in `CONFIG_DIR`.

---

#### `CONFIG_DIR`

**Default:** _(unset)_

Point to a directory and every `.yml` file inside it is loaded as a config file. Best for setups with many files where you don't want to list them all explicitly.

:::tabs
== Docker / Podman
```yaml
environment:
  - CONFIG_DIR=/app/config/traefik
volumes:
  - /host/traefik/config:/app/config/traefik
  # every *.yml in that directory is picked up automatically
```
:::

---

#### `CONFIG_PATHS`

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

#### `CONFIG_PATH`

**Default:** `/app/config/dynamic.yml`

Single config file. Existing behaviour - no changes needed for single-file setups.

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

Directory where timestamped backups of `dynamic.yml` are stored before every save.

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

Path to the Traefik Manager settings file. Useful if you want to separate it from the dynamic config directory.

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

### `ACME_JSON_PATH`

**Default:** `/app/acme.json`

Path to Traefik's `acme.json` file. Required for the **Certificates** tab to show TLS certificate status and expiry dates. On native Linux installs Traefik typically writes this to a path outside `/app` - set this variable to match your actual path.

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

::: info
If you use certificate files (e.g. `chain.pem` / `key.pem`) via a `tls.yml` instead of `acme.json`, the Certificates tab is not applicable - Traefik Manager can only read ACME-managed certificates from `acme.json`.
:::

---

### `STATIC_CONFIG_PATH`

**Default:** `/app/traefik.yml`

Path to Traefik's static configuration file (`traefik.yml` or `traefik.toml`). Required for the **Plugins** tab to list installed experimental plugins.

:::tabs
== Docker / Podman
```yaml
environment:
  - STATIC_CONFIG_PATH=/etc/traefik/traefik.yml
volumes:
  - /path/to/traefik.yml:/etc/traefik/traefik.yml:ro
```

== Linux (systemd)
```ini
Environment=STATIC_CONFIG_PATH=/etc/traefik/traefik.yml
```
:::

---

### `ACCESS_LOG_PATH`

**Default:** `/app/logs/access.log`

Path to Traefik's access log file. Required for the **Logs** tab. Enable access logging in your Traefik static config first:

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

### `OTP_ENCRYPTION_KEY`

**Default:** _(auto-generated and stored at `/app/config/.otp_key`)_

Fernet symmetric key used to encrypt the TOTP secret at rest in `manager.yml`. If not set, a key is automatically generated on first start and written to `.otp_key` inside the config directory.

Set this variable if you want to manage the key yourself (e.g., from a secrets manager) or to ensure the key survives config volume replacement.

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

::: info
If you lose this key, existing TOTP secrets become unreadable and 2FA will need to be re-enrolled. The `.otp_key` file is separate from `manager.yml` - back it up alongside your config volume.
:::
