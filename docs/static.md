# Static Config Editor

The **Static Config** editor lets you view and edit Traefik's static configuration (`traefik.yml`) directly from the Traefik Manager UI. Access it via **Settings → Static Config**. Changes are staged and backed up before saving; a banner then prompts you to restart Traefik with one click, using whichever restart method you configure.

The editor is only visible when `STATIC_CONFIG_PATH` is set and the file exists.

---

## What is static config

Traefik's static configuration controls settings that cannot be changed at runtime via dynamic config:

- **Entrypoints** - ports, protocols, HTTP-to-HTTPS redirects
- **Certificate resolvers** - ACME email, storage path, DNS/HTTP challenge settings
- **Plugins** - `experimental.plugins` declarations
- **API / Dashboard** - expose the Traefik dashboard
- **Log level and access log** - log verbosity and access log path
- **Providers** - which providers Traefik polls

---

## Sections

| Section               | Description                                                                                                                                          |
| -----------------------| ------------------------------------------------------------------------------------------------------------------------------------------------------|
| Entrypoints           | Add, edit, and remove entrypoints - port, protocol, optional HTTP-to-HTTPS redirect, and the [Underscore Headers](hardening.md#header-alias-spoofing-underscore-headers) strategy (Traefik 3.6.20 / 3.7.6+). Edits merge into the existing entrypoint, preserving keys the form does not manage. |
| Certificate Resolvers | ACME email, storage path, DNS or HTTP challenge type and credentials                                                                                 |
| Plugins               | Install and remove experimental plugins; view installed plugins                                                                                      |
| API                   | Enable or disable the Traefik API and Dashboard, insecure mode, and debug mode                                                                       |
| Logging               | Set the log level (DEBUG / INFO / WARN / ERROR) and toggle access logging with an optional file path                                                 |
| Providers             | Enable and configure Docker and File providers via dedicated toggles; add other provider types via the **+ Provider** button which opens a template editor |
| Advanced              | Full raw YAML editor (Monaco) - for anything not covered by the form sections                                                                        |

::: warning API section
Disabling the Traefik API from the API section will prevent Traefik Manager from reading routes, services, and middleware. Keep it enabled while using TM.
:::

### Adding providers

Docker and File providers have dedicated toggle cards with form fields (endpoint, directory, watch). For all other providers, click **+ Provider** to open the template editor:

1. Select the provider type from the dropdown
2. A Monaco YAML editor appears pre-filled with a working template for that provider
3. Edit the values as needed
4. Click **Add Provider**

Supported provider types: Docker Swarm, HTTP, Kubernetes CRD, Kubernetes Ingress, Kubernetes Gateway, HashiCorp Nomad, AWS ECS, Consul Catalog, Consul KV, Redis KV, etcd KV, ZooKeeper KV.

Clicking the edit button on an existing provider opens the same editor with its current configuration loaded.

### Pending changes and saving

1. Edit any value in any section - a yellow **Pending changes** banner appears.
2. Click **Apply** - TM validates the YAML, backs up the current file, then writes the new one.
3. The banner changes to **Restart required to apply changes** with a **Restart** button.
4. Click **Restart** - TM triggers the configured restart method. A full-screen overlay shows while Traefik is down and dismisses automatically once it is back.

Multiple edits in one session only require a single restart.

---

## Trusted IPs helper

Behind a proxy such as Cloudflare, Traefik only believes `X-Forwarded-For` from sources listed in an entrypoint's `forwardedHeaders.trustedIPs`. Until those are set, your logs, CrowdSec, `ipAllowList` and the login limiter all see the proxy IP instead of the real client. The **Trusted IPs** button in the Static Config header opens a guided helper that writes that field for you.

1. Pick the target entrypoint (for example `websecure`). Any `trustedIPs` already configured are shown.
2. Choose one or more sources:
   - **Cloudflare edge ranges** - the full IPv4 + IPv6 set, hardcoded with a capture date. Nothing is fetched at runtime.
   - **Private ranges** - `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`, `fc00::/7`.
   - **Your own proxies / LAN** - free-form CIDRs or single IPs, one per line. Invalid entries are flagged and skipped.
3. Click **Preview change** to see exactly which ranges will be added. Existing entries are kept, and anything already trusted is deduplicated - the helper only ever adds.
4. Click **Apply & Save** to stage the change into the static config, back it up, and save. As with any static change, a **Restart required** banner then appears.

Because `trustedIPs` lives in the static config, this is global and needs a Traefik restart. Every trusted range can forge client IPs downstream, so only add proxies you control. Use the [Client IP Diagnostic](hardening.md) to confirm what actually reaches the app before and after. The helper works for the Host and for remote agents.

::: tip Refreshing the Cloudflare ranges
The hardcoded ranges live in `_CLOUDFLARE_IPS_V4` / `_CLOUDFLARE_IPS_V6` in `app.py`, sourced from [cloudflare.com/ips](https://www.cloudflare.com/ips/) (`/ips-v4` + `/ips-v6`). They are refreshed on release; replace both lists from that source and bump `_CLOUDFLARE_IPS_CAPTURED`.
:::

---

## Setup

### 1. Mount traefik.yml into TM

The static config file must be mounted into the Traefik Manager container **read-write** (no `:ro`).

:::tabs
== Docker / Podman
```yaml
services:
  traefik-manager:
    volumes:
      - /path/to/traefik/traefik.yml:/app/traefik.yml
    environment:
      - STATIC_CONFIG_PATH=/app/traefik.yml
```

== Linux (systemd)
```ini
Environment=STATIC_CONFIG_PATH=/etc/traefik/traefik.yml
```
On native Linux TM reads the file directly from the host path - no volume mount needed.
:::

### 2. Set the restart method

Set `RESTART_METHOD` to one of: `proxy`, `socket`, or `poison-pill`.

:::tabs
== Docker / Podman
```yaml
environment:
  - RESTART_METHOD=proxy
  - TRAEFIK_CONTAINER=traefik
```

== Linux (systemd)
```ini
Environment=RESTART_METHOD=poison-pill
Environment=TRAEFIK_CONTAINER=traefik
```
:::

### 3. Configure the restart method

See below for the compose additions required by each method.

---

## Restart methods

### Socket proxy (recommended)

Runs a `tecnativa/docker-socket-proxy` sidecar. TM connects to the proxy, which only exposes container restart - TM never sees the full Docker socket.

```yaml
services:
  traefik-manager:
    environment:
      - STATIC_CONFIG_PATH=/app/traefik.yml
      - RESTART_METHOD=proxy
      - TRAEFIK_CONTAINER=traefik
      - DOCKER_HOST=tcp://socket-proxy:2375
    networks:
      - traefik-net
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

**Pros:** Minimal socket exposure, no changes to Traefik's compose.
**Cons:** One extra container.

---

### Poison pill (no socket, no extra container)

TM writes a signal file to a shared Docker volume. Traefik's healthcheck detects it and sends `SIGTERM` to itself. Docker's restart policy brings it back within seconds.

Add the healthcheck and volume to your **Traefik** service:

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
      # ... your other volumes

  traefik-manager:
    environment:
      - STATIC_CONFIG_PATH=/app/traefik.yml
      - RESTART_METHOD=poison-pill
      - SIGNAL_FILE_PATH=/signals/restart.sig
    volumes:
      - tm-signals:/signals
      # ... your other volumes

volumes:
  tm-signals:
```

**Pros:** No Docker socket needed at all, no extra container.
**Cons:** Requires adding a healthcheck to Traefik's compose. Up to 5s delay before the signal is detected.

---

### Direct socket (advanced)

Mount `/var/run/docker.sock` directly into TM. Simplest setup but full Docker daemon access.

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
The full Docker socket gives TM the ability to start, stop, or delete any container on the host. If TM is ever compromised, the blast radius is the entire Docker daemon. Use the socket proxy method instead unless you have a specific reason to avoid the extra container.
:::

---

## Using the traefik-stack installer

If you installed with [setup.sh](traefik-stack.md), the static config editor is optional during install. When you answer **y** to "Mount Traefik static config?", the script asks which restart method you want and generates all the required compose additions automatically - volume mounts, env vars, socket proxy service, or Traefik healthcheck depending on your choice.

For existing installs, see [Enable static config editor](static-enable.md).

---

## Environment variable reference

| Variable | Default | Description |
|----------|---------|-------------|
| `STATIC_CONFIG_PATH` | `/app/traefik.yml` | Path to `traefik.yml` inside TM's container (or host path for native) |
| `RESTART_METHOD` | _(unset)_ | `proxy`, `socket`, or `poison-pill` |
| `TRAEFIK_CONTAINER` | `traefik` | Container name to restart (used by `proxy` and `socket` methods) |
| `DOCKER_HOST` | _(unset)_ | Docker socket URL - set to `tcp://socket-proxy:2375` for the proxy method |
| `SIGNAL_FILE_PATH` | `/signals/restart.sig` | Path to the signal file (poison pill method only) |

Full reference: [Environment Variables](env-vars.md).
