# Environment Variables

All supported environment variables for Traefik Manager. Variables marked **Override** take priority over the corresponding [`manager.yml`](manager-yml.md) field.

---

## Quick reference

| Variable | Default | Override | Description |
|----------|---------|----------|-------------|
| `COOKIE_SECURE` | `false` | — | Mark session cookie as `Secure` (required for HTTPS) |
| `AUTH_ENABLED` | `true` | ✅ `auth_enabled` | Disable built-in login entirely |
| `ADMIN_PASSWORD` | _(unset)_ | ✅ `password_hash` | Admin password in plain text (hashed at runtime) |
| `DOMAINS` | `example.com` | ✅ `domains` | Comma-separated base domains |
| `CERT_RESOLVER` | `cloudflare` | ✅ `cert_resolver` | Default ACME resolver name |
| `TRAEFIK_API_URL` | `http://traefik:8080` | ✅ `traefik_api_url` | Traefik API URL |
| `CONFIG_PATH` | `/app/config/dynamic.yml` | — | Path to the Traefik dynamic config |
| `BACKUP_DIR` | `/app/backups` | — | Directory for timestamped config backups |
| `SETTINGS_PATH` | `/app/config/manager.yml` | — | Path to the Traefik Manager settings file |
| `OTP_ENCRYPTION_KEY` | _(auto-generated)_ | — | Fernet key for encrypting the TOTP secret at rest |

---

## Reference

### `COOKIE_SECURE`

**Default:** `false`

Set to `true` when Traefik Manager is served over HTTPS. Marks the session cookie as `Secure`, which is required by browsers for cookies on HTTPS origins.

=== "Docker / Podman"
    ```yaml
    environment:
      - COOKIE_SECURE=true
    ```

=== "Linux (systemd)"
    ```ini
    Environment=COOKIE_SECURE=true
    ```

!!! warning
    If you are behind a reverse proxy with HTTPS and do not set this, logins will fail silently — the session cookie will not be sent by the browser.

---

### `AUTH_ENABLED`

**Default:** `true`
**Overrides:** `auth_enabled` in `manager.yml`

Set to `false` to disable the built-in login entirely. Use this when Traefik Manager is protected by an external auth provider (Authentik, Authelia, Traefik `basicAuth`, etc.).

=== "Docker / Podman"
    ```yaml
    environment:
      - AUTH_ENABLED=false
    ```

=== "Linux (systemd)"
    ```ini
    Environment=AUTH_ENABLED=false
    ```

!!! danger
    When disabled, the UI is fully open. Only use this behind another authentication layer.

---

### `ADMIN_PASSWORD`

**Default:** _(unset)_
**Overrides:** `password_hash` in `manager.yml`

Set the admin password in plain text. It is hashed with bcrypt at runtime. Useful for scripted deployments where you do not want to pre-generate a hash.

=== "Docker / Podman"
    ```yaml
    environment:
      - ADMIN_PASSWORD=mysecretpassword
    ```

=== "Linux (systemd)"
    ```ini
    Environment=ADMIN_PASSWORD=mysecretpassword
    ```

!!! note
    When this variable is set, the CLI `flask reset-password` command and the in-UI password change have no effect — the password always comes from this variable. Remove the variable to switch back to `manager.yml`-managed passwords.

---

### `DOMAINS`

**Default:** `example.com`
**Overrides:** `domains` in `manager.yml`

Comma-separated list of base domains shown in the **Add Route** form.

=== "Docker / Podman"
    ```yaml
    environment:
      - DOMAINS=example.com,home.lab
    ```

=== "Linux (systemd)"
    ```ini
    Environment=DOMAINS=example.com,home.lab
    ```

---

### `CERT_RESOLVER`

**Default:** `cloudflare`
**Overrides:** `cert_resolver` in `manager.yml`

The default ACME cert resolver name pre-filled in the **Add Route** form.

=== "Docker / Podman"
    ```yaml
    environment:
      - CERT_RESOLVER=letsencrypt
    ```

=== "Linux (systemd)"
    ```ini
    Environment=CERT_RESOLVER=letsencrypt
    ```

---

### `TRAEFIK_API_URL`

**Default:** `http://traefik:8080`
**Overrides:** `traefik_api_url` in `manager.yml`

The URL of the Traefik API. Must be reachable from the host running Traefik Manager.

=== "Docker / Podman"
    ```yaml
    environment:
      - TRAEFIK_API_URL=http://traefik:8080
    ```

=== "Linux (systemd)"
    ```ini
    Environment=TRAEFIK_API_URL=http://localhost:8080
    ```

---

### `CONFIG_PATH`

**Default:** `/app/config/dynamic.yml`

Path to the Traefik dynamic config file. Change this if your layout does not match the default.

=== "Docker / Podman"
    ```yaml
    environment:
      - CONFIG_PATH=/data/traefik/dynamic.yml
    volumes:
      - /path/to/traefik/dynamic.yml:/data/traefik/dynamic.yml
    ```

=== "Linux (systemd)"
    ```ini
    Environment=CONFIG_PATH=/etc/traefik/dynamic.yml
    ```

---

### `BACKUP_DIR`

**Default:** `/app/backups`

Directory where timestamped backups of `dynamic.yml` are stored before every save.

=== "Docker / Podman"
    ```yaml
    environment:
      - BACKUP_DIR=/data/backups
    volumes:
      - /path/to/backups:/data/backups
    ```

=== "Linux (systemd)"
    ```ini
    Environment=BACKUP_DIR=/var/lib/traefik-manager/backups
    ```

---

### `SETTINGS_PATH`

**Default:** `/app/config/manager.yml`

Path to the Traefik Manager settings file. Useful if you want to separate it from the dynamic config directory.

=== "Docker / Podman"
    ```yaml
    environment:
      - SETTINGS_PATH=/data/manager.yml
    volumes:
      - /path/to/manager.yml:/data/manager.yml
    ```

=== "Linux (systemd)"
    ```ini
    Environment=SETTINGS_PATH=/var/lib/traefik-manager/manager.yml
    ```

---

### `OTP_ENCRYPTION_KEY`

**Default:** _(auto-generated and stored at `/app/config/.otp_key`)_

Fernet symmetric key used to encrypt the TOTP secret at rest in `manager.yml`. If not set, a key is automatically generated on first start and written to `.otp_key` inside the config directory.

Set this variable if you want to manage the key yourself (e.g., from a secrets manager) or to ensure the key survives config volume replacement.

=== "Docker / Podman"
    ```yaml
    environment:
      - OTP_ENCRYPTION_KEY=your-32-byte-url-safe-base64-key
    ```

=== "Linux (systemd)"
    ```ini
    Environment=OTP_ENCRYPTION_KEY=your-32-byte-url-safe-base64-key
    ```

!!! tip "Generating a key"
    ```bash
    python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    ```

!!! note
    If you lose this key, existing TOTP secrets become unreadable and 2FA will need to be re-enrolled. The `.otp_key` file is separate from `manager.yml` — back it up alongside your config volume.
