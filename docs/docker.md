# Running with Docker

The standard deployment method for Traefik Manager using Docker Compose.

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

Start:

```bash
docker compose up -d
```

Open **http://your-server:5000** - the setup wizard will guide you through the rest.

> Set `COOKIE_SECURE=true` when running behind HTTPS.

---

## Connecting to Traefik on the same host

Both containers need to share a Docker network so they can reach each other by container name.

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

Add these volume lines to enable optional tabs:

```yaml
volumes:
  - /path/to/traefik/acme.json:/app/acme.json:ro          # Certs tab
  - /path/to/traefik/traefik.yml:/app/traefik.yml          # Plugins + Static Config tab (read-write)
  - /path/to/traefik/logs/access.log:/app/logs/access.log:ro  # Logs tab
```

> Mount `traefik.yml` without `:ro` if you want to use the Static Config editor. Read-only mounts enable only the Plugins tab.

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

The Static Config tab lets you edit `traefik.yml` directly from the UI - entrypoints, certificate resolvers, plugins, providers, API settings, and log level. After saving, Traefik Manager can restart Traefik automatically.

### Requirements

Mount `traefik.yml` read-write (no `:ro`) and set `RESTART_METHOD` to one of the methods below.

### Method 1: Socket proxy (recommended)

Run a Docker socket proxy alongside Traefik Manager. The proxy limits Traefik Manager to only container restart operations.

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

No Docker socket access for Traefik Manager. Instead, Traefik Manager writes a signal file to a shared named volume. Traefik's own healthcheck detects the file, removes it, and kills itself (`kill -TERM 1`). Docker's `restart: unless-stopped` policy immediately starts a fresh Traefik instance. No extra container needed.

Add a `healthcheck` to your Traefik service and mount the shared volume on both containers:

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

Mount the Docker socket directly into Traefik Manager. Simplest setup but grants broader Docker API access.

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
  traefik:
    external: true
```

### Environment variables

| Variable | Values | Default | Description |
|---|---|---|---|
| `STATIC_CONFIG_PATH` | path | - | Path to `traefik.yml` inside the container. Must be set for the Static Config and Plugins tabs to work. |
| `RESTART_METHOD` | `proxy`, `socket`, `poison-pill` | - | How to restart Traefik after a static config change |
| `TRAEFIK_CONTAINER` | container name | `traefik` | Name of the Traefik container to restart (`proxy` and `socket` methods) |
| `DOCKER_HOST` | URL | - | Docker host URL for the socket proxy method (e.g. `tcp://socket-proxy:2375`) |
| `SIGNAL_FILE_PATH` | path | `/signals/restart.sig` | Signal file path for the `poison-pill` method |

---

## Config file setup

### Single config file (default)

The default setup. Mount one dynamic config file and set `CONFIG_PATH` to point at it:

```yaml
environment:
  - CONFIG_PATH=/app/config/dynamic.yml
volumes:
  - /path/to/traefik/dynamic.yml:/app/config/dynamic.yml
  - /path/to/traefik-manager/config:/app/config
  - /path/to/traefik-manager/backups:/app/backups
```

If you mount your file to `/app/config/dynamic.yml` and do not set `CONFIG_PATH`, that path is used automatically as the default.

### Multiple config files

Mount more than one Traefik dynamic config and manage them all from one UI. A **Config File** picker appears automatically in the route and middleware forms when more than one file is loaded.

:::tabs
== CONFIG_PATHS (explicit list)
Comma-separated list of config file paths inside the container. Use this when you want to name exactly which files are managed.

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
Point at a directory and every `.yml` file inside it is picked up automatically. Useful when the number of config files changes over time.

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

Remove `ports`, add labels, and ensure both containers share the same network:

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

## Password reset

```bash
docker exec traefik-manager flask reset-password
```

Generates a new temporary password and prints it to the terminal. Two-factor authentication is preserved.

If you have also lost access to your TOTP app:

```bash
docker exec traefik-manager flask reset-password --disable-otp
```

---

## Volume reference

| Host path | Container path | Required | Purpose |
|---|---|---|---|
| `/path/to/traefik/dynamic.yml` | `/app/config/dynamic.yml` | ✅ | Traefik dynamic config - read and written by Traefik Manager |
| `/path/to/traefik-manager/config` | `/app/config` | ✅ | Persists `manager.yml` and the session secret key |
| `/path/to/traefik-manager/backups` | `/app/backups` | ✅ | Timestamped backups before every change |
| `/path/to/traefik/acme.json` | `/app/acme.json` | Optional | Enables the **Certs** tab |
| `/path/to/traefik/traefik.yml` | `/app/traefik.yml` | Optional | Enables the **Plugins** and **Static Config** tabs; mount read-write to allow editing |
| `/path/to/traefik/logs/access.log` | `/app/logs/access.log` | Optional | Enables the **Logs** tab |
| any `.yml` files | `/app/config/*.yml` | Optional | **Multi-config** - set `CONFIG_PATHS` or `CONFIG_DIR` |
