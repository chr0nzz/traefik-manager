<div align="center">

<img src="docs/public/images/icon.png" width="128" height="128" alt="Traefik Manager">

# Traefik Manager

**A clean, self-hosted web UI for your Traefik reverse proxy.**

Routes, middlewares, certificates and logs, without editing YAML by hand.

[![Version](https://img.shields.io/github/v/release/chr0nzz/traefik-manager)](https://github.com/chr0nzz/traefik-manager/releases)
[![Build](https://img.shields.io/github/actions/workflow/status/chr0nzz/traefik-manager/docker.yml?logo=githubactions&logoColor=white&label=build)](https://github.com/chr0nzz/traefik-manager/actions/workflows/docker.yml)
[![Tests](https://img.shields.io/github/actions/workflow/status/chr0nzz/traefik-manager/tests.yml?branch=dev&logo=githubactions&logoColor=white&label=tests)](https://github.com/chr0nzz/traefik-manager/actions/workflows/tests.yml)
[![Docker Image](https://img.shields.io/badge/ghcr.io-chr0nzz%2Ftraefik--manager-blue?logo=docker&logoColor=white)](https://github.com/chr0nzz/traefik-manager/pkgs/container/traefik-manager)
[![License](https://img.shields.io/badge/license-GPL--3.0-blue)](LICENSE)
[![Docs](https://img.shields.io/badge/docs-xyzlab.dev-blue)](https://traefik-manager.xyzlab.dev/)

[![Stars](https://img.shields.io/github/stars/chr0nzz/traefik-manager?logo=github&color=e3b341)](https://github.com/chr0nzz/traefik-manager/stargazers)
[![Issues](https://img.shields.io/github/issues/chr0nzz/traefik-manager?logo=github)](https://github.com/chr0nzz/traefik-manager/issues)
[![Ko-fi](https://img.shields.io/badge/Ko--fi-Sponsor-ff5f5f?logo=ko-fi&logoColor=white)](https://ko-fi.com/chr0nzz)

<sub>Built for homelabbers who love Traefik but hate editing YAML at 2am.</sub>

<p align="center">
<a href="https://traefik-manager.xyzlab.dev/ui-examples.html"><picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/public/images/readme-carousel-dark.gif">
  <img src="docs/public/images/readme-carousel-light.gif" width="85%" alt="Traefik Manager" />
</picture></a>
</p>

</div>

---

## Quick start

### Installer


```bash
curl -fsSL https://get-traefik.xyzlab.dev | bash
```

Installs the `tm` CLI and runs `tm install`. Six modes: Traefik + Traefik Manager together, Traefik Manager on its own (Docker or native), or the agent for a remote host (Docker, Docker + Traefik, or binary).

Afterwards `tm` manages the install: `tm status`, `tm update`, `tm logs`, `tm reconfigure`, `tm doctor`. [Full guide](https://traefik-manager.xyzlab.dev/tm-cli.html)

### Docker Compose

For an existing Traefik install.

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

Open **http://your-server:5000** and the setup wizard takes it from there.

---

## Features

**Routes** - HTTP, TCP and UDP. Multiple domains and backends per route, sticky sessions, health checks, priority, per-route certificate resolvers, wildcard certificates and TLS profiles. Guided presets for security headers and media streaming.

**Services** - build a load balancer, weighted, mirroring or failover service on its own, or balance a route across a mix of raw addresses and existing services with a weight on each row. Services Traefik Manager did not write stay read only until you take them over, which records ownership without touching the file.

**Middlewares** - 35 wizards covering auth, rate limiting, headers, CORS, redirects, prefixes, error pages and TLS client certificates, plus a raw YAML editor and your own reusable templates.

**Dashboard and Route Map** - a homepage-style grid of your apps with icons and health, and a topology map from entry point through middlewares to backend, coloured per hop.

**Monitoring** - live router and service health from the Traefik API, provider tabs for Docker, Kubernetes, Swarm, Nomad, ECS, Consul, Redis and more, TLS expiry tracking, and CVE advisories for your running Traefik version.

**Logs and CrowdSec** - access log analytics and CrowdSec attacks, bans and decisions. Optional country flags and a world map, resolved on your own server.

**Notifications** - nine destinations: Discord, Slack, ntfy, Gotify, Pushover, Pushbullet, Telegram, UnifiedPush and generic webhooks. Route events to each one by category and severity, with quiet hours, hourly or daily digests, and errors that break through anyway. Desktop notifications while a tab is open.

**Background monitoring** - the server checks your routes on a schedule and tells you when a backend goes down or a pool degrades, alongside certificate expiry, Traefik and agent reachability, CrowdSec activity, GeoIP freshness and new releases. Alerts arrive whether or not the interface is open.

**Static config editor** - edit `traefik.yml` from the UI and apply it with a one-click restart, via socket proxy, poison pill or direct socket.

**Plugins** - see every Traefik plugin with the middlewares using it, install new ones, and get flagged when the catalog has a newer version.

**Backups** - timestamped local backups before every change, plus git push with commit history, diffs and one-click restore.

**Multi-server** - a lightweight Go agent runs beside Traefik on any remote host, and every tab works against whichever server you pick. No VPN, no SSH.

**Security** - bcrypt, TOTP two-factor, OIDC single sign-on, per-device API keys, CSRF protection, rate limiting, and secrets encrypted at rest.

**Two layouts** - *Fluid* fills the screen, *Fixed* caps the width.

**Mobile** - a native Android app on Google Play, and the web app installs as a PWA on any platform.

Full [documentation](https://traefik-manager.xyzlab.dev/).

---

## Deployment

| Runtime                                                                                                              | Guide                                                                                 |
| ----------------------------------------------------------------------------------------------------------------------| ---------------------------------------------------------------------------------------|
| <img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/png/windows-terminal.png" width="20" height="20"> Installer | [Full stack, TM only, agent](https://traefik-manager.xyzlab.dev/tm-cli.html)   |
| <img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/png/docker.png" width="20" height="20"> Docker              | [Compose, networking, behind Traefik](https://traefik-manager.xyzlab.dev/docker.html) |
| <img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/png/podman.png" width="20" height="20"> Podman              | [Rootless, Quadlet, SELinux](https://traefik-manager.xyzlab.dev/podman.html)          |
| <img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/png/linux.png" width="20" height="20"> Linux                | [Native Python and systemd](https://traefik-manager.xyzlab.dev/linux.html)            |
| <img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/png/unraid.png" width="20" height="20"> Unraid              | [Template install and appdata paths](https://traefik-manager.xyzlab.dev/unraid.html)     |
| <img src="docs/public/images/icon.png" width="20" height="20"> Agent                                                 | [TMA for multi-server management](https://traefik-manager.xyzlab.dev/agent.html)      |

---

## Documentation

**[traefik-manager.xyzlab.dev](https://traefik-manager.xyzlab.dev/)**

[Overview](https://traefik-manager.xyzlab.dev/overview.html) ·
[Configuration](https://traefik-manager.xyzlab.dev/manager-yml.html) ·
[Environment variables](https://traefik-manager.xyzlab.dev/env-vars.html) ·
[Security](https://traefik-manager.xyzlab.dev/security.html) ·
[API](https://traefik-manager.xyzlab.dev/api.html) ·
[OIDC](https://traefik-manager.xyzlab.dev/oidc.html) ·
[Reset password](https://traefik-manager.xyzlab.dev/reset-password.html) ·
[Beta](https://traefik-manager.xyzlab.dev/beta.html)

---

## tm CLI

One binary that installs and manages the whole stack. Six install modes: Traefik and Traefik Manager together, Traefik Manager on its own (Docker or native), or an agent for a remote host (Docker, Docker + Traefik, or binary). Afterwards `tm status`, `tm update`, `tm logs`, `tm reconfigure`, `tm doctor` and `tm password reset` manage it in place.

[![tm CLI](https://img.shields.io/badge/tm-repo-green?logo=go&logoColor=white)](https://github.com/chr0nzz/tm-cli)
[![Release](https://img.shields.io/github/v/release/chr0nzz/tm-cli?logo=github&logoColor=white)](https://github.com/chr0nzz/tm-cli/releases/latest)
[![Platforms](https://img.shields.io/badge/linux-amd64_%7C_arm64-blue?logo=linux&logoColor=white)](https://github.com/chr0nzz/tm-cli/releases/latest)

```bash
curl -fsSL https://get-traefik.xyzlab.dev | bash
```

[Repository](https://github.com/chr0nzz/tm-cli) ·
[Releases](https://github.com/chr0nzz/tm-cli/releases/latest) ·
[Docs](https://traefik-manager.xyzlab.dev/tm-cli.html)

---

## Mobile app

Native Android, rewritten in Kotlin and Jetpack Compose for v2. Needs Traefik Manager v1.10.1 or newer and a per-device API key from **Settings - Authentication - API Keys**.

[![Mobile App](https://img.shields.io/badge/mobile-repo-green?logo=android&logoColor=white)](https://github.com/chr0nzz/traefik-manager-mobile)
[![Google Play](https://img.shields.io/badge/Google_Play-Available-blue?logo=google-play&logoColor=white)](https://play.google.com/store/apps/details?id=dev.chr0nzz.traefikmanager)
[![Play Downloads](https://playbadges.pavi2410.me/badge/downloads?id=dev.chr0nzz.traefikmanager)](https://play.google.com/store/apps/details?id=dev.chr0nzz.traefikmanager)

[Repository](https://github.com/chr0nzz/traefik-manager-mobile) ·
[Releases](https://github.com/chr0nzz/traefik-manager-mobile/releases/latest) ·
[Docs](https://traefik-manager.xyzlab.dev/mobile.html)

---

## Built with

| Layer | Technology |
| --- | --- |
| Backend | Python 3.11 · Flask 3.1 · Gunicorn |
| Agent | Go 1.25 · Alpine |
| Config | ruamel.yaml, preserving comments and Go templates |
| Auth | bcrypt · pyotp · CSRF · Flask-Limiter · Fernet |
| Frontend | Vanilla JS · Tailwind 3.4 · Phosphor Icons · Monaco |
| Geolocation | maxminddb · DB-IP Lite, local lookups only |
| Tests | pytest · ruff · `go test`, on every pull request |

All JS and CSS is bundled at build time - nothing is fetched from a CDN at runtime.

---

## Contributing

Pull requests are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) for reporting bugs, suggesting features, and running the project locally.

### Contributors

<p align="center">
<a href="https://github.com/fbnlrz" title="Fabi (@fbnlrz) - client-IP feature set, guided route presets, config-safety fixes"><img src="https://images.weserv.nl/?url=github.com/fbnlrz.png&w=140&h=140&fit=cover&mask=circle" width="70" height="70" alt="fbnlrz"></a>
<a href="https://github.com/adrianrp1988" title="Adrian Rodriguez (@adrianrp1988) - TCP middlewares on TCP routes"><img src="https://images.weserv.nl/?url=github.com/adrianrp1988.png&w=140&h=140&fit=cover&mask=circle" width="70" height="70" alt="adrianrp1988"></a>
<a href="https://github.com/akanealw" title="@akanealw - Authelia forward-auth template fix"><img src="https://images.weserv.nl/?url=github.com/akanealw.png&w=140&h=140&fit=cover&mask=circle" width="70" height="70" alt="akanealw"></a>
<a href="https://github.com/maca134" title="@maca134 - horizontally resizable modals"><img src="https://images.weserv.nl/?url=github.com/maca134.png&w=140&h=140&fit=cover&mask=circle" width="70" height="70" alt="maca134"></a>
</p>

Thanks as well to everyone who has opened an issue or a discussion - several features started as a question from someone running into something unexpected.

## Stats

<div align="center">
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/chr0nzz/chr0nzz/main/profile/star-history-traefik-manager-dark.svg" />
  <source media="(prefers-color-scheme: light)" srcset="https://raw.githubusercontent.com/chr0nzz/chr0nzz/main/profile/star-history-traefik-manager-light.svg" />
  <img src="https://raw.githubusercontent.com/chr0nzz/chr0nzz/main/profile/star-history-traefik-manager-dark.svg" alt="star history" />
</picture>

<p align="center">
 <a href="https://www.star-history.com/chr0nzz/traefik-manager">
  <picture><source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/badge?repo=chr0nzz/traefik-manager&type=rank&theme=dark" /><source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/badge?repo=chr0nzz/traefik-manager&type=rank" /><img alt="Star History Rank" src="https://api.star-history.com/badge?repo=chr0nzz/traefik-manager&type=rank" /></picture> <picture><source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/badge?repo=chr0nzz/traefik-manager&type=trending&theme=dark" /><source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/badge?repo=chr0nzz/traefik-manager&type=trending" /><img alt="GitHub Trending Repository of the Day" src="https://api.star-history.com/badge?repo=chr0nzz/traefik-manager&type=trending" /></picture>
 </a>
</p>

</div>


## License

[GPL-3.0](LICENSE)
