# Traefik Manager - Documentation

A reference guide for all tabs, settings, and configuration options.

---

## Quick start

1. **First run** - a temporary password is printed to container logs. Log in, complete the setup wizard, and set a permanent password.
2. **Enable tabs** - in the setup wizard step 2 ("Optional monitoring"), toggle the tabs you need. You can change this any time in **Settings → Visible Tabs**.
3. **Connect to Traefik** - provide your Traefik API URL in **Settings → Connection** (e.g. `http://traefik:8080`). Click **Test connection** to verify.
4. **Add your first route** - click **Add Route** in the top bar.

---

## Management tabs

These tabs are always visible and let you manage your Traefik configuration.

| Tab         | Doc                                      | Description                                                                             |
| -------------| ------------------------------------------| -----------------------------------------------------------------------------------------|
| Routes      | [tab-routes.md](tab-routes.md)           | Create, edit, and delete HTTP/TCP/UDP routes stored in `dynamic.yml`                    |
| Middlewares | [tab-middlewares.md](tab-middlewares.md) | Create and manage middleware definitions with built-in templates                        |
| Services    | [tab-services.md](tab-services.md)       | Read-only view of all Traefik services across every provider (`@file`, `@docker`, etc.) |

---

## Monitoring tabs

Optional tabs that require host file mounts.

| Tab | Doc | Mount required | Description |
|-----|-----|----------------|-------------|
| SSL Certificates | [tab-certs.md](tab-certs.md) | `acme.json:/app/acme.json:ro` | TLS certificates issued by Traefik's ACME resolver |
| Plugins | [tab-plugins.md](tab-plugins.md) | `traefik.yml:/app/traefik.yml:ro` | Plugins declared under `experimental.plugins` in the static config |
| Logs | [tab-logs.md](tab-logs.md) | `logs/access.log:/logs/access.log:ro` | Traefik access log tail |

---

## Provider tabs

All provider tabs are **read-only**. Data is pulled live from the Traefik API - no extra volume mounts needed. Each tab filters `/api/http/routers` (and TCP/UDP) by the `provider` field.

### Orchestrator providers

| Tab | Doc | Provider string(s) | `traefik.yml` key |
|-----|-----|--------------------|-------------------|
| Docker | [tab-docker.md](tab-docker.md) | `docker` | `providers.docker` |
| Kubernetes | [tab-kubernetes.md](tab-kubernetes.md) | `kubernetescrd`, `kubernetes`, `kubernetesgateway` | `providers.kubernetesCRD` / `providers.kubernetesIngress` |
| Swarm | [tab-swarm.md](tab-swarm.md) | `swarm` | `providers.swarm` |
| Nomad | [tab-nomad.md](tab-nomad.md) | `nomad` | `providers.nomad` |
| ECS | [tab-ecs.md](tab-ecs.md) | `ecs` | `providers.ecs` |
| Consul Catalog | [tab-consulcatalog.md](tab-consulcatalog.md) | `consulcatalog` | `providers.consulCatalog` |

### KV store providers

| Tab | Doc | Provider string | `traefik.yml` key |
|-----|-----|-----------------|-------------------|
| Redis | [tab-redis.md](tab-redis.md) | `redis` | `providers.redis` |
| etcd | [tab-etcd.md](tab-etcd.md) | `etcd` | `providers.etcd` |
| Consul KV | [tab-consul.md](tab-consul.md) | `consul` | `providers.consul` |
| ZooKeeper | [tab-zookeeper.md](tab-zookeeper.md) | `zookeeper` | `providers.zooKeeper` |

> **Consul Catalog vs Consul KV** - two separate providers. Consul Catalog (`consulcatalog`) uses service discovery. Consul KV (`consul`) reads from the key-value store. They have separate tabs.

### Config-based providers

| Tab | Doc | Provider string | Notes |
|-----|-----|-----------------|-------|
| HTTP Provider | [tab-http_provider.md](tab-http_provider.md) | `http` | Traefik polls a remote URL for dynamic config |
| File (external) | [tab-file_external.md](tab-file_external.md) | `file` | External file configs - traefik-manager-managed routes are automatically excluded |

---

## Traefik configuration reference

Minimal `traefik.yml` snippets to enable each provider. Add to your existing static config.

### Docker
```yaml
providers:
  docker:
    exposedByDefault: false
```

### Docker Swarm
```yaml
providers:
  swarm:
    exposedByDefault: false
```

### Kubernetes
```yaml
providers:
  kubernetesCRD: {}
  kubernetesIngress: {}
```

### Nomad
```yaml
providers:
  nomad:
    endpoint:
      address: "http://nomad:4646"
```

### Amazon ECS
```yaml
providers:
  ecs:
    region: us-east-1
    clusters:
      - my-cluster
```

### Consul Catalog
```yaml
providers:
  consulCatalog:
    endpoint:
      address: "consul:8500"
    exposedByDefault: false
```

### Redis
```yaml
providers:
  redis:
    endpoints:
      - "redis:6379"
```

### etcd
```yaml
providers:
  etcd:
    endpoints:
      - "etcd:2379"
```

### Consul KV
```yaml
providers:
  consul:
    endpoints:
      - "consul:8500"
```

### ZooKeeper
```yaml
providers:
  zooKeeper:
    endpoints:
      - "zookeeper:2181"
```

### HTTP Provider
```yaml
providers:
  http:
    endpoint: "https://config.example.com/traefik"
    pollInterval: "30s"
```

### File provider (external)
```yaml
providers:
  file:
    directory: /etc/traefik/dynamic/
    watch: true
```

### Access logging (for Logs tab)
```yaml
accessLog:
  filePath: "/logs/access.log"
  format: common
```

---

## Other docs

| Doc | Description |
|-----|-------------|
| [UI Examples](ui-examples.md) | Screenshots and workflow walkthroughs |
| [Podman](podman.md) | Running with Podman - compose, rootless, Quadlet/systemd, SELinux volume labels |
