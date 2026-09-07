# Overview

A self-hosted web UI for managing and monitoring your [Traefik](https://traefik.io/) reverse proxy - add routes, manage middlewares, view TLS certificates, and inspect live traffic, all without editing YAML by hand.

---

## Get Started

One command installs the `tm` CLI and runs `tm install`, which sets up Traefik and Traefik Manager together, Traefik Manager on its own, or the agent on a remote host.

```bash
curl -fsSL https://get-traefik.xyzlab.dev | bash
```

`tm` then manages the install: `tm status`, `tm update`, `tm reconfigure`, `tm doctor`.

[What the installer sets up →](tm-cli.md)

### Install it yourself

<div class="vp-pick">
<a class="vp-pick-card" href="./docker">
  <img src="/images/i-docker.png" alt="" width="28" height="28">
  <strong>Docker</strong>
  <span>You already run containers. Compose file, image on GHCR.</span>
</a>
<a class="vp-pick-card" href="./podman">
  <img src="/images/i-podman.png" alt="" width="28" height="28">
  <strong>Podman</strong>
  <span>You want rootless. Quadlet units and SELinux labels covered.</span>
</a>
<a class="vp-pick-card" href="./linux">
  <img src="/images/i-linux.png" alt="" width="28" height="28">
  <strong>Linux</strong>
  <span>No container runtime. Python and a systemd service on the host.</span>
</a>
<a class="vp-pick-card" href="./unraid">
  <img src="/images/i-unraid.png" alt="" width="28" height="28">
  <strong>Unraid</strong>
  <span>Install from the Community Applications template.</span>
</a>
</div>

---

## Management

Always visible. These tabs read and write your Traefik dynamic config.

| Tab | Description |
|-----|-------------|
| [Routes](tab-routes.md) | Create, edit, delete, and enable/disable HTTP, TCP, and UDP routes |
| [Middlewares](tab-middlewares.md) | Create and manage middlewares with built-in templates |
| [Services](tab-services.md) | View services from every provider; create and edit the ones in your config files |

**Multiple config files** - mount several dynamic config files with `CONFIG_DIR` or `CONFIG_PATHS`. A dropdown in the route and middleware forms picks the file each entry is written to. See [Environment Variables](env-vars.md).

---

## Navigation and layout

Tabs live in the left side nav, grouped Traffic, Observability, Infrastructure and Providers. Settings opens from its foot, or with **Shift** + **P**.

Layout is set under **Settings - Interface - Layout**, instance-wide.

| Layout | Content | Detail panel |
|--------|---------|--------------|
| **Fluid** (default) | Fills the screen | Pushes the page |
| **Fixed** | Capped width | Slides over |

---

## Stat panel

Above the content on the Dashboard, Routes, Middlewares and Services tabs sits a panel that answers one question: is anything wrong right now.

A verdict line sums up every problem in plain language and names the providers responsible. Four cards - HTTP routers, TCP/UDP routers, services and middlewares - each show a total, a strip with one cell per object worst-first, and counts you can click to jump straight to the broken ones. A provider strip scopes all four cards to one provider in a click. Below them, entry points list their protocol, flags, address and bound router count, over a runtime footer with the Traefik version, uptime and whether metrics, access logs and tracing are on.

Colour is rationed: a healthy install is almost monochrome, so anything coloured is worth reading.

The HTTP routers card also counts routes whose backend the background reachability check found down, as **unreachable**, alongside what Traefik itself reports. Click the count to filter the Routes tab to them.

Choose which of the four tabs show it under **Settings - Interface - Show on**, and switch to a denser layout with **Compact stat cards**. The [Logs](tab-logs.md) and [CrowdSec](tab-crowdsec.md) analytics panels use the same visual language.

---

## Static Config Editor

Edit your Traefik static config (`traefik.yml`) from the UI - no SSH needed. Changes are staged until you save, every save is backed up first, and a one-click restart applies them via your configured restart method.

**What you can manage:**
- Entrypoints - ports, redirects, trusted IPs, PROXY protocol, TLS defaults, middleware chains, timeouts
- Certificate resolvers - ACME challenges, custom CA, key type, EAB, DNS propagation
- Providers - Docker and File toggles, other providers via templates, throttle duration
- Plugins (remote and local), API and dashboard, logging with rotation and access-log filters
- Observability (ping, Prometheus, OTLP tracing) and system options (servers transport, rule syntax)
- Raw YAML editor (Monaco/VS Code engine) for anything else

Works identically for [remote agents](agent.md#static-config-editing) - the sections read and write the active agent's own `traefik.yml`.

**Setup required:**

| Requirement | Details |
|-------------|---------|
| Mount `traefik.yml` read-write | `-v /path/to/traefik.yml:/app/traefik.yml` (no `:ro`) |
| Set `STATIC_CONFIG_PATH` | Path inside the container, e.g. `/app/traefik.yml`. No default. Also settable under **Settings - System Monitoring - File Paths** |
| Set `RESTART_METHOD` | How TM restarts Traefik after a config change - `proxy` (default), `poison-pill` or `socket` |

Once the file is readable, **Settings - Interface - Tabs** places the editor: **Off**, inside **Settings**, or as its own **Tab**.

See [Static Config Editor](static.md) for each restart method.

---

## Multi-Server

Manage remote Traefik instances from one UI through [TMA](agent.md), a small Go agent that runs next to Traefik on each server. A switcher at the top of the side nav changes the active server, and every tab - routes, middlewares, services, backups, logs - then works against it. No VPN or SSH required.

Adding an agent offers two paths: a one-line `tm` CLI install command to run on the remote server, or a ready-to-paste Docker Compose or Docker Run command to deploy yourself. The API key is shown once and stored encrypted.

---

## Backups

Every change writes a timestamped backup first, and any of them can be restored in one click. Retention is configurable.

[Git backup](git-backup.md) additionally pushes your config to GitHub, Gitea, Forgejo, GitLab or any HTTPS remote, with commit history, side-by-side diffs and one-click restore of any commit. Agents can push to the Host's repository on their own branch, one branch per server, so a single repository covers every server.

---

## Visualizations

Optional tabs, no extra mounts needed. Dashboard, Route Map and TLS Options toggle on in **Settings - Interface - Tabs**; CrowdSec in **Settings - System Monitoring - Tab Visibility**. The setup wizard can turn on Dashboard and Route Map; TLS Options and CrowdSec are Settings only.

| Tab                           | Description                                                                    |
| -------------------------------| --------------------------------------------------------------------------------|
| [Dashboard](tab-dashboard.md) | Routes grouped by category with app icons, custom groups, per-card editing, and one-click app launching |
| [Route Map](tab-routemap.md)  | Topology connection map - entry points → routes → middlewares → services       |
| [TLS Options](tab-tls-options.md) | Named `tls.options` profiles - min/max version, ciphers, mTLS - assignable per route |
| [CrowdSec](tab-crowdsec.md)   | Who is attacking, from where, how and what they went after, from a CrowdSec LAPI; ban, captcha, bypass or unban with one click |

---

## Monitoring

Optional tabs - each requires a file mounted into the container.

| Tab | Mount required | Description |
|-----|----------------|-------------|
| [Certificates](tab-certs.md) | `acme.json:/app/acme.json:ro` | TLS certificates with expiry tracking. `ACME_JSON_PATH` accepts several files or a directory, for setups with one resolver per storage file |
| [Plugins](tab-plugins.md) | `traefik.yml:/app/traefik.yml` plus `STATIC_CONFIG_PATH=/app/traefik.yml` (no default) | Plugins from your static config with the middlewares using each one, plus a guided install. Versions are checked against the catalog daily and flagged when one is out of date. Add `:ro` to keep the tab read-only |
| [Logs](tab-logs.md) | `access.log:/app/logs/access.log:ro` | Access log analytics: status, latency, paths, clients and services as clickable cards over a live tail, with optional auto refresh and a [world map](geoip.md) |

---

## Providers

Read-only tabs that pull live data from the Traefik API - no extra mounts, just a working API connection. Each lists that provider's routers and its middlewares.

### Orchestrators

| Tab | Provider |
|-----|----------|
| [Docker](tab-docker.md) | `docker` |
| [Kubernetes](tab-kubernetes.md) | `kubernetesCRD` / `kubernetesIngress` / `kubernetesGateway` |
| [Swarm](tab-swarm.md) | `swarm` |
| [Nomad](tab-nomad.md) | `nomad` |
| [ECS](tab-ecs.md) | `ecs` |
| [Consul Catalog](tab-consulcatalog.md) | `consulCatalog` |

### Key-Value Stores

| Tab | Provider |
|-----|----------|
| [Redis](tab-redis.md) | `redis` |
| [etcd](tab-etcd.md) | `etcd` |
| [Consul KV](tab-consul.md) | `consul` |
| [ZooKeeper](tab-zookeeper.md) | `zooKeeper` |

### Config-based

| Tab | Provider |
|-----|----------|
| [HTTP Provider](tab-http_provider.md) | `http` |
| [File (external)](tab-file_external.md) | `file` |

> Traefik Manager's own routes are automatically excluded from the File provider tab.

---

## Configuration

Settings open from the foot of the side nav. Each pane lists its settings as aligned rows carrying the setting name, what it does and its control.

The search box above the panes filters every pane at once by name and description: matches elsewhere show as a count beside that pane in the sidebar, so you can find a setting without knowing where it lives.

A verdict line above the search flags anything that needs attention, such as no authentication being active.

| Page                                   | Description                                                                                   |
| ----------------------------------------| -----------------------------------------------------------------------------------------------|
| [manager.yml](manager-yml.md)          | Full settings file reference - all keys, types, and defaults                                  |
| [Environment Variables](env-vars.md)   | All supported environment variables with override behaviour                                   |
| [OIDC / SSO Login](oidc.md)            | OpenID Connect as an additional login method alongside the built-in password                  |
| [Notification Webhooks](webhooks.md)   | Forward events to Discord, Slack, ntfy or any JSON endpoint                                   |
| [Git Repository Backup](git-backup.md) | Auto-push, commit history, diff viewer and one-click restore                                  |

---

## Operations

| Page | Description |
|------|-------------|
| [Reset Password](reset-password.md) | Set a chosen password or a temporary one, TOTP recovery, and manual reset via manager.yml |
| [Security](security.md) | Security controls, API keys, sessions, and hardening recommendations |
| [Traefik Hardening](hardening.md) | CVE advisories, header aliases, forwardAuth limits, and real client IPs |
| [Development](development.md) | Project layout, running the test suite, and what a pull request needs |

---

## Self Route

Put Traefik Manager itself behind Traefik so you can reach it on a domain with HTTPS.

Go to **Settings - Connection - Self Route**. The URL pre-fills from your current hostname; the service URL and entry point are detected from your existing config. Click **Save Route** and TM writes the router and service entries into your dynamic config file. No changes to `traefik.yml` needed.

---

## Traefik provider config snippets

Minimal additions to your `traefik.yml` to enable each provider tab.

:::tabs
== Docker
```yaml
providers:
  docker:
    exposedByDefault: false
```

== Swarm
```yaml
providers:
  swarm:
    exposedByDefault: false
```

== Kubernetes
```yaml
providers:
  kubernetesCRD: {}
  kubernetesIngress: {}
```

== Nomad
```yaml
providers:
  nomad:
    endpoint:
      address: "http://nomad:4646"
```

== ECS
```yaml
providers:
  ecs:
    region: us-east-1
    clusters:
      - my-cluster
```

== Consul Catalog
```yaml
providers:
  consulCatalog:
    endpoint:
      address: "consul:8500"
    exposedByDefault: false
```

== Redis
```yaml
providers:
  redis:
    endpoints:
      - "redis:6379"
```

== etcd
```yaml
providers:
  etcd:
    endpoints:
      - "etcd:2379"
```

== Consul KV
```yaml
providers:
  consul:
    endpoints:
      - "consul:8500"
```

== ZooKeeper
```yaml
providers:
  zooKeeper:
    endpoints:
      - "zookeeper:2181"
```

== HTTP Provider
```yaml
providers:
  http:
    endpoint: "https://config.example.com/traefik"
    pollInterval: "30s"
```

== File (external)
```yaml
providers:
  file:
    directory: /etc/traefik/dynamic/
    watch: true
```

== Logs tab
```yaml
accessLog:
  filePath: "/logs/access.log"
  format: common
```
:::

---

## Mobile App

A companion Android app. See the [requirements table](mobile.md#requirements) for which server version each app release needs.

Connect it with an API key: go to **Settings - Authentication - API Keys**, click **Add Key**, enter a device name, and copy the generated key. Each device gets its own key, so one can be revoked without affecting the others.

<div class="vp-grid-cards">
<div class="vp-card">

**<img src="/images/icon.png" style="height:24px;width:24px;vertical-align:middle;display:inline-block"> Traefik Manager Mobile**

Browse routes, middlewares, and services. Enable/disable routes. Add and edit with built-in templates. Follows system light/dark theme.

<MobileRelease /> [Mobile docs →](mobile.md)

</div>
</div>

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11 · Flask 3.1 · Gunicorn |
| Agent | Go 1.25 · Alpine Linux (TMA - remote agent daemon) |
| Config | ruamel.yaml (preserves comments and Go templates) |
| Auth | bcrypt · pyotp (TOTP) · Flask sessions · CSRF · Flask-Limiter · Fernet |
| Frontend | Vanilla JS · Tailwind CSS 3.4 · Phosphor Icons |
| Editor | Monaco Editor 0.52 (VS Code engine) |
| Route Map | dagre 3.1 (graph layout) |
| Geolocation | maxminddb · DB-IP Lite (local lookups, no external calls) |
| Tests | pytest · ruff · `go test` - run on every pull request |
| Container | Docker · Alpine Linux · all JS/CSS bundled at build time (no CDN at runtime) |
