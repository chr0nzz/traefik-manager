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

Open **http://your-server:5000** — the setup wizard will guide you through the rest.

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
| `/path/to/traefik/dynamic.yml` | `/app/config/dynamic.yml` | ✅ | Traefik dynamic config — read and written by Traefik Manager |
| `/path/to/traefik-manager/config` | `/app/config` | ✅ | Persists `manager.yml` and the session secret key |
| `/path/to/traefik-manager/backups` | `/app/backups` | ✅ | Timestamped backups of `dynamic.yml` before every change |
| `/path/to/traefik/acme.json` | `/app/acme.json` | Optional | Enables the **Certs** tab |
| `/path/to/traefik/traefik.yml` | `/app/traefik.yml` | Optional | Enables the **Plugins** tab |
| `/path/to/traefik/logs/access.log` | `/app/logs/access.log` | Optional | Enables the **Logs** tab |
