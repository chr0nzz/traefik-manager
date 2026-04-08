# Traefik Manager

A self-hosted web UI for managing and monitoring your [Traefik](https://traefik.io/) reverse proxy - add routes, manage middlewares, view TLS certificates, and inspect live traffic, all without editing YAML by hand.

---

## Get Started

<div class="vp-grid-cards">
<div class="vp-card">

**⚡ Traefik Stack**

One command installs Traefik + Traefik Manager together, or Traefik Manager on its own via Docker or a native Linux service.

[Traefik Stack guide →](traefik-stack.md)

</div>
<div class="vp-card">

**🐳 Docker**

Deploy with Docker Compose - minimal setup, pre-built image on GHCR.

[Docker guide →](docker.md)

</div>
<div class="vp-card">

**🦭 Podman**

Rootless containers, Quadlet/systemd, SELinux volume labels.

[Podman guide →](podman.md)

</div>
<div class="vp-card">

**🐧 Linux (native)**

Run directly on the host with Python + systemd. No container runtime needed.

[Linux guide →](linux.md)

</div>
<div class="vp-card">

**🟠 Unraid**

Install from the Community Applications store with a pre-built template.

[Unraid guide →](unraid.md)

</div>
</div>

---

## Management

These tabs are always visible. They let you read and write your Traefik dynamic config.

| Tab | Description |
|-----|-------------|
| [Routes](tab-routes.md) | Create, edit, delete, and enable/disable HTTP, TCP, and UDP routes |
| [Middlewares](tab-middlewares.md) | Create and manage middlewares with built-in templates |
| [Services](tab-services.md) | Read-only view of all services across every provider |

**Multiple config files** - mount several Traefik dynamic config files using `CONFIG_DIR` or `CONFIG_PATHS`. A dropdown in the route/middleware modals lets you choose which file each entry is saved to. See [Environment Variables](env-vars.md) for setup.

---

## Visualizations

Optional tabs - toggle on in **Settings - Interface - Tabs** or during the setup wizard. No extra mounts needed.

| Tab | Description |
|-----|-------------|
| [Dashboard](tab-dashboard.md) | Routes grouped by category with app icons, custom groups, and per-card editing |
| [Route Map](tab-routemap.md) | Topology connection map - entry points → routes → middlewares → services |

---

## Monitoring

Optional tabs - each requires a file mounted into the container.

| Tab | Mount required | Description |
|-----|----------------|-------------|
| [Certificates](tab-certs.md) | `acme.json:/app/acme.json:ro` | TLS certificates with expiry tracking |
| [Plugins](tab-plugins.md) | `traefik.yml:/app/traefik.yml:ro` | Plugins declared in your static config |
| [Logs](tab-logs.md) | `access.log:/app/logs/access.log:ro` | Live Traefik access log tail |

---

## Providers

Read-only tabs that pull live data from the Traefik API. No extra mounts needed - just a working API connection.

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

| Page | Description |
|------|-------------|
| [manager.yml](manager-yml.md) | Full settings file reference - all keys, types, and defaults |
| [Environment Variables](env-vars.md) | All supported environment variables with override behaviour |

---

## Operations

| Page | Description |
|------|-------------|
| [Reset Password](reset-password.md) | CLI reset, TOTP recovery, and manual reset via manager.yml |
| [Security](security.md) | Security controls, API keys, sessions, and hardening recommendations |

---

## Mobile App

The [traefik-manager-mobile](mobile.md) companion app connects using an API key.

Go to **Settings - Authentication - App / Mobile API Keys**, click **Add Key**, enter a device name, and copy the generated key. Each device gets its own key - you can revoke one without affecting others.

---

## Self Route

Put Traefik Manager itself behind Traefik so you can access it via a domain with HTTPS.

Go to **Settings - Connection - Self Route**. The URL field pre-fills from your current hostname and the service URL is detected from your existing config if a matching route is found. Click **Save Route** - TM writes the router and service entries into your dynamic config file. No changes to `traefik.yml` needed.

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

A companion Android app for managing Traefik Manager on the go. Requires **v0.6.0 or higher**.

<div class="vp-grid-cards">
<div class="vp-card">

**🤖 traefik-manager-mobile**

Browse routes, middlewares, and services. Enable/disable routes. Add and edit with built-in templates. Follows system light/dark theme.

Authenticates via the API key from **Settings → Authentication**.

<MobileRelease /> [Mobile docs →](mobile.md)

</div>
</div>

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11 · Flask · Gunicorn |
| Config | ruamel.yaml (preserves comments) |
| Auth | bcrypt · pyotp (TOTP) · Flask sessions · CSRF |
| Frontend | Vanilla JS · Tailwind CSS · Phosphor Icons |
| Container | Docker · Alpine Linux |
