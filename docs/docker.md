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
  - /path/to/traefik/traefik.yml:/app/traefik.yml:ro       # Plugins tab
  - /path/to/traefik/logs/access.log:/app/logs/access.log:ro  # Logs tab
```

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
      - /path/to/traefik/traefik.yml:/app/traefik.yml:ro
      - /path/to/traefik/logs/access.log:/app/logs/access.log:ro
```

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

=== "CONFIG_PATHS (explicit list)"
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

=== "CONFIG_DIR (auto-discover from directory)"
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
| `/path/to/traefik/traefik.yml` | `/app/traefik.yml` | Optional | Enables the **Plugins** tab |
| `/path/to/traefik/logs/access.log` | `/app/logs/access.log` | Optional | Enables the **Logs** tab |
| any `.yml` files | `/app/config/*.yml` | Optional | **Multi-config** - set `CONFIG_PATHS` or `CONFIG_DIR` |
