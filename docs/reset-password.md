# Reset Password

This page covers all methods for recovering access to Traefik Manager. All of them need shell or file access to the host.

---

## Method 1 - tm CLI (recommended)

If the stack was installed with [tm](tm-cli.md), one command covers every install type. It works out where Traefik Manager keeps its settings, and runs the reset below as the user that owns them.

```bash
tm password reset
```

You are asked for the new password twice, hidden, and can log in with it straight away. Add `--disable-otp` if you have also lost your authenticator, `--stdin` to pipe it from a script, or `--random` for a temporary password instead.

Needs Traefik Manager v1.12.0 or newer. On older versions `tm` says so and points you at `--random`.

---

## Method 2 - Flask CLI

### Set your own password

| Option | Use it for |
|---|---|
| `--prompt` | Typing the password yourself. Asked twice, never echoed |
| `--stdin` | Scripts and automation |
| `--password TEXT` | One-off scripted calls. Visible in `ps` output and shell history, so prefer `--stdin` |

Minimum 8 characters, maximum 72 bytes - the bcrypt limit. Accented and non-Latin characters take more than one byte each, so a passphrase can pass 72 bytes at well under 72 characters.

Pass only one of the three. Nothing is written if the password is rejected. All three refuse to run while [`ADMIN_PASSWORD`](env-vars.md#admin-password) is set - change or unset that variable instead.

:::tabs
== Docker
```bash
docker exec -it traefik-manager flask reset-password --prompt
```

From a script:
```bash
printf '%s' "$NEW_PASSWORD" | docker exec -i traefik-manager flask reset-password --stdin
```

== Podman
```bash
podman exec -it traefik-manager flask reset-password --prompt
```

From a script:
```bash
printf '%s' "$NEW_PASSWORD" | podman exec -i traefik-manager flask reset-password --stdin
```

== Unraid
Open the Unraid dashboard → Docker tab → click the Traefik Manager icon → **Console**, then run:
```bash
flask reset-password --prompt
```

== umbrelOS
Open a terminal on the Umbrel, over SSH or from **Settings**, **Advanced settings**, **Terminal**, then run:
```bash
sudo docker exec -it tm-traefik-manager_web_1 flask reset-password --prompt
```

== Linux (native)
```bash
cd /opt/traefik-manager
SETTINGS_PATH=/var/lib/traefik-manager/manager.yml \
  venv/bin/flask reset-password --prompt
```

From a script:
```bash
cd /opt/traefik-manager
printf '%s' "$NEW_PASSWORD" | sudo -u traefik-manager \
  env SETTINGS_PATH=/var/lib/traefik-manager/manager.yml \
  venv/bin/flask reset-password --stdin
```
:::

The password is confirmed but not printed back. Log in with it straight away: no forced change screen, and `/setup` stays closed.

::: info Lost your authenticator too?
Two-factor authentication is **preserved** by default. Add `--disable-otp` to any form of the command to reset the password and turn 2FA off in one step, then re-enable it from **Settings → Authentication → Password & 2FA**.
:::

### Temporary password

Run the command with no password option. A random password is printed to the terminal, and on your next login you are sent to a forced password-change screen before you reach the dashboard.

:::tabs
== Docker
```bash
docker exec traefik-manager flask reset-password
```

== Podman
```bash
podman exec traefik-manager flask reset-password
```

== Unraid
Open the Unraid dashboard → Docker tab → click the Traefik Manager icon → **Console**, then run:
```bash
flask reset-password
```

== umbrelOS
Open a terminal on the Umbrel, over SSH or from **Settings**, **Advanced settings**, **Terminal**, then run:
```bash
sudo docker exec tm-traefik-manager_web_1 flask reset-password
```

== Linux (native)
```bash
cd /opt/traefik-manager
SETTINGS_PATH=/var/lib/traefik-manager/manager.yml \
  venv/bin/flask reset-password
```
:::

::: warning Temporary passwords only
This form also sets `setup_password_reset: true` in `manager.yml`, which leaves `/setup` open to anyone who can reach Traefik Manager until you use it. Set your new password promptly. The flag clears on any password change and on your next successful sign-in, by password, two-factor or OIDC. With two-factor on, the reset page also asks for a current code. With `ADMIN_PASSWORD` set, or local login turned off, the page refuses and clears the flag. `--prompt`, `--stdin` and `--password` never set it.

Every reset signs out all browser sessions.
:::

---

## Method 3 - Manual reset via manager.yml

Use this if you cannot exec into the container (e.g. the container won't start).

**1. Add the reset flag** to `manager.yml`:

```yaml
setup_password_reset: true
```

If two-factor is on and you no longer have the authenticator, also set `otp_enabled: false`, since the reset page asks for a current code.

**2. Restart:**

:::tabs
== Docker
```bash
nano /path/to/traefik-manager/config/manager.yml
docker compose restart traefik-manager
```

== Podman
```bash
nano /path/to/traefik-manager/config/manager.yml
podman restart traefik-manager
```

== Unraid
```bash
nano /mnt/user/appdata/traefik-manager/config/manager.yml
```
Then Docker tab → click the Traefik Manager icon → **Restart**.

== umbrelOS
```bash
sudo nano ~/umbrel/app-data/tm-traefik-manager/data/tm/config/manager.yml
sudo docker restart tm-traefik-manager_web_1
```

== Linux (native)
```bash
nano /var/lib/traefik-manager/manager.yml
systemctl restart traefik-manager
```
:::

**3. Open `/setup`** (`https://your-traefik-manager.example.com/setup`). You are asked for a new password and nothing else. Setting it clears the flag and signs you in.

::: warning
While the flag is set, anyone who can reach Traefik Manager can set the password. Restart, set the new password, and confirm you are signed in.
:::

---

## Method 4 - Write a password hash into manager.yml

Use this if you cannot run the CLI at all. Generate a bcrypt hash:

:::tabs
== Docker
```bash
docker run --rm ghcr.io/chr0nzz/traefik-manager:latest \
  python3 -c "import bcrypt; print(bcrypt.hashpw(b'yournewpassword', bcrypt.gensalt()).decode())"
```

== Podman
```bash
podman run --rm ghcr.io/chr0nzz/traefik-manager:latest \
  python3 -c "import bcrypt; print(bcrypt.hashpw(b'yournewpassword', bcrypt.gensalt()).decode())"
```

== Unraid
Open a terminal from the Unraid dashboard, then run:
```bash
docker run --rm ghcr.io/chr0nzz/traefik-manager:latest \
  python3 -c "import bcrypt; print(bcrypt.hashpw(b'yournewpassword', bcrypt.gensalt()).decode())"
```

== Linux (native)
```bash
cd /opt/traefik-manager
venv/bin/python3 -c "import bcrypt; print(bcrypt.hashpw(b'yournewpassword', bcrypt.gensalt()).decode())"
```
:::

Update `manager.yml`:

```yaml
password_hash: "$2b$12$..."
must_change_password: false
setup_complete: true
```

Restart the container - no wizard, no forced change, log in immediately with the password you set.

Browsers signed in before the change stay signed in unless you also raise `session_epoch` by one.

See [manager.yml reference](manager-yml.md) for all available fields.

---

## Two-factor authentication

### Enable 2FA

1. **Settings → Authentication → Password & 2FA → Enable 2FA**
2. Scan the QR code with your TOTP app (Google Authenticator, Authy, 1Password, etc.)
3. Enter the 6-digit code to confirm - 2FA is now active

### Disable 2FA (while logged in)

**Settings → Authentication → Password & 2FA → Disable 2FA**. No code is required - you are already authenticated.

### Disable 2FA (locked out)

Use the `--disable-otp` flag with the CLI reset command shown above.
