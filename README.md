<div align="center">

<img src="docs/images/icon.png" width="128" height="128" alt="Traefik Manager">

# Traefik Manager

**A clean, self-hosted web UI for managing your Traefik reverse proxy.**

Add routes, manage middlewares, monitor services, and view TLS certificates — all without touching a YAML file by hand.

[![Docker Image](https://img.shields.io/badge/ghcr.io-chr0nzz%2Ftraefik--manager-blue?logo=docker&logoColor=white)](https://github.com/chr0nzz/traefik-manager/pkgs/container/traefik-manager)
[![License](https://img.shields.io/badge/license-GPL--3.0-blue)](LICENSE)
[![Version](https://img.shields.io/github/v/release/chr0nzz/traefik-manager)](https://github.com/chr0nzz/traefik-manager/releases)
[![Docs](https://img.shields.io/badge/docs-github.io-blue)](https://traefik-manager.xyzlab.dev/)
[![Mobile App](https://img.shields.io/badge/mobile-traefik--manager--mobile-green?logo=android&logoColor=white)](https://github.com/chr0nzz/traefik-manager-mobile)

</div>
<div align="center">
<sub>Built for homelabbers who love Traefik but hate editing YAML at 2am.</sub>
</div>

---

## Interface Gallery

<details>
<summary><b>Initial Setup Workflow</b></summary>
<p align="center"><i>Screenshots coming soon — setup screen is currently in development.</i></p>
</details>

<details>
<summary><b>Dashboard</b></summary>
<p align="center">
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/images/dark-compact-stats.png">
  <img src="docs/images/light-compact-stats.png" width="48%" alt="Dashboard – compact stats" />
</picture>
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/images/dark-hidden-stats.png">
  <img src="docs/images/light-hidden-stats.png" width="48%" alt="Dashboard – stats hidden" />
</picture>
</p>
</details>

<details>
<summary><b>Routes</b></summary>
<table>
<tr>
<td width="33%">
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/images/dark-routes.png">
  <img src="docs/images/light-routes.png" alt="Routes overview" />
</picture>
<br /><b>Overview</b>
</td>
<td width="33%">
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/images/dark-route-details.png">
  <img src="docs/images/light-route-details.png" alt="Route details" />
</picture>
<br /><b>Details</b>
</td>
<td width="33%">
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/images/dark-route-edit.png">
  <img src="docs/images/light-route-edit.png" alt="Route edit" />
</picture>
<br /><b>Edit</b>
</td>
</tr>
<tr>
<td>
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/images/dark-route-add-http.png">
  <img src="docs/images/light-route-add-http.png" alt="Add HTTP route" />
</picture>
<br /><b>Add HTTP</b>
</td>
<td>
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/images/dark-route-add-tcp.png">
  <img src="docs/images/light-route-add-tcp.png" alt="Add TCP route" />
</picture>
<br /><b>Add TCP</b>
</td>
<td>
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/images/dark-route-add-udp.png">
  <img src="docs/images/light-route-add-udp.png" alt="Add UDP route" />
</picture>
<br /><b>Add UDP</b>
</td>
</tr>
</table>
</details>

<details>
<summary><b>Services</b></summary>
<p align="center">
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/images/dark-services.png">
  <img src="docs/images/light-services.png" width="48%" alt="Services" />
</picture>
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/images/dark-services-details.png">
  <img src="docs/images/light-services-details.png" width="48%" alt="Service details" />
</picture>
</p>
</details>

<details>
<summary><b>Middlewares</b></summary>
<table>
<tr>
<td>
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/images/dark-middleware.png">
  <img src="docs/images/light-middleware.png" alt="Middlewares" />
</picture>
<br /><b>List</b>
</td>
<td>
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/images/dark-middleware-edit.png">
  <img src="docs/images/light-middleware-edit.png" alt="Edit middleware" />
</picture>
<br /><b>Edit</b>
</td>
<td>
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/images/dark-middleware-add.png">
  <img src="docs/images/light-middleware-add.png" alt="Add middleware" />
</picture>
<br /><b>Add</b>
</td>
</tr>
</table>
</details>

<details>
<summary><b>Plugins & Certificates</b></summary>
<p align="center">
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/images/dark-plugins.png">
  <img src="docs/images/light-plugins.png" width="32%" alt="Plugins" />
</picture>
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/images/dark-plugins-details.png">
  <img src="docs/images/light-plugins-details.png" width="32%" alt="Plugin details" />
</picture>
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/images/dark-certs.png">
  <img src="docs/images/light-certs.png" width="32%" alt="Certificates" />
</picture>
</p>
</details>

<details>
<summary><b>Docker Provider</b></summary>
<p align="center">
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/images/dark-docker.png">
  <img src="docs/images/light-docker.png" width="48%" alt="Docker routes" />
</picture>
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/images/dark-docker-details.png">
  <img src="docs/images/light-docker-details.png" width="48%" alt="Docker route details" />
</picture>
</p>
</details>

<details>
<summary><b>Logs</b></summary>
<p align="center">
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/images/dark-logs.png">
  <img src="docs/images/light-logs.png" width="80%" alt="Logs" />
</picture>
</p>
</details>

<details>
<summary><b>Settings</b></summary>
<table>
<tr>
<td width="33%">
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/images/dark-settins-auth.png">
  <img src="docs/images/light-settings-auth.png" alt="Settings – auth" />
</picture>
<br /><b>Authentication</b>
</td>
<td width="33%">
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/images/dark-settins-connections.png">
  <img src="docs/images/light-settings-connections.png" alt="Settings – connections" />
</picture>
<br /><b>Connections</b>
</td>
<td width="33%">
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/images/dark-settins-routes.png">
  <img src="docs/images/light-settings-routes.png" alt="Settings – routes" />
</picture>
<br /><b>Routes Config</b>
</td>
</tr>
<tr>
<td>
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/images/dark-settins-system.png">
  <img src="docs/images/light-settings-system.png" alt="Settings – system" />
</picture>
<br /><b>System</b>
</td>
<td>
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/images/dark-settins-backups.png">
  <img src="docs/images/light-settings-backups.png" alt="Settings – backups" />
</picture>
<br /><b>Backups</b>
</td>
<td>
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/images/dark-settins-ui.png">
  <img src="docs/images/light-settings-ui.png" alt="Settings – UI" />
</picture>
<br /><b>UI Preferences</b>
</td>
</tr>
</table>
</details>

---

## Features

**Routing & Middleware**
- Add, edit, delete, and **enable/disable** HTTP, TCP, and UDP routes — no YAML editing required
- Create middlewares with built-in templates (Basic Auth, Forward Auth, Redirect, Strip Prefix)
- Timestamped backups of `dynamic.yml` before every change; one-click restore from Settings

**Live Dashboard**
- Real-time stats: router counts, service health, entrypoints, Traefik version
- Provider tabs: Docker, Kubernetes, Swarm, Nomad, ECS, Consul Catalog, Redis, etcd, Consul KV, ZooKeeper, HTTP Provider, File — all API-based, no extra mounts
- **Filter live services** by protocol (HTTP/TCP/UDP) and provider (docker, file, kubernetes…)

**System Monitoring** *(optional file mounts)*
- **Certs** — `acme.json` certificates with expiry tracking
- **Plugins** — plugins from your static `traefik.yml`
- **Logs** — live Traefik access log tail

**Security**
- bcrypt passwords, CSRF protection, session management with session fixation protection
- Optional TOTP 2FA · 7-day remember me · 2hr inactivity timeout for browser sessions
- Auto-generated password on first start · CLI recovery with `flask reset-password`
- **API key authentication** — scoped `X-Api-Key` for mobile/app access, revocable without touching your password or 2FA
- **Rate limiting** on login and auth endpoints (Flask-Limiter)
- **Atomic config writes** — crash-safe YAML saves via temp file + rename
- **Encrypted OTP secret** — TOTP seed encrypted at rest with Fernet

---

## Mobile App

**traefik-manager-mobile** is a React Native companion app for managing Traefik Manager from your phone. Requires **Traefik Manager v0.5.0 or higher**.

| | |
|---|---|
| Repo | [github.com/chr0nzz/traefik-manager-mobile](https://github.com/chr0nzz/traefik-manager-mobile) |
| Download | [traefik-manager-v0.1.0.apk](https://github.com/chr0nzz/traefik-manager-mobile/releases/download/v0.1.0/traefik-manager-v0.1.0.apk) |
| Auth | API key — generate one in **Settings → Authentication** |

Features: browse routes, middlewares, and services · enable/disable routes · add and edit routes and middlewares (12 middleware templates) · edit mode for bulk actions · system light/dark theme.

---

## Quick Start

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

```bash
docker compose up -d
```

Open **http://your-server:5000** — the setup wizard will guide you through the rest.

---

## Deployment

| Runtime　 | Guide                                                                                          |
| -----------| ------------------------------------------------------------------------------------------------|
| 🐳 Docker | [Docker Compose setup, networking, behind Traefik](https://traefik-manager.xyzlab.dev/docker/) |
| 🦭 Podman | [Rootless, Quadlet/systemd, SELinux labels](https://traefik-manager.xyzlab.dev/podman/)        |
| 🐧 Linux　| [Native Python + systemd, no container required](https://traefik-manager.xyzlab.dev/linux/)    |

---

## Documentation

Full documentation at **[traefik-manager.xyzlab.dev](https://traefik-manager.xyzlab.dev/)**

| | |
|---|---|
| [Get Started](https://traefik-manager.xyzlab.dev/docker/) | Deployment guides for Docker, Podman, and Linux |
| [Configuration](https://traefik-manager.xyzlab.dev/manager-yml/) | `manager.yml` reference and environment variables |
| [Reset Password](https://traefik-manager.xyzlab.dev/reset-password/) | CLI reset, TOTP recovery, manual reset |
| [UI Examples](https://traefik-manager.xyzlab.dev/ui-examples/) | Screenshots and walkthroughs |
| [Provider Tabs](https://traefik-manager.xyzlab.dev/) | Docker, Kubernetes, Swarm, Nomad, ECS, and more |

---

## Tech Stack

| Layer     | Technology                                    |
| -----------| -----------------------------------------------|
| Backend   | Python 3.11 · Flask · Gunicorn                |
| Config    | ruamel.yaml (preserves comments)              |
| Auth      | bcrypt · pyotp (TOTP) · Flask sessions · CSRF · Flask-Limiter · Fernet |
| Frontend  | Vanilla JS · Tailwind CSS · Phosphor Icons    |
| Container | Docker · Alpine Linux                         |

---

## Contributing

Pull requests are welcome. For larger changes please open an issue first.

## License

[GPL-3.0](LICENSE)
