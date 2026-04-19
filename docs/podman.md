# Running with Podman

Traefik Manager works with Podman. This page covers the key differences from Docker and shows the common deployment patterns.

---

## Key differences from Docker

|                     | Docker                   | Podman                                                                          |
| ---------------------| --------------------------| ---------------------------------------------------------------------------------|
| Compose command     | `docker compose`         | `podman compose` (Podman 4.7+) or `podman-compose`                              |
| Exec into container | `docker exec`            | `podman exec`                                                                   |
| SELinux hosts       | No label needed          | Add `:z` (shared) or `:Z` (private) to volume mounts                            |
| Rootless ports      | Ports < 1024 need root   | Same - use port ≥ 1024 or configure `net.ipv4.ip_unprivileged_port_start`       |
| Restart policy      | `unless-stopped`         | Use `always` with podman-compose, or use a Quadlet unit for systemd integration |
| Network aliases     | Docker Compose sets them | Must create a named network and join both containers to it                      |

---

## podman compose

Podman 4.7+ ships `podman compose` as a built-in subcommand. For older versions install `podman-compose`:

```bash
pip install podman-compose
```

### Minimal compose file

```yaml
services:
  traefik-manager:
    image: ghcr.io/chr0nzz/traefik-manager:latest
    container_name: traefik-manager
    restart: always
    ports:
      - "5000:5000"
    environment:
      - COOKIE_SECURE=false
    volumes:
      - /path/to/traefik/dynamic.yml:/app/config/dynamic.yml:z
      - /path/to/traefik-manager/config:/app/config:z
      - /path/to/traefik-manager/backups:/app/backups:z
```

> The `:z` label tells the container runtime to relabel the volume for SELinux. Use `:Z` if you want the label to be private to this container. On non-SELinux hosts (most Debian/Ubuntu setups) these labels are harmless and can be omitted.

Start:

```bash
podman compose up -d
```

---

## Connecting to Traefik on the same host 

Traefik Manager needs to reach the Traefik API URL you configure in settings (e.g. `http://traefik:8080`). When both containers run on the same Podman network they can reach each other by container name.

### Create a shared network

```bash
podman network create traefik
```

### Join both containers to it

In your compose file, add a `networks` block:

```yaml
services:
  traefik-manager:
    image: ghcr.io/chr0nzz/traefik-manager:latest
    container_name: traefik-manager
    restart: always
    ports:
      - "5000:5000"
    environment:
      - COOKIE_SECURE=false
    volumes:
      - /path/to/traefik/dynamic.yml:/app/config/dynamic.yml:z
      - /path/to/traefik-manager/config:/app/config:z
      - /path/to/traefik-manager/backups:/app/backups:z
    networks:
      - traefik

networks:
  traefik:
    external: true
```

Then in the setup wizard, set the Traefik API URL to `http://traefik:8080`.

---

## Rootless Podman

Rootless Podman runs containers as your regular user with no daemon. No extra config is needed for Traefik Manager - just run the compose commands as your regular user.

```bash
# Start
podman compose up -d

# Check logs for the auto-generated password on first run
podman logs traefik-manager | grep -A3 "AUTO-GENERATED"
```

If you're running rootless and need a port below 1024, either:
- Map to a high port: `-p 8080:5000` and use a reverse proxy in front
- Lower the unprivileged port start: `sysctl -w net.ipv4.ip_unprivileged_port_start=80`

---

## Systemd integration with Quadlet

Quadlet is the recommended way to run Podman containers as systemd services. It replaces `podman generate systemd`.

Create `/etc/containers/systemd/traefik-manager.container` (system) or `~/.config/containers/systemd/traefik-manager.container` (rootless):

```ini
[Unit]
Description=Traefik Manager
After=network-online.target

[Container]
Image=ghcr.io/chr0nzz/traefik-manager:latest
ContainerName=traefik-manager
PublishPort=5000:5000
Environment=COOKIE_SECURE=false
Volume=/path/to/traefik/dynamic.yml:/app/config/dynamic.yml:z
Volume=/path/to/traefik-manager/config:/app/config:z
Volume=/path/to/traefik-manager/backups:/app/backups:z
Network=traefik.network

[Service]
Restart=always

[Install]
WantedBy=default.target
```

Reload and start:

```bash
systemctl --user daemon-reload
systemctl --user enable --now traefik-manager
```

For system-level (root) units, drop `--user` from the systemctl commands.

---

## Password reset

```bash
podman exec traefik-manager flask reset-password
```

This generates a new temporary password, prints it to the terminal, and requires you to change it on next login. Identical to the Docker workflow - just `podman exec` instead of `docker exec`.

---

## Optional monitoring mounts

Add `:z` to every optional volume mount on SELinux hosts:

```yaml
volumes:
  - /path/to/traefik/acme.json:/app/acme.json:ro,z
  - /path/to/traefik/traefik.yml:/app/traefik.yml:z          # read-write for Static Config editor
  - /path/to/traefik/logs/access.log:/app/logs/access.log:ro,z
```

> Mount `traefik.yml` without `:ro` if you want to use the Static Config editor. Read-only enables only the Plugins tab.

---

## Static config editor

The Static Config tab lets you edit `traefik.yml` directly from the UI. After saving, Traefik Manager can restart Traefik automatically.

### Requirements

Mount `traefik.yml` read-write (no `:ro`) and set `RESTART_METHOD`.

### Method 1: Poison pill (recommended for Podman)

Traefik Manager writes a signal file. A watcher sidecar monitors the file and restarts Traefik. No socket access needed for Traefik Manager.

```yaml
services:
  traefik-watcher:
    image: alpine:latest
    container_name: traefik-watcher
    restart: always
    entrypoint: >
      sh -c 'while true; do
        if [ -f /signals/restart.sig ]; then
          podman restart traefik && rm /signals/restart.sig;
        fi;
        sleep 2;
      done'
    volumes:
      - traefik-signals:/signals:z

  traefik-manager:
    image: ghcr.io/chr0nzz/traefik-manager:latest
    container_name: traefik-manager
    restart: always
    ports:
      - "5000:5000"
    environment:
      - COOKIE_SECURE=false
      - RESTART_METHOD=poison-pill
      - SIGNAL_FILE_PATH=/signals/restart.sig
    volumes:
      - /path/to/traefik/dynamic.yml:/app/config/dynamic.yml:z
      - /path/to/traefik-manager/config:/app/config:z
      - /path/to/traefik-manager/backups:/app/backups:z
      - /path/to/traefik/traefik.yml:/app/traefik.yml:z
      - traefik-signals:/signals:z

volumes:
  traefik-signals:
```

### Method 2: Direct socket

Mount the Podman socket directly. The socket path depends on whether Podman runs as root or rootless.

```yaml
services:
  traefik-manager:
    image: ghcr.io/chr0nzz/traefik-manager:latest
    container_name: traefik-manager
    restart: always
    ports:
      - "5000:5000"
    environment:
      - COOKIE_SECURE=false
      - RESTART_METHOD=socket
      - TRAEFIK_CONTAINER=traefik
    volumes:
      - /path/to/traefik/dynamic.yml:/app/config/dynamic.yml:z
      - /path/to/traefik-manager/config:/app/config:z
      - /path/to/traefik-manager/backups:/app/backups:z
      - /path/to/traefik/traefik.yml:/app/traefik.yml:z
      # Root Podman:
      - /run/podman/podman.sock:/var/run/docker.sock:ro
      # Rootless Podman (replace 1000 with your UID):
      # - /run/user/1000/podman/podman.sock:/var/run/docker.sock:ro
```

### Environment variables

| Variable | Values | Default | Description |
|---|---|---|---|
| `RESTART_METHOD` | `proxy`, `socket`, `poison-pill` | `proxy` | How to restart Traefik after a static config change |
| `TRAEFIK_CONTAINER` | container name | `traefik` | Name of the Traefik container to restart |
| `SIGNAL_FILE_PATH` | path | `/signals/restart.sig` | Signal file path for the `poison-pill` method |

---

## Config file setup

### Single config file (default)

The default setup. Mount one dynamic config file and set `CONFIG_PATH` to point at it:

```yaml
environment:
  - CONFIG_PATH=/app/config/dynamic.yml
volumes:
  - /path/to/traefik/dynamic.yml:/app/config/dynamic.yml:z
  - /path/to/traefik-manager/config:/app/config:z
  - /path/to/traefik-manager/backups:/app/backups:z
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
  - /path/to/traefik-manager/config:/app/config:z
  - /path/to/traefik/routes.yml:/app/config/routes.yml:z
  - /path/to/traefik/services.yml:/app/config/services.yml:z
  - /path/to/traefik-manager/backups:/app/backups:z
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
  - /path/to/traefik-manager/config:/app/config:z
  - /path/to/traefik/config:/app/config/traefik:z
  - /path/to/traefik-manager/backups:/app/backups:z
```
:::

**Quadlet units:** set the environment variable in the `[Container]` section:

```ini
# Single config file (default):
# Environment=CONFIG_PATH=/app/config/dynamic.yml
# Multiple config files:
Environment=CONFIG_PATHS=/app/config/routes.yml,/app/config/services.yml
```

See the [Environment Variables](env-vars.md) reference for the full priority order.

---

## Behind Traefik (expose via subdomain)

Works the same as with Docker. Remove `ports`, add labels, and make sure both containers share the same Podman network:

```yaml
services:
  traefik-manager:
    image: ghcr.io/chr0nzz/traefik-manager:latest
    container_name: traefik-manager
    restart: always
    environment:
      - COOKIE_SECURE=true
    volumes:
      - /path/to/traefik/dynamic.yml:/app/config/dynamic.yml:z
      - /path/to/traefik-manager/config:/app/config:z
      - /path/to/traefik-manager/backups:/app/backups:z
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
