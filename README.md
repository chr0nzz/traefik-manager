<div align="center">

<img src="https://user.fm/files/v2-1b91adfdc6068ede7e20f5fe6bc80e41/fav.ico" width="64" height="64" alt="Traefik Manager">

# Traefik Manager

**A clean, self-hosted web UI for managing your Traefik reverse proxy.**

Add routes, manage middlewares, monitor services, and view TLS certificates — all without touching a YAML file by hand.

[![Docker Image](https://img.shields.io/badge/ghcr.io-chr0nzz%2Ftraefik--manager-blue?logo=docker&logoColor=white)](https://github.com/chr0nzz/traefik-manager/pkgs/container/traefik-manager)
[![License](https://img.shields.io/github/license/chr0nzz/traefik-manager)](LICENSE)
[![Version](https://img.shields.io/github/v/release/chr0nzz/traefik-manager)](https://github.com/chr0nzz/traefik-manager/releases)

</div>
<div align="center">
<sub>Built for homelabbers who love Traefik but hate editing YAML at 2am.</sub>
</div>

---

## Screenshots

> _Screenshots coming soon_

<!-- Replace the comments below with your actual screenshot paths once added -->
<!-- ![Dashboard](screenshots/dashboard.png) -->
<!-- ![Add Route](screenshots/add-route.png) -->
<!-- ![Setup Wizard](screenshots/setup.png) -->
<!-- ![Certificates](screenshots/certs.png) -->

---

## Features

- **Route management** — add, edit, and delete HTTP, TCP, and UDP routes via a simple form
- **Middleware management** — create and manage Traefik middlewares with built-in templates (Basic Auth, Forward Auth, Redirect, Strip Prefix)
- **Live dashboard** — real-time stats pulled from the Traefik API: router counts, service health, entrypoints, and version
- **TLS certificates** — view all certificates from `acme.json` with expiry tracking
- **Plugin viewer** — inspect plugins configured in your static `traefik.yml`
- **Access logs** — stream and filter Traefik access logs in the browser
- **Docker container view** — see running containers via the Docker socket
- **Automatic backups** — every config change creates a timestamped backup of `dynamic.yml`
- **Built-in auth** — password-protected with bcrypt hashing, session management, and CSRF protection
- **First-run setup wizard** — configure everything (domains, API URL, cert resolver, visible tabs, password) on first launch
- **Dark / light theme** — persisted per browser

---

## Requirements

- Docker + Docker Compose
- A running [Traefik v2/v3](https://traefik.io/) instance
- Traefik's `dynamic.yml` file accessible on the host

---

## Quick Start

### Using the pre-built image (recommended)

Create a `docker-compose.yml`:

```yaml
services:
  traefik-manager:
    image: ghcr.io/chr0nzz/traefik-manager:latest
    container_name: traefik-manager
    restart: unless-stopped
    ports:
      - "5000:5000"
    environment:
      - COOKIE_SECURE=true
    volumes:
      - /path/to/traefik/dynamic.yml:/app/config/dynamic.yml
      - /path/to/traefik-manager/config:/app/config
      - /path/to/traefik-manager/backups:/app/backups
```

Then run:

```bash
docker compose up -d
```

Open **http://your-server:5000** — the setup wizard will guide you through the rest.

---

## Volume Mounts

| Host path | Container path | Required | Purpose |
|---|---|---|---|
| `/path/to/traefik/dynamic.yml` | `/app/config/dynamic.yml` | ✅ | Traefik dynamic config — this is what Traefik Manager reads and writes |
| `/path/to/traefik-manager/config` | `/app/config` | ✅ | Persists `manager.yml` (settings) and the session secret key |
| `/path/to/traefik-manager/backups` | `/app/backups` | ✅ | Stores timestamped backups of `dynamic.yml` before every change |
| `/path/to/traefik/acme.json` | `/app/acme.json` | ➕ Optional | Enables the **Certs** tab |
| `/path/to/traefik/traefik.yml` | `/app/traefik.yml` | ➕ Optional | Enables the **Plugins** tab |
| `/path/to/traefik/logs/access.log` | `/app/logs/access.log` | ➕ Optional | Enables the **Logs** tab |
| `/var/run/docker.sock` | `/var/run/docker.sock` | ➕ Optional | Enables the **Docker** tab |

> **Note:** The docker.sock is used to retrieve metadata such as container labels and IPs. It isn't required for monitoring (@docker) when using docker labels and is only necessary if you want the Docker Tab to display extra container information.

---

## Optional Monitoring Tabs

Traefik Manager includes four optional views that require additional mounts. They can be enabled during the setup wizard or toggled anytime in Settings. If a required file isn't mounted yet, the tab will show the exact line to add to your compose file.

### Certs tab

Mount your `acme.json` read-only:

```yaml
volumes:
  - /path/to/traefik/acme.json:/app/acme.json:ro
```

### Plugins tab

Mount your Traefik static config read-only:

```yaml
volumes:
  - /path/to/traefik/traefik.yml:/app/traefik.yml:ro
```

### Logs tab

First, enable access logging in your `traefik.yml`:

```yaml
accessLog:
  filePath: "/logs/access.log"
```

Then mount the log file into the traefik-manager container:

```yaml
volumes:
  - /path/to/traefik/logs/access.log:/app/logs/access.log:ro
```

> Traefik must be restarted after adding `accessLog` to `traefik.yml`. Traefik Manager does not need to restart for any of these mounts.

### Docker tab

Mount the Docker socket for extra information - Not required to view @docker routing:

```yaml
volumes:
  - /var/run/docker.sock:/var/run/docker.sock:ro
```

## Full compose example (all tabs enabled)

```yaml
services:
  traefik-manager:
    image: ghcr.io/chr0nzz/traefik-manager:latest
    container_name: traefik-manager
    restart: unless-stopped
    ports:
      - "5000:5000"
    environment:
      - COOKIE_SECURE=true
    volumes:
      # Required
      - /path/to/traefik/dynamic.yml:/app/config/dynamic.yml
      - /path/to/traefik-manager/config:/app/config
      - /path/to/traefik-manager/backups:/app/backups
      # Optional monitoring
      - /path/to/traefik/acme.json:/app/acme.json:ro
      - /path/to/traefik/traefik.yml:/app/traefik.yml:ro
      - /path/to/traefik/logs/access.log:/app/logs/access.log:ro
      - /var/run/docker.sock:/var/run/docker.sock:ro
```

---

## Behind Traefik (expose via subdomain)

To expose Traefik Manager through Traefik itself, remove the `ports` mapping and add labels:

```yaml
services:
  traefik-manager:
    image: ghcr.io/chr0nzz/traefik-manager:latest
    container_name: traefik-manager
    restart: unless-stopped
    environment:
      - COOKIE_SECURE=true
    volumes:
      - /path/to/traefik/dynamic.yml:/app/config/dynamic.yml
      - /path/to/traefik-manager/config:/app/config
      - /path/to/traefik-manager/backups:/app/backups
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.traefik-manager.rule=Host(`manager.example.com`)"
      - "traefik.http.routers.traefik-manager.entrypoints=https"
      - "traefik.http.routers.traefik-manager.tls.certresolver=cloudflare"
      - "traefik.http.services.traefik-manager.loadbalancer.server.port=5000"
    networks:
      - traefik

networks:
  traefik:
    external: true
```

> `COOKIE_SECURE=true` is required when running behind HTTPS so the session cookie is sent correctly.

---

## Building from source

### With Docker Compose

```bash
git clone https://github.com/chr0nzz/traefik-manager.git
cd traefik-manager
```

Edit the volumes in `docker-compose.yml` to match your paths, then:

```bash
docker compose up -d --build
```

### With Docker directly

```bash
git clone https://github.com/chr0nzz/traefik-manager.git
cd traefik-manager

docker build -t traefik-manager .

docker run -d \
  --name traefik-manager \
  --restart unless-stopped \
  -p 5000:5000 \
  -e COOKIE_SECURE=true \
  -v /path/to/traefik/dynamic.yml:/app/config/dynamic.yml \
  -v /path/to/traefik-manager/config:/app/config \
  -v /path/to/traefik-manager/backups:/app/backups \
  traefik-manager
```

---

## First-run setup

On first launch you'll be greeted by a setup wizard:

1. **Connection & domains** — enter your base domains (e.g. `example.com, example.net`), certificate resolver name, and the internal Traefik API URL (usually `http://traefik:8080` on the same Docker network). Use the **Test connection** button to verify before proceeding.
2. **Optional monitoring** — toggle on any of the four optional views (Docker, Certs, Plugins, Logs). You can change these anytime in Settings.
3. **Password** — set a password (minimum 8 characters) to protect the UI.

All settings are saved to `manager.yml` inside the config volume. The setup wizard only appears once — if you need to re-run it, delete `manager.yml` and restart the container.

---

## Resetting your password

If you forget your password, remove the `password_hash` line from `manager.yml` and restart the container. The setup wizard will appear again for the password step.

```bash
# Edit manager.yml inside your config volume
nano /path/to/traefik-manager/config/manager.yml

# Remove or blank the password_hash line, then restart
docker restart traefik-manager
```

---

## Disabling built-in auth

If you're protecting Traefik Manager externally via Authentik, Authelia, or a Traefik `basicAuth` middleware, you can disable the built-in auth entirely:

```yaml
environment:
  - AUTH_ENABLED=false
```

---

## How it works

Traefik Manager reads and writes Traefik's `dynamic.yml` file directly. Since Traefik watches this file for changes, routes take effect immediately — no Traefik restart needed.

The Traefik API (read-only) is used to pull live stats, service health, router details, and version information shown in the dashboard.

Every time you save or delete a route or middleware, a timestamped backup of `dynamic.yml` is created in the backups directory before the change is written. You can restore any backup from the Settings panel.

---

## Tech stack

| Layer | Technology |
|---|---|
| Backend | Python 3.11 · Flask · Gunicorn |
| Config parsing | ruamel.yaml (preserves comments and formatting) |
| Auth | bcrypt · Flask sessions · CSRF protection |
| Frontend | Vanilla JS · Tailwind CSS (CDN) · Phosphor Icons |
| Container | Docker · Alpine Linux |

---

## Contributing

Pull requests are welcome. For larger changes, please open an issue first to discuss what you'd like to change.

---

## License

[GPL-3.0 license](LICENSE)
