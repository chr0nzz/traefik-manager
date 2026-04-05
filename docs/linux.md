# Running on Linux (without Docker)

Traefik Manager is a standard Python/Flask application and runs natively on any Linux system with Python 3.11+. No container runtime required.

---

## Requirements

- Python 3.11 or newer
- `pip`
- A running Traefik instance reachable from the same host
- Write access to your Traefik `dynamic.yml`

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

**3. Create the data directories**

```bash
mkdir -p /var/lib/traefik-manager/backups
```

**4. Test run**

```bash
CONFIG_PATH=/etc/traefik/dynamic.yml \
BACKUP_DIR=/var/lib/traefik-manager/backups \
SETTINGS_PATH=/var/lib/traefik-manager/manager.yml \
COOKIE_SECURE=false \
/opt/traefik-manager/venv/bin/gunicorn \
  --bind 0.0.0.0:5000 \
  --workers 1 \
  --chdir /opt/traefik-manager \
  app:app
```

Open **http://your-server:5000** - the setup wizard will guide you through the rest.

---

## Systemd service

Running as a systemd service gives you automatic start on boot and restart on crash.

**1. Create a dedicated user (recommended)**

```bash
useradd --system --no-create-home --shell /usr/sbin/nologin traefik-manager
```

Give it read/write access to the files it needs:

```bash
# Write access to dynamic.yml and its directory (for backups/config)
chown traefik-manager: /etc/traefik/dynamic.yml
chown traefik-manager: /var/lib/traefik-manager
chown traefik-manager: /var/lib/traefik-manager/backups

# Read-only optional mounts (if using Certs/Plugins/Logs tabs)
# The user just needs read access to these files
```

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
    --bind 0.0.0.0:5000 \
    --workers 1 \
    --log-level info \
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

---

## Optional monitoring mounts

The Certs, Plugins, and Logs tabs work the same as with Docker - just point the env vars at your existing files:

```ini
# In the [Service] section of the systemd unit:

# Certs tab - path to acme.json
Environment=ACME_JSON_PATH=/etc/traefik/acme.json

# Plugins tab - path to traefik.yml
Environment=STATIC_CONFIG_PATH=/etc/traefik/traefik.yml

# Logs tab - path to access.log
Environment=ACCESS_LOG_PATH=/logs/access.log
```

Make sure `traefik-manager` user has read access to each file:

```bash
chmod o+r /etc/traefik/acme.json
chmod o+r /etc/traefik/traefik.yml
chmod o+r /var/log/traefik/access.log
```

Access logs are often owned by `root` or a `adm`/`syslog` group. If `chmod o+r` is not appropriate for your setup, add the user to the owning group instead:

```bash
usermod -aG adm traefik-manager
```

---

## Config file setup

### Single config file (default)

The default setup. Point `CONFIG_PATH` at your dynamic config file:

```ini
# In the [Service] section of the systemd unit:
Environment=CONFIG_PATH=/etc/traefik/dynamic.yml
```

### Multiple config files

Mount more than one Traefik dynamic config and manage them all from one UI. A **Config File** picker appears automatically in the route and middleware forms when more than one file is loaded.

:::tabs
== CONFIG_PATHS (explicit list)
Comma-separated list of config file paths. Use this when you want to name exactly which files are managed.

```ini
# In the [Service] section of the systemd unit:
# Single config file (default):
# Environment=CONFIG_PATH=/etc/traefik/dynamic.yml
# Multiple config files:
Environment=CONFIG_PATHS=/etc/traefik/routes.yml,/etc/traefik/services.yml
```

Make sure `traefik-manager` user has read/write access to each file.

== CONFIG_DIR (auto-discover from directory)
Point at a directory and every `.yml` file inside it is picked up automatically. Useful when the number of config files changes over time.

```ini
# In the [Service] section of the systemd unit:
# Single config file (default):
# Environment=CONFIG_PATH=/etc/traefik/dynamic.yml
# Multiple config files (auto-discover):
Environment=CONFIG_DIR=/etc/traefik/conf.d
```

Make sure `traefik-manager` user has read/write access to the directory and all `.yml` files in it.
:::

See the [Environment Variables](env-vars.md) reference for the full priority order.

---

## Behind a reverse proxy (nginx or Traefik)

When serving Traefik Manager over HTTPS through a reverse proxy, set `COOKIE_SECURE=true` in the service unit and remove the direct port binding.

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

Without Docker, use the `flask` CLI directly from the install directory:

```bash
cd /opt/traefik-manager
SETTINGS_PATH=/var/lib/traefik-manager/manager.yml \
  venv/bin/flask reset-password
```

With `--disable-otp` if you have also lost access to your TOTP app:

```bash
cd /opt/traefik-manager
SETTINGS_PATH=/var/lib/traefik-manager/manager.yml \
  venv/bin/flask reset-password --disable-otp
```

---

## Updating

```bash
cd /opt/traefik-manager
git pull
source venv/bin/activate
pip install -r requirements.txt gunicorn
systemctl restart traefik-manager
```

---

## Uninstall

```bash
systemctl disable --now traefik-manager
rm /etc/systemd/system/traefik-manager.service
systemctl daemon-reload
rm -rf /opt/traefik-manager
# Keep /var/lib/traefik-manager if you want to preserve your settings and backups
```
