# Running on Linux (without Docker)

::: tip This page is the Traefik Manager server
Installing the **agent** (TMA) on a remote server is a different setup with a different variable set - it uses `CONFIG_PATH` only, and has no `CONFIG_DIR` or `CONFIG_PATHS`. See [Agent](agent.md) for that.
:::

Traefik Manager is a standard Python/Flask application and runs natively on any Linux system with Python 3.11+. No container runtime required.

---

## Requirements

- Python 3.11 or newer, with the `venv` module (`sudo apt install python3-venv` on Debian and Ubuntu)
- `pip`
- A running Traefik instance reachable from the same host
- Write access to your Traefik `dynamic.yml` and the directory holding it

---

## Install

**1. Clone the repository**

```bash
git clone https://github.com/chr0nzz/traefik-manager.git /opt/traefik-manager
cd /opt/traefik-manager
```

**2. Create a virtual environment and install dependencies**

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt gunicorn
```

**3. Download vendor assets and build CSS**

```bash
bash scripts/setup-assets.sh
```

This downloads Monaco, fonts, icons and the other vendored JS libraries, then compiles Tailwind CSS - none of them are in the Git repository. It runs from any directory and needs no `sudo`: when `/usr/local/bin` is not writable the `tailwindcss` binary goes to a temporary location instead.

**4. Create the data directories**

```bash
mkdir -p /var/lib/traefik-manager/backups
```

**5. Test run**

```bash
CONFIG_PATH=/etc/traefik/dynamic.yml \
BACKUP_DIR=/var/lib/traefik-manager/backups \
SETTINGS_PATH=/var/lib/traefik-manager/manager.yml \
COOKIE_SECURE=false \
/opt/traefik-manager/venv/bin/gunicorn \
  --config /opt/traefik-manager/gunicorn.conf.py \
  --bind 0.0.0.0:5000 \
  --chdir /opt/traefik-manager \
  app:app
```

Open **http://your-server:5000** and log in with the temporary password printed in the startup output, then the setup wizard takes over.

---

## Systemd service

Running as a systemd service gives you start on boot and restart on crash.

**1. Create a dedicated user (recommended)**

```bash
useradd --system --no-create-home --shell /usr/sbin/nologin traefik-manager
```

Give it write access to the config file **and its directory** - saves are written to a temporary file next to the config and then renamed:

```bash
chown traefik-manager: /etc/traefik /etc/traefik/dynamic.yml
chown traefik-manager: /var/lib/traefik-manager /var/lib/traefik-manager/backups
```

Read access is enough for the optional Logs file. The Certs tab needs more, see [acme.json](#acme-json).

**2. Create the service unit**

Create `/etc/systemd/system/traefik-manager.service`:

```ini
[Unit]
Description=Traefik Manager
After=network.target

[Service]
Type=simple
User=traefik-manager
WorkingDirectory=/opt/traefik-manager
Environment=HOME=/opt/traefik-manager
ExecStart=/opt/traefik-manager/venv/bin/gunicorn \
    --config /opt/traefik-manager/gunicorn.conf.py \
    --bind 0.0.0.0:5000 \
    app:app

# Paths
Environment=CONFIG_PATH=/etc/traefik/dynamic.yml
Environment=BACKUP_DIR=/var/lib/traefik-manager/backups
Environment=SETTINGS_PATH=/var/lib/traefik-manager/manager.yml

# Set to true if running behind a reverse proxy with HTTPS
Environment=COOKIE_SECURE=false

Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

::: tip Real client IPs behind another proxy
With one proxy in front (Traefik), the default is correct. If something else sits in front of Traefik as well - Cloudflare, a load balancer, another reverse proxy - set `PROXY_FIX_HOPS` to the number of hops you control, so the login and audit log record the real client instead of the intermediate proxy:

```ini
Environment=PROXY_FIX_HOPS=2
```

Only count hops you actually control: each trusted hop is one more `X-Forwarded-For` entry a client could forge. The [Client IP Diagnostic](tab-logs.md) in the nav bar shows what the app currently sees. Forwarding headers are only read from `TRUSTED_PROXIES`, which by default covers loopback, private and Tailscale addresses.
:::

**3. Enable and start**

```bash
systemctl daemon-reload
systemctl enable --now traefik-manager
```

**4. Check it is running**

```bash
systemctl status traefik-manager
journalctl -u traefik-manager -f
```

The temporary first-run password is in that journal output.

---

## Optional monitoring paths

The Certs, Plugins and Logs tabs work as they do under Docker - point the env vars at your existing files, then switch each tab on in **Settings -> System Monitoring**:

```ini
# In the [Service] section of the systemd unit:

# Certs tab - path to acme.json
Environment=ACME_JSON_PATH=/etc/traefik/acme.json

# Plugins + Static Config - path to traefik.yml
Environment=STATIC_CONFIG_PATH=/etc/traefik/traefik.yml

# Logs tab - path to access.log
Environment=ACCESS_LOG_PATH=/var/log/traefik/access.log
```

The `traefik-manager` user needs read access to the Plugins and Logs files:

```bash
chmod o+r /etc/traefik/traefik.yml   # write access instead, for the Static Config editor
chmod o+r /var/log/traefik/access.log
```

Access logs are often owned by `root` or an `adm`/`syslog` group. Where `chmod o+r` is not appropriate, add the user to the owning group instead:

```bash
usermod -aG adm traefik-manager
```

### acme.json

Traefik refuses an `acme.json` with any group or other permission and stops loading certificates at its next start. `chmod o+r` sets one, and so does `setfacl`, because the ACL mask shows as the group bits. Keep the file at `600` and run Traefik Manager as the user that owns it.

| Certs tab | Needs |
|---|---|
| View certificates | `User=` in the Traefik Manager unit set to the owner of `acme.json` |
| Remove certificates | The same, plus a [restart method](#static-config-editor) |

Then `chown` the paths from [Systemd service](#systemd-service) to that user instead of `traefik-manager`.

---

## Static config editor

Edit `traefik.yml` from the UI. After saving, click **Restart Traefik** to apply the change with your configured restart method.

### Requirements

Give `traefik-manager` write access to `traefik.yml` and set `RESTART_METHOD` in the service unit. Choose where the editor appears in **Settings -> Interface -> Tabs -> Static Config**: `Off`, `Settings` (inside the settings window) or `Tab` (its own side-nav entry).

```bash
chown traefik-manager: /etc/traefik/traefik.yml
```

### Method 1: Poison pill (recommended)

Traefik Manager writes a signal file, a watcher script sees it and restarts Traefik. No Docker socket access needed.

Add to the `[Service]` section of your unit file:

```ini
Environment=RESTART_METHOD=poison-pill
Environment=SIGNAL_FILE_PATH=/var/lib/traefik-manager/signals/restart.sig
```

Create a watcher script at `/usr/local/bin/traefik-restart-watcher.sh`:

```bash
#!/bin/sh
SIGNAL=/var/lib/traefik-manager/signals/restart.sig
mkdir -p "$(dirname "$SIGNAL")"
while true; do
  if [ -f "$SIGNAL" ]; then
    systemctl restart traefik
    rm -f "$SIGNAL"
  fi
  sleep 2
done
```

Make it executable:

```bash
chmod +x /usr/local/bin/traefik-restart-watcher.sh
```

Create `/etc/systemd/system/traefik-restart-watcher.service`:

```ini
[Unit]
Description=Traefik restart watcher
After=network.target

[Service]
Type=simple
ExecStart=/usr/local/bin/traefik-restart-watcher.sh
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

Enable it:

```bash
systemctl daemon-reload
systemctl enable --now traefik-restart-watcher
```

### Method 2: Direct Docker socket

When Traefik itself runs as a Docker container, give `traefik-manager` access to the socket:

```bash
usermod -aG docker traefik-manager
```

Add to the `[Service]` section:

```ini
Environment=RESTART_METHOD=socket
Environment=TRAEFIK_CONTAINER=traefik
```

### Environment variables

| Variable | Values | Default | Description |
|---|---|---|---|
| `RESTART_METHOD` | `proxy`, `socket`, `poison-pill` | `proxy` | How to restart Traefik after a static config change (`proxy` and `socket` both restart the container over the Docker API) |
| `TRAEFIK_CONTAINER` | container name | `traefik` | Docker container to restart (socket method) |
| `SIGNAL_FILE_PATH` | path | `/signals/restart.sig` | Signal file for the `poison-pill` method |

---

## Config file setup

### Single config file (default)

Point `CONFIG_PATH` at your dynamic config file:

```ini
# In the [Service] section of the systemd unit:
Environment=CONFIG_PATH=/etc/traefik/dynamic.yml
```

### Multiple config files

Manage several Traefik dynamic configs from one UI. A **Config File** picker appears in the route, middleware and TLS option forms once more than one file is loaded.

:::tabs
== CONFIG_PATHS (explicit list)
Comma-separated list of config file paths. Use it to name exactly which files are managed.

```ini
# In the [Service] section of the systemd unit:
# Single config file (default):
# Environment=CONFIG_PATH=/etc/traefik/dynamic.yml
# Multiple config files:
Environment=CONFIG_PATHS=/etc/traefik/routes.yml,/etc/traefik/services.yml
```

The `traefik-manager` user needs read/write access to each file and to its directory.

== CONFIG_DIR (auto-discover from directory)
Point at a directory and every `.yml` and `.yaml` file inside it, subdirectories included, is picked up. Useful when the number of config files changes over time.

```ini
# In the [Service] section of the systemd unit:
# Single config file (default):
# Environment=CONFIG_PATH=/etc/traefik/dynamic.yml
# Multiple config files (auto-discover):
Environment=CONFIG_DIR=/etc/traefik/conf.d
```

The `traefik-manager` user needs read/write access to the directory and every `.yml` file in it.
:::

See the [Environment Variables](env-vars.md) reference for the full priority order.

---

## Behind a reverse proxy (nginx or Traefik)

When serving Traefik Manager over HTTPS through a reverse proxy, set `COOKIE_SECURE=true` in the service unit and remove the direct port binding.

To serve Traefik Manager under a path rather than its own hostname, set [`BASE_PATH`](env-vars.md#base-path).

### nginx

```nginx
server {
    listen 443 ssl;
    server_name manager.example.com;

    ssl_certificate     /etc/letsencrypt/live/manager.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/manager.example.com/privkey.pem;

    location / {
        proxy_pass         http://127.0.0.1:5000;
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
        proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
    }
}
```

### Traefik (file provider)

Add to your `dynamic.yml`:

```yaml
http:
  routers:
    traefik-manager:
      rule: "Host(`manager.example.com`)"
      entrypoints: [https]
      tls:
        certResolver: cloudflare
      service: traefik-manager

  services:
    traefik-manager:
      loadBalancer:
        servers:
          - url: "http://127.0.0.1:5000"
```

---

## Password reset

Without Docker, run the `flask` CLI from the install directory:

```bash
cd /opt/traefik-manager
SETTINGS_PATH=/var/lib/traefik-manager/manager.yml \
  venv/bin/flask reset-password --prompt
```

Asks for the new password twice, hidden, and sets it. Drop `--prompt` to get a random temporary password and a forced change at next login instead. Two-factor authentication is preserved - add `--disable-otp` if you have also lost your TOTP app. Other recovery methods: [Reset Password](reset-password.md).

---

## Updating

```bash
cd /opt/traefik-manager
git pull
source venv/bin/activate
pip install -r requirements.txt gunicorn
bash scripts/setup-assets.sh
systemctl restart traefik-manager
```

Run `setup-assets.sh` on every update - new versions may add vendor libraries or use Tailwind classes that are not in the compiled stylesheet.

---

## Uninstall

```bash
systemctl disable --now traefik-manager
rm /etc/systemd/system/traefik-manager.service
systemctl daemon-reload
rm -rf /opt/traefik-manager
# Keep /var/lib/traefik-manager to preserve your settings and backups
```
