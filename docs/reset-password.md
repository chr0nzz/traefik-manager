# Reset Password

This page covers all methods for recovering access to Traefik Manager.

---

## Method 1 - CLI reset (recommended)

This is the fastest method when you can exec into the container.

:::tabs
== Docker
```bash
docker exec traefik-manager flask reset-password
```

== Podman
```bash
podman exec traefik-manager flask reset-password
```

== Linux (native)
```bash
cd /opt/traefik-manager
SETTINGS_PATH=/var/lib/traefik-manager/manager.yml \
  venv/bin/flask reset-password
```
:::

A new temporary password is printed to the terminal. On your next login you will be redirected to a forced password-change screen before you can access the dashboard.

::: info
Two-factor authentication is **preserved** by default. Your existing TOTP setup remains active.
:::

---

## Lost TOTP access

If you have also lost access to your TOTP authenticator app, add `--disable-otp` to reset both the password and 2FA in one step:

:::tabs
== Docker
```bash
docker exec traefik-manager flask reset-password --disable-otp
```

== Podman
```bash
podman exec traefik-manager flask reset-password --disable-otp
```

== Linux (native)
```bash
cd /opt/traefik-manager
SETTINGS_PATH=/var/lib/traefik-manager/manager.yml \
  venv/bin/flask reset-password --disable-otp
```
:::

This will:

- Generate a new temporary password and print it to the terminal
- Disable TOTP 2FA
- Require a password change on next login

After logging in, you can re-enable 2FA from **Settings → Authentication → Enable 2FA**.

---

## Method 2 - Manual reset via manager.yml

Use this if you cannot exec into the container (e.g. the container won't start).

**1. Open `manager.yml`** in your config volume:

```bash
nano /path/to/traefik-manager/config/manager.yml
```

**2. Remove or blank the password hash and mark setup incomplete:**

```yaml
password_hash: ""
setup_complete: false
```

**3. Restart:**

:::tabs
== Docker
```bash
docker restart traefik-manager
```

== Podman
```bash
podman restart traefik-manager
```

== Linux (native)
```bash
systemctl restart traefik-manager
```
:::

A new temporary password is auto-generated and printed to the logs:

:::tabs
== Docker
```bash
docker compose logs traefik-manager | grep -A3 "AUTO-GENERATED"
```

== Podman
```bash
podman logs traefik-manager | grep -A3 "AUTO-GENERATED"
```

== Linux (native)
```bash
journalctl -u traefik-manager | grep -A3 "AUTO-GENERATED"
```
:::

::: warning
Setting `setup_complete: false` will re-run the setup wizard after login. Your existing routes and settings are not affected - just complete the wizard again.
:::

---

## Method 3 - Pre-set a known password

If you want to set a specific known password instead of using the auto-generated one, generate a bcrypt hash and write it directly to `manager.yml`:

```bash
python3 -c "import bcrypt; print(bcrypt.hashpw(b'yournewpassword', bcrypt.gensalt()).decode())"
```

Update `manager.yml`:

```yaml
password_hash: "$2b$12$..."
must_change_password: false
setup_complete: true
```

Restart the container - no wizard, no forced change, log in immediately with the password you set.

See [manager.yml reference](manager-yml.md) for all available fields.

---

## Two-factor authentication

### Enable 2FA

1. **Settings → Authentication → Enable 2FA**
2. Scan the QR code with your TOTP app (Google Authenticator, Authy, 1Password, etc.)
3. Enter the 6-digit code to confirm - 2FA is now active

### Disable 2FA (while logged in)

**Settings → Authentication → Disable 2FA**

No code is required - you are already authenticated.

### Disable 2FA (locked out)

Use the `--disable-otp` flag with the CLI reset command shown above.
