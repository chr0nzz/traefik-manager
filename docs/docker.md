# Running with Docker

The standard deployment method for Traefik Manager, using Docker Compose.

---

## Minimal compose file

```yaml
services:
  traefik-manager:
    image: ghcr.io/chr0nzz/traefik-manager:latest
    container_name: traefik-manager
    restart: unless-stopped
    ports:
      - "5000:5000"
    environment:
      - COOKIE_SECURE=false
    volumes:
      - /path/to/traefik/dynamic.yml:/app/config/dynamic.yml
      - /path/to/traefik-manager/config:/app/config
      - /path/to/traefik-manager/backups:/app/backups
```

Start it, then read the temporary password from the log:

```bash
docker compose up -d
docker logs traefik-manager | grep -A3 AUTO-GENERATED
```

Open **http://your-server:5000**, log in with that password, and the setup wizard takes over.

> Set `COOKIE_SECURE=true` when running behind HTTPS.

---

## Connecting to Traefik on the same host

Both containers need a shared Docker network to reach each other by container name.

### Create a shared network

```bash
docker network create traefik
```

Add a `networks` block to your compose file:

```yaml
services:
  traefik-manager:
    image: ghcr.io/chr0nzz/traefik-manager:latest
    container_name: traefik-manager
    restart: unless-stopped
    ports:
      - "5000:5000"
    environment:
      - COOKIE_SECURE=false
    volumes:
      - /path/to/traefik/dynamic.yml:/app/config/dynamic.yml
      - /path/to/traefik-manager/config:/app/config
      - /path/to/traefik-manager/backups:/app/backups
    networks:
      - traefik

networks:
  traefik:
    external: true
```

Then in the setup wizard set the Traefik API URL to `http://traefik:8080`.

---

## Optional monitoring mounts

```yaml
volumes:
  - /path/to/traefik/acme.json:/app/acme.json:ro              # Certs tab
  - /path/to/traefik/traefik.yml:/app/traefik.yml             # Plugins + Static Config
  - /path/to/traefik/logs/access.log:/app/logs/access.log:ro  # Logs tab
```

Switch Certs, Plugins and Logs on in **Settings -> System Monitoring**; mounting the file alone does not reveal them. `traefik.yml` also needs `STATIC_CONFIG_PATH=/app/traefik.yml` - that path has no default. The Static Config editor is placed separately, in **Settings -> Interface -> Tabs**.

> Mount `traefik.yml` without `:ro`. Read-only still lists plugins, but saving the static config or installing a plugin fails with a write error.

### Named volumes

Docker cannot mount a single file out of a named volume, so if Traefik stores its certificates or
logs in one, mount the volume as a directory and name the file with an environment variable:

```yaml
services:
  traefik-manager:
    environment:
      ACME_JSON_PATH: /traefik-certs/acme.json
      ACCESS_LOG_PATH: /traefik-logs/access.log
    volumes:
      - traefik_certs:/traefik-certs:ro
      - traefik_logs:/traefik-logs:ro

volumes:
  traefik_certs:
    external: true
  traefik_logs:
    external: true
```

Both default to the bind-mount paths above (`/app/acme.json` and `/app/logs/access.log`), so an
existing deployment needs no change. `STATIC_CONFIG_PATH` and `PLUGINS_DIR` work the same way, and
so does the agent, which reads the same variables.

Either can also be set in **Settings**, which takes precedence over the environment variable.

### Full compose example (all monitoring enabled)

```yaml
services:
  traefik-manager:
    image: ghcr.io/chr0nzz/traefik-manager:latest
    container_name: traefik-manager
    restart: unless-stopped
    ports:
      - "5000:5000"
    environment:
      - COOKIE_SECURE=false
      - STATIC_CONFIG_PATH=/app/traefik.yml
    volumes:
      # Required
      - /path/to/traefik/dynamic.yml:/app/config/dynamic.yml
      - /path/to/traefik-manager/config:/app/config
      - /path/to/traefik-manager/backups:/app/backups
      # Optional monitoring
      - /path/to/traefik/acme.json:/app/acme.json:ro
      - /path/to/traefik/traefik.yml:/app/traefik.yml
      - /path/to/traefik/logs/access.log:/app/logs/access.log:ro
```

---

## Static config editor

Edit `traefik.yml` from the UI: entrypoints, certificate resolvers, providers, plugins, API and dashboard, logging, observability and system options. After saving, click **Restart Traefik** to apply the change with your configured restart method.

### Requirements

Mount `traefik.yml` read-write (no `:ro`), set `STATIC_CONFIG_PATH`, and set `RESTART_METHOD` to one of the methods below. Choose where the editor appears in **Settings -> Interface -> Tabs -> Static Config**: `Off`, `Settings` (inside the settings window) or `Tab` (its own side-nav entry).

### Method 1: Socket proxy (recommended)

A Docker socket proxy limits Traefik Manager to container restart operations.

```yaml
services:
  socket-proxy:
    image: ghcr.io/tecnativa/docker-socket-proxy:latest
    container_name: socket-proxy
    restart: unless-stopped
    environment:
      - CONTAINERS=1
      - POST=1
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
    networks:
      - socket-proxy-net

  traefik-manager:
    image: ghcr.io/chr0nzz/traefik-manager:latest
    container_name: traefik-manager
    restart: unless-stopped
    ports:
      - "5000:5000"
    environment:
      - COOKIE_SECURE=false
      - STATIC_CONFIG_PATH=/app/traefik.yml
      - RESTART_METHOD=proxy
      - DOCKER_HOST=tcp://socket-proxy:2375
      - TRAEFIK_CONTAINER=traefik
    volumes:
      - /path/to/traefik/dynamic.yml:/app/config/dynamic.yml
      - /path/to/traefik-manager/config:/app/config
      - /path/to/traefik-manager/backups:/app/backups
      - /path/to/traefik/traefik.yml:/app/traefik.yml
    networks:
      - traefik
      - socket-proxy-net

networks:
  traefik:
    external: true
  socket-proxy-net:
    internal: true
```

### Method 2: Poison pill

No Docker socket access at all. Traefik Manager writes a signal file to a shared named volume; Traefik's own healthcheck finds it, removes it and kills itself (`kill -TERM 1`), and `restart: unless-stopped` starts it again.

Add the healthcheck to your Traefik service and mount the shared volume on both containers:

```yaml
services:
  traefik:
    image: traefik:latest
    container_name: traefik
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "[ ! -f /signals/restart.sig ] || (rm /signals/restart.sig && kill -TERM 1)"]
      interval: 5s
      timeout: 3s
      retries: 1
    volumes:
      # your existing traefik volumes...
      - traefik-signals:/signals
    networks:
      - traefik

  traefik-manager:
    image: ghcr.io/chr0nzz/traefik-manager:latest
    container_name: traefik-manager
    restart: unless-stopped
    ports:
      - "5000:5000"
    environment:
      - COOKIE_SECURE=false
      - STATIC_CONFIG_PATH=/app/traefik.yml
      - RESTART_METHOD=poison-pill
      - SIGNAL_FILE_PATH=/signals/restart.sig
    volumes:
      - /path/to/traefik/dynamic.yml:/app/config/dynamic.yml
      - /path/to/traefik-manager/config:/app/config
      - /path/to/traefik-manager/backups:/app/backups
      - /path/to/traefik/traefik.yml:/app/traefik.yml
      - traefik-signals:/signals
    networks:
      - traefik

volumes:
  traefik-signals:

networks:
  traefik:
    external: true
```

### Method 3: Direct socket

Simplest setup, but it grants broad Docker API access.

```yaml
services:
  traefik-manager:
    image: ghcr.io/chr0nzz/traefik-manager:latest
    container_name: traefik-manager
    restart: unless-stopped
    ports:
      - "5000:5000"
    environment:
      - COOKIE_SECURE=false
      - STATIC_CONFIG_PATH=/app/traefik.yml
      - RESTART_METHOD=socket
      - TRAEFIK_CONTAINER=traefik
    volumes:
      - /path/to/traefik/dynamic.yml:/app/config/dynamic.yml
      - /path/to/traefik-manager/config:/app/config
      - /path/to/traefik-manager/backups:/app/backups
      - /path/to/traefik/traefik.yml:/app/traefik.yml
      - /var/run/docker.sock:/var/run/docker.sock:ro
    networks:
      - traefik

networks:
  traefik:
    external: true
```

### Environment variables

| Variable | Values | Default | Description |
|---|---|---|---|
| `STATIC_CONFIG_PATH` | path | - | Path to `traefik.yml` inside the container. Required for the Static Config and Plugins tabs. |
| `RESTART_METHOD` | `proxy`, `socket`, `poison-pill` | `proxy` | How to restart Traefik after a static config change. `proxy` and `socket` both restart the container over the Docker API. |
| `TRAEFIK_CONTAINER` | container name | `traefik` | Container to restart (`proxy` and `socket` methods) |
| `DOCKER_HOST` | URL | - | Docker endpoint for the `proxy` method (e.g. `tcp://socket-proxy:2375`) |
| `SIGNAL_FILE_PATH` | path | `/signals/restart.sig` | Signal file for the `poison-pill` method |

---

## Config file setup

### Single config file (default)

Mount one dynamic config file and point `CONFIG_PATH` at it:

```yaml
environment:
  - CONFIG_PATH=/app/config/dynamic.yml
volumes:
  - /path/to/traefik/dynamic.yml:/app/config/dynamic.yml
  - /path/to/traefik-manager/config:/app/config
  - /path/to/traefik-manager/backups:/app/backups
```

`/app/config/dynamic.yml` is the default, so mounting your file there needs no `CONFIG_PATH` at all.

### Multiple config files

Mount several Traefik dynamic configs and manage them from one UI. A **Config File** picker appears in the route, middleware and TLS option forms once more than one file is loaded.

:::tabs
== CONFIG_PATHS (explicit list)
Comma-separated list of config file paths inside the container. Use it to name exactly which files are managed.

```yaml
environment:
  # Single config file (default):
  # - CONFIG_PATH=/app/config/dynamic.yml
  # Multiple config files:
  - CONFIG_PATHS=/app/config/routes.yml,/app/config/services.yml
volumes:
  - /path/to/traefik-manager/config:/app/config
  - /path/to/traefik/routes.yml:/app/config/routes.yml
  - /path/to/traefik/services.yml:/app/config/services.yml
  - /path/to/traefik-manager/backups:/app/backups
```

== CONFIG_DIR (auto-discover from directory)
Point at a directory and every `.yml` and `.yaml` file inside it, subdirectories included, is picked up. Useful when the number of config files changes over time.

```yaml
environment:
  # Single config file (default):
  # - CONFIG_PATH=/app/config/dynamic.yml
  # Multiple config files (auto-discover):
  - CONFIG_DIR=/app/config/traefik
volumes:
  - /path/to/traefik-manager/config:/app/config
  - /path/to/traefik/config:/app/config/traefik
  - /path/to/traefik-manager/backups:/app/backups
```
:::

See the [Environment Variables](env-vars.md) reference for the full priority order.

---

## Behind Traefik (expose via subdomain)

Remove `ports`, add labels, and put both containers on the same network:

To serve Traefik Manager under a path rather than its own hostname, set [`BASE_PATH`](env-vars.md#base-path).

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

> `COOKIE_SECURE=true` is required when running behind HTTPS.

---


::: tip Real client IPs behind another proxy
With one proxy in front (Traefik), the default is correct. If something else sits in front of Traefik as well - Cloudflare, a load balancer, another reverse proxy - set `PROXY_FIX_HOPS` to the number of hops you control, so the login and audit log record the real client instead of the intermediate proxy:

```yaml
environment:
  - PROXY_FIX_HOPS=2
```

Only count hops you actually control: each trusted hop is one more `X-Forwarded-For` entry a client could forge. The [Client IP Diagnostic](tab-logs.md) in the nav bar shows what the app currently sees.
:::

## Building from source

```bash
git clone https://github.com/chr0nzz/traefik-manager.git
cd traefik-manager
docker compose up -d --build
```

### With Docker directly (no compose)

```bash
docker build -t traefik-manager .

docker run -d \
  --name traefik-manager \
  --restart unless-stopped \
  -p 5000:5000 \
  -e COOKIE_SECURE=false \
  -v /path/to/traefik/dynamic.yml:/app/config/dynamic.yml \
  -v /path/to/traefik-manager/config:/app/config \
  -v /path/to/traefik-manager/backups:/app/backups \
  traefik-manager
```

---

## Running as a non-root user

The container runs as root unless you ask otherwise, so upgrading never changes how an existing install runs. To run it as an unprivileged user, give that user your mounted paths on the host, then set `PUID` and `PGID`:

```bash
sudo chown -R 1000:1000 /path/to/traefik-manager/config /path/to/traefik-manager/backups
sudo chown 1000:1000 /path/to/traefik/dynamic.yml
```

```yaml
environment:
  - PUID=1000
  - PGID=1000
```

A mounted Docker socket keeps working: the user is added to the group that owns it. If the configuration directory is not writable by that user, the container stops at startup and says which directory and which `chown` to run. See [`PUID` / `PGID`](env-vars.md#puid-pgid) for the details.

---

## Password reset

```bash
docker exec -it traefik-manager flask reset-password --prompt
```

Asks for the new password twice, hidden, and sets it. Drop `--prompt` to get a random temporary password and a forced change at next login instead. Two-factor authentication is preserved - add `--disable-otp` if you have also lost your TOTP app. Other recovery methods: [Reset Password](reset-password.md).

---

## Volume reference

| Host path | Container path | Required | Purpose |
|---|---|---|---|
| `/path/to/traefik/dynamic.yml` | `/app/config/dynamic.yml` | ✅ | Traefik dynamic config - read and written by Traefik Manager |
| `/path/to/traefik-manager/config` | `/app/config` | ✅ | Persists `manager.yml`, its companion files and the generated keys |
| `/path/to/traefik-manager/backups` | `/app/backups` | ✅ | Timestamped backups before every change |
| `/path/to/traefik/acme.json` | `/app/acme.json` | Optional | Enables the **Certs** tab |
| `/path/to/traefik/traefik.yml` | `/app/traefik.yml` | Optional | Enables the **Plugins** and **Static Config** tabs (also set `STATIC_CONFIG_PATH`); mount read-write to allow editing |
| `/path/to/traefik/logs/access.log` | `/app/logs/access.log` | Optional | Enables the **Logs** tab |
| any `.yml` files | `/app/config/*.yml` | Optional | **Multi-config** - set `CONFIG_PATHS` or `CONFIG_DIR` |
