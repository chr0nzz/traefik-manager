# Static Config Editor

Static Config lets you view and edit Traefik's static configuration (`traefik.yml`) from the Traefik Manager UI. Changes are staged and backed up before saving; a banner then prompts you to restart Traefik with one click, using whichever restart method you configure.

It is off by default. Once a static config path is set and the file exists, a **Static Config** row appears under **Settings → Interface → Tabs** with three placements:

| Placement | Where it appears |
|---|---|
| Off | Nowhere. |
| Settings | As a **Static Config** panel in the Settings sidebar. |
| Tab | As its own tab in the side navigation. |

The path comes from the `static_config_path` field in `manager.yml` (**Settings → System Monitoring → File Paths**) if set, otherwise from the `STATIC_CONFIG_PATH` environment variable. A path set in Settings must be an existing `.yml`, `.yaml` or `.toml` file outside Traefik Manager's own files ([rules](manager-yml.md#file-paths)).

Everything here also works for [remote agents](agent.md#static-config-editing): with an agent selected in the server switcher, the same section editors read and write the agent's own `traefik.yml`, with the agent's backup and restart flow.

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
| Entrypoints           | Port, protocol, optional HTTP-to-HTTPS redirect, the [Alias Headers](hardening.md#header-alias-spoofing) strategy (Traefik 3.7.12+, or Underscore Headers on 3.7.6 to 3.7.11), trusted IPs for forwarded headers (`forwardedHeaders.trustedIPs` / `insecure`, one CIDR per line), PROXY protocol trust (`proxyProtocol.trustedIPs` / `insecure`), an entrypoint-wide middleware chain (`http.middlewares`), TLS-by-default (`http.tls` with cert resolver and TLS options), `asDefault`, and responding timeouts (read / write / idle). |
| Certificate Resolvers | ACME email, storage path, DNS / HTTP / TLS challenge type, custom CA server, key type, external account binding (EAB), and DNS propagation controls (check resolvers, delay, disable checks). |
| Plugins               | Remote plugins (module + version) and local plugins from the `plugins-local` directory. The [Plugins tab](tab-plugins.md) offers the richer install flow. |
| API                   | Enable or disable the Traefik API and Dashboard, insecure mode, and debug mode. |
| Logging               | Traefik log: level, text/JSON format, optional log file with rotation (max size, backups, age, compression). Access log: file path, CLF/JSON format, buffering, status-code and min-duration filters, retry-only mode, and header keep/redact. |
| Observability         | Ping health endpoint, Prometheus metrics with entrypoint / router / service label toggles, and OTLP tracing (service name, sample rate, collector endpoint). Other metrics backends configured in YAML are left untouched. |
| System                | Traefik version check, anonymous usage statistics, the default rule syntax (v3 / v2 compatibility), and servers transport defaults - backend TLS verification skip, root CAs, max idle connections, forwarding timeouts. |
| Providers             | Docker and File providers via dedicated toggles, the providers throttle duration, and other provider types via the **+ Provider** button. |

Edits merge into the existing entry, so keys the forms do not manage survive a save.

Anything the sections do not cover is reachable through the **raw YAML editor** - the code button in the toolbar opens `traefik.yml` in Monaco. Section edits and raw edits share the same staged buffer, so they never overwrite each other.

::: warning API section
Disabling the Traefik API will prevent Traefik Manager from reading routes, services, and middleware. Keep it enabled while using TM.
:::

### Adding providers

Docker and File have dedicated toggle cards with form fields (endpoint, directory, watch). For all other providers, click **+ Provider**:

1. Select the provider type from the dropdown
2. A Monaco YAML editor appears pre-filled with a working template for that provider
3. Edit the values as needed
4. Click **Add Provider**

Supported types: Docker Swarm, HTTP, Kubernetes (CRD), Kubernetes Ingress, Kubernetes Gateway, HashiCorp Nomad, AWS ECS, Consul Catalog, Consul KV, Redis KV, etcd KV, ZooKeeper KV.

The edit button on an existing provider opens the same editor with its current configuration loaded.

### Pending changes and saving

1. Edit any value - an **Unsaved changes** bar appears; nothing is written to `traefik.yml` until you save.
2. Click **Save** - TM validates the YAML, backs up the current file, then writes the new one. **Discard** reloads from disk instead.
3. The bar changes to **Saved. Traefik is still running the previous config.** with a **Restart Traefik** button.
4. Click it - TM triggers the configured restart method. A full-screen overlay shows while Traefik restarts and dismisses once it is back (for agents, once the agent is reachable again).

Multiple edits in one session need only a single restart.

---

## Trusted IPs helper

Behind a proxy such as Cloudflare, Traefik only believes `X-Forwarded-For` from sources listed in an entrypoint's `forwardedHeaders.trustedIPs`. Until those are set, your logs, CrowdSec, `ipAllowList` and the login limiter all see the proxy IP instead of the real client. The shield button in the Static Config toolbar opens a guided helper that writes that field for you.

1. Pick the target entrypoint (for example `websecure`). Any `trustedIPs` already configured are shown.
2. Choose one or more sources:
   - **Cloudflare edge ranges** - the full IPv4 + IPv6 set, hardcoded with a capture date. Nothing is fetched at runtime.
   - **Private ranges** - `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`, `fc00::/7`.
   - **Your own proxies / LAN** - free-form CIDRs or single IPs, one per line. Invalid entries are flagged and skipped.
3. Click **Preview change** to see which ranges will be added. Existing entries are kept and duplicates are dropped - the helper only ever adds.
4. Click **Apply & Save** to stage the change, back up the file, and save. A **Restart required** banner then appears.

Because `trustedIPs` lives in the static config, this is global and needs a Traefik restart. Every trusted range can forge client IPs downstream, so only add proxies you control. Use the [Client IP Diagnostic](tab-logs.md) to confirm what actually reaches the app before and after. The helper works for the Host and for remote agents.

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

Set `RESTART_METHOD` to `proxy`, `socket`, or `poison-pill`.

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
Environment=SIGNAL_FILE_PATH=/var/lib/traefik-manager/signals/restart.sig
```
Point the signal file at a directory the service user can write to. `TRAEFIK_CONTAINER` is only used by `proxy` and `socket`.
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

**Pros:** No Docker socket at all, no extra container.
**Cons:** Requires a healthcheck on Traefik. Up to 5s delay before the signal is detected.

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
The full Docker socket lets TM start, stop, or delete any container on the host. If TM is ever compromised, the blast radius is the entire Docker daemon. Use the socket proxy method instead unless you have a specific reason to avoid the extra container.
:::

---

## Using the tm CLI installer {#using-the-traefik-stack-installer}

If you installed with [the tm CLI installer](tm-cli.md), answering **y** to "Mount Traefik static config?" asks which restart method you want and generates every required compose addition - volume mounts, env vars, socket proxy service, or Traefik healthcheck.

To turn it on or change the restart method afterwards, run `tm reconfigure --section mounts`.

`tm doctor` checks the wiring: that the signals volume is mounted on both sides and the poison pill healthcheck is present, or that `traefik-restart.path` is active on systemd. Run it first when the Restart button does nothing.

For existing installs set up by hand, see [Enable static config editor](static-enable.md).

---

## Environment variable reference

| Variable | Default | Description |
|----------|---------|-------------|
| `STATIC_CONFIG_PATH` | _(unset)_ | Path to `traefik.yml` inside TM's container (or host path for native). The editor stays hidden until this or `static_config_path` in Settings is set. |
| `RESTART_METHOD` | `proxy` | `proxy`, `socket`, or `poison-pill` |
| `TRAEFIK_CONTAINER` | `traefik` | Container name to restart (`proxy` and `socket` only) |
| `DOCKER_HOST` | _(unset - uses `/var/run/docker.sock`)_ | Docker socket URL - set to `tcp://socket-proxy:2375` for the proxy method |
| `SIGNAL_FILE_PATH` | `/signals/restart.sig` | Path to the signal file (`poison-pill` only) |

Full reference: [Environment Variables](env-vars.md).
