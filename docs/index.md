# Traefik Manager

A self-hosted web UI for managing and monitoring your [Traefik](https://traefik.io/) reverse proxy — add routes, manage middlewares, view TLS certificates, and inspect live traffic, all without editing YAML by hand.

---

## Get Started

<div class="grid cards" markdown>

-   :material-docker: **Docker**

    ---

    Deploy with Docker Compose — minimal setup, pre-built image on GHCR.

    [:octicons-arrow-right-24: Docker guide](docker.md)

-   :simple-podman: **Podman**

    ---

    Rootless containers, Quadlet/systemd, SELinux volume labels.

    [:octicons-arrow-right-24: Podman guide](podman.md)

-   :material-linux: **Linux (native)**

    ---

    Run directly on the host with Python + systemd. No container runtime needed.

    [:octicons-arrow-right-24: Linux guide](linux.md)

</div>

---

## Management

These tabs are always visible. They let you read and write your Traefik `dynamic.yml`.

| Tab | Description |
|-----|-------------|
| [Routes](tab-routes.md) | Create, edit, and delete HTTP, TCP, and UDP routes |
| [Middlewares](tab-middlewares.md) | Create and manage middlewares with built-in templates |
| [Services](tab-services.md) | Read-only view of all services across every provider |

---

## Monitoring

Optional tabs — each requires a file mounted into the container.

| Tab                          | Mount required                       | Description                            |
| ------------------------------| --------------------------------------| ----------------------------------------|
| [Certificates](tab-certs.md) | `acme.json:/app/acme.json:ro`        | TLS certificates with expiry tracking  |
| [Plugins](tab-plugins.md)    | `traefik.yml:/app/traefik.yml:ro`    | Plugins declared in your static config |
| [Logs](tab-logs.md)          | `access.log:/app/logs/access.log:ro` | Live Traefik access log tail           |

---

## Providers

Read-only tabs that pull live data from the Traefik API. No extra mounts needed — just a working API connection.

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

| Tab                                     | Provider |
| -----------------------------------------| ----------|
| [HTTP Provider](tab-http_provider.md)   | `http`   |
| [File (external)](tab-file_external.md) | `file`   |

> Traefik Manager's own routes are automatically excluded from the File provider tab.

---

## Configuration

| Page | Description |
|------|-------------|
| [manager.yml](manager-yml.md) | Full settings file reference — all keys, types, and defaults |
| [Environment Variables](env-vars.md) | All supported environment variables with override behaviour |

---

## Operations

| Page | Description |
|------|-------------|
| [Reset Password](reset-password.md) | CLI reset, TOTP recovery, and manual reset via manager.yml |

---

## Traefik provider config snippets

Minimal additions to your `traefik.yml` to enable each provider tab.

=== "Docker"
    ```yaml
    providers:
      docker:
        exposedByDefault: false
    ```

=== "Swarm"
    ```yaml
    providers:
      swarm:
        exposedByDefault: false
    ```

=== "Kubernetes"
    ```yaml
    providers:
      kubernetesCRD: {}
      kubernetesIngress: {}
    ```

=== "Nomad"
    ```yaml
    providers:
      nomad:
        endpoint:
          address: "http://nomad:4646"
    ```

=== "ECS"
    ```yaml
    providers:
      ecs:
        region: us-east-1
        clusters:
          - my-cluster
    ```

=== "Consul Catalog"
    ```yaml
    providers:
      consulCatalog:
        endpoint:
          address: "consul:8500"
        exposedByDefault: false
    ```

=== "Redis"
    ```yaml
    providers:
      redis:
        endpoints:
          - "redis:6379"
    ```

=== "etcd"
    ```yaml
    providers:
      etcd:
        endpoints:
          - "etcd:2379"
    ```

=== "Consul KV"
    ```yaml
    providers:
      consul:
        endpoints:
          - "consul:8500"
    ```

=== "ZooKeeper"
    ```yaml
    providers:
      zooKeeper:
        endpoints:
          - "zookeeper:2181"
    ```

=== "HTTP Provider"
    ```yaml
    providers:
      http:
        endpoint: "https://config.example.com/traefik"
        pollInterval: "30s"
    ```

=== "File (external)"
    ```yaml
    providers:
      file:
        directory: /etc/traefik/dynamic/
        watch: true
    ```

=== "Logs tab"
    ```yaml
    accessLog:
      filePath: "/logs/access.log"
      format: common
    ```
---

## Tech Stack

| Layer     | Technology                                    |
| -----------| -----------------------------------------------|
| Backend   | Python 3.11 · Flask · Gunicorn                |
| Config    | ruamel.yaml (preserves comments)              |
| Auth      | bcrypt · pyotp (TOTP) · Flask sessions · CSRF |
| Frontend  | Vanilla JS · Tailwind CSS · Phosphor Icons    |
| Container | Docker · Alpine Linux                         |