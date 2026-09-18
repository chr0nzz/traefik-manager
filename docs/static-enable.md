# Enable Static Config Editor

How to enable the static config editor for an existing Traefik Manager install without re-running the setup script.

**Prerequisites:** the path to your `traefik.yml` on the host, and a choice of [restart method](static.md#restart-methods).

---

## Generate it

Paste your compose file, pick a restart method, give it the host path to `traefik.yml`, and copy the result. This does Steps 1 to 3 for you.

<ComposeUpgrader />

Then apply it:

```bash
docker compose pull
docker compose up -d
```

Prefer to do it by hand, or not using Compose? The steps below cover Docker, Podman and systemd.

---

## Step 1 - Mount traefik.yml into TM

Add the volume to your Traefik Manager service. The mount must be **read-write** (no `:ro`).

:::tabs
== Docker / Podman
```yaml
services:
  traefik-manager:
    volumes:
      - /path/to/traefik/traefik.yml:/app/traefik.yml
```

== Linux (systemd)
No volume mount needed - TM reads the file directly from the host path. Skip to Step 2.
:::

---

## Step 2 - Set env vars on TM

:::tabs
== Docker / Podman
```yaml
services:
  traefik-manager:
    environment:
      - STATIC_CONFIG_PATH=/app/traefik.yml
      - RESTART_METHOD=proxy        # proxy | socket | poison-pill
      - TRAEFIK_CONTAINER=traefik   # proxy and socket only
```

== Linux (systemd)
Edit `/etc/systemd/system/traefik-manager.service` and add to the `[Service]` block:
```ini
Environment=STATIC_CONFIG_PATH=/etc/traefik/traefik.yml
Environment=RESTART_METHOD=poison-pill
Environment=SIGNAL_FILE_PATH=/var/lib/traefik-manager/signals/restart.sig
```
Then reload: `sudo systemctl daemon-reload`
:::

---

## Step 3 - Configure your restart method

Pick one tab below and follow only that section.

:::tabs
== Socket proxy

Add the `socket-proxy` service and set `DOCKER_HOST` on TM. A `docker-compose.override.yml` keeps your main file untouched:

```yaml
# docker-compose.override.yml
services:
  traefik-manager:
    environment:
      - STATIC_CONFIG_PATH=/app/traefik.yml
      - RESTART_METHOD=proxy
      - TRAEFIK_CONTAINER=traefik
      - DOCKER_HOST=tcp://socket-proxy:2375
    networks:
      - socket-proxy-net

  socket-proxy:
    image: tecnativa/docker-socket-proxy
    restart: unless-stopped
    environment:
      CONTAINERS: 1
      POST: 1
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
    networks:
      - socket-proxy-net

networks:
  socket-proxy-net:
    internal: true
```

Docker Compose merges this with your existing `docker-compose.yml` on every `up`.

To undo: `rm docker-compose.override.yml && docker compose up -d`

== Poison pill

Add the healthcheck and shared volume to your **Traefik** service:

```yaml
services:
  traefik:
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "[ ! -f /signals/restart.sig ] || (rm /signals/restart.sig && kill -TERM 1)"]
      interval: 5s
      timeout: 3s
      retries: 1
    volumes:
      - tm-signals:/signals
      # ... your existing volumes

  traefik-manager:
    environment:
      - STATIC_CONFIG_PATH=/app/traefik.yml
      - RESTART_METHOD=poison-pill
      - SIGNAL_FILE_PATH=/signals/restart.sig
    volumes:
      - tm-signals:/signals
      # ... your existing volumes

volumes:
  tm-signals:
```

For **native Linux installs**, point the signal file at a directory the TM service user can write to:

```ini
Environment=RESTART_METHOD=poison-pill
Environment=SIGNAL_FILE_PATH=/var/lib/traefik-manager/signals/restart.sig
```

Then add the healthcheck to your Traefik Docker service (same YAML as above, pointing at the same path). If Traefik also runs as a systemd service, use a `.path` unit watching that file to `systemctl restart traefik` instead.

== Direct socket

Add the socket mount to TM:

```yaml
services:
  traefik-manager:
    environment:
      - STATIC_CONFIG_PATH=/app/traefik.yml
      - RESTART_METHOD=socket
      - TRAEFIK_CONTAINER=traefik
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
```

::: danger
The full Docker socket lets TM start, stop, or delete any container. Consider the socket proxy method instead.
:::
:::

---

## Step 4 - Apply

:::tabs
== Docker / Podman
```bash
docker compose up -d
```

Or to recreate only TM without restarting Traefik:
```bash
docker compose up -d --force-recreate traefik-manager
```

== Linux (systemd)
```bash
sudo systemctl restart traefik-manager
```
:::

---

## Verify

Open Traefik Manager - a **Static Config** row appears under **Settings → Interface → Tabs** with three choices:

| Choice | Where it appears |
|---|---|
| **Off** | Nowhere. |
| **Settings** | As a **Static Config** panel in the Settings sidebar. |
| **Tab** | As its own tab in the side navigation. |

If the row does not appear, check that a static config path is set - either `STATIC_CONFIG_PATH` or the field under **Settings → System Monitoring → File Paths**, which wins when both are present - and that the file exists at that path inside the container:

```bash
docker exec traefik-manager ls -la /app/traefik.yml
```

---

## Undo

Remove the volume mount, env vars, and any compose additions you added, then restart TM:

```bash
docker compose up -d --force-recreate traefik-manager
```

Static Config disappears. Your `traefik.yml` is unchanged.
