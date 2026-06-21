# Traefik Manager Agent (TMA)

TMA is a lightweight Go daemon that runs alongside Traefik on a remote server. It exposes an HTTP API on port 8090 that lets a central Traefik Manager instance manage the remote server's routes, config files, backups, and more - without needing direct access to the Traefik API or config files.

## How it works

1. Install TMA on each remote server (alongside Traefik)
2. In TM Settings - Agents, click **Add Agent** and enter the agent's URL
3. TM generates an API key - save it and set it as `TMA_API_KEY` in the agent's environment
4. Use the **server switcher** in the TM navigation bar to switch between the Host and remote servers

Each agent card in Settings - Agents has four action buttons:

| Button | Action |
|---|---|
| Key icon | Manage API keys for this agent |
| Pencil icon | Rename the agent - click to edit inline, Enter or click the checkmark to save |
| Gear icon | Edit agent settings (Traefik config, paths, restart method, git backup, CrowdSec) |
| Trash icon | Remove the agent from TM (does not affect the agent service on the remote server) |

When a remote agent is active:

- **Routes** - The Routes tab shows the agent's routes fetched live from the remote Traefik instance. You can add, edit, delete, and toggle routes exactly as you would locally - changes are written to the agent's config files and a `.bak` backup is created before every write. The Config File selector in the Add/Edit Route modal lists the agent's actual config files (fetched live), not the Host's config files. If the agent has **Domains** configured (Settings - Agents - Traefik tab), the Add/Edit Route modal shows domain chip selectors - the same experience as the Host. Without domains configured, the Subdomain field becomes a free-form **Hostname** field (enter the full hostname, e.g. `app.example.com`). Entrypoints in the route form are fetched live from the agent's Traefik instance.
- **Middlewares** - The Middlewares tab shows only middlewares managed by TM - those in config files under `CONFIG_PATH` with the `@file` provider suffix. Traefik built-in and other provider middlewares are excluded from the badge count and the chip selector. You can add and edit middlewares on the agent exactly as you would locally.
- **Services** - Shows the agent's services from the remote Traefik API.
- **Route Map** - The route map diagram renders the agent's routes and services.
- **Tab visibility** - Provider and monitoring tab toggles (Docker, Kubernetes, Certs, Plugins, etc.) are stored per-server in the browser. Changes made while on an agent do not affect the Host or other agents.
- **Static Config** (Settings - Static Config) - Available if the agent has `STATIC_CONFIG_PATH` set. Raw YAML editing is supported; section-based editing (entrypoints, cert resolvers, etc.) is available only on the Host. Traefik restart works if the agent has `RESTART_METHOD` configured.
- **Backups** (Settings - Backups) - Shows the agent's local `.bak` backup files. The agent creates a `.bak` automatically before every config write; you can also create a manual backup at any time. Restore, delete, and git history operations all proxy through the agent. Git backup configuration fields are hidden (managed via `GIT_BACKUP_*` env vars on the agent). The Static Config backup sub-tab is not shown for agents.
- **Logs** - The Logs tab shows the agent's access log when `ACCESS_LOG_PATH` is set on the agent. When installed via the installer script alongside Traefik, this is set automatically.
- **Certificates** - The Certificates tab shows certs from the agent's `acme.json` when `ACME_JSON_PATH` is set. When installed via the installer script alongside Traefik, this is set automatically.
- **CrowdSec** - If the agent has `CROWDSEC_LAPI_URL` and `CROWDSEC_API_KEY` configured, the CrowdSec tab shows that server's decisions and alerts.
- **Settings sidebar** - When an agent is active, only agent-relevant Settings panels are shown: Backups, Route Monitoring tab toggles, Static Config (if configured), System Monitoring tab toggles (Tab Visibility and File Paths only), and Templates. Authentication, Connection, Notifications, and the CrowdSec credentials sub-tab are hidden - they only apply to the Host. CrowdSec on the agent is configured via `CROWDSEC_LAPI_URL` and `CROWDSEC_API_KEY` env vars on the agent itself.

## Install via installer script

The fastest way is to use the `traefik-stack` installer with the agent option pre-selected:

```bash
curl -fsSL https://get-traefik.xyzlab.dev | bash
```

Choose **Traefik Manager Agent** from the menu. Or, to skip the menu entirely:

```bash
export TMA_INSTALL=1
curl -fsSL https://get-traefik.xyzlab.dev | bash
```

The installer uses an arrow-key menu and a review screen - type a section number to go back and edit it, or press Enter to proceed. It covers all options including:

- **Install method** - Docker agent only, Docker agent + Traefik (deploys both), or binary (systemd)
- **Traefik connection** - API URL, config path, static config mount, and TLS skip-verify (prompted automatically when URL is `https://`)
- **Traefik install** (Agent + Traefik mode) - TLS method, Let's Encrypt email, Cloudflare token, dashboard hostname, network name
- **CrowdSec** - install alongside the agent (Docker only) or connect to an existing instance
- **Git backup**, **optional paths**, **restart method**, **install location**

## Install via Docker manually

```yaml
services:
  traefik-manager-agent:
    image: ghcr.io/chr0nzz/traefik-manager-agent:latest
    restart: unless-stopped
    ports:
      - "8090:8090"
    environment:
      - TMA_API_KEY=your-api-key-here
      - TRAEFIK_API_URL=http://traefik:8080
      - CONFIG_PATH=/app/config
      # Optional - enable static config editing:
      - STATIC_CONFIG_PATH=/etc/traefik/traefik.yml
      # Optional - enable Traefik restart:
      - RESTART_METHOD=proxy
      - TRAEFIK_CONTAINER=traefik
      - DOCKER_HOST=tcp://socket-proxy:2375
    volumes:
      - /host/config:/app/config
      - /etc/traefik/traefik.yml:/etc/traefik/traefik.yml
      - tma_backups:/app/backups

volumes:
  tma_backups:
```

> **Backup persistence**: Always include the `tma_backups` named volume (or a bind mount to a host path via `BACKUP_DIR`). Without it, all backup files stored in `/app/backups` are lost when the container is recreated (e.g. on image update). The Settings - Agents wizard generates this volume automatically.

## Install via binary

Download the binary for your platform from the [GitHub Releases](https://github.com/chr0nzz/traefik-manager/releases) page (`tma-linux-amd64`, `tma-linux-arm64`, etc.) and create a systemd unit:

```ini
[Unit]
Description=Traefik Manager Agent
After=network.target

[Service]
Environment=TMA_API_KEY=your-api-key-here
Environment=TRAEFIK_API_URL=http://traefik:8080
Environment=CONFIG_PATH=/app/config
ExecStart=/usr/local/bin/tma
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now tma
```

## Environment variables

### Required

| Variable | Description |
|---|---|
| `TMA_API_KEY` | API key generated in TM Settings - Agents |

### Traefik connection

| Variable | Default | Description |
|---|---|---|
| `TRAEFIK_API_URL` | `http://traefik:8080` | Traefik API URL. Use `http://traefik:8080` when TMA runs alongside Traefik on the same Docker network, or a public HTTPS URL for a remote Traefik instance. |
| `TRAEFIK_INSECURE_SKIP_VERIFY` | `false` | Skip TLS certificate verification for HTTPS Traefik API URLs. Useful when using a self-signed cert or Cloudflare Origin Certificate. |
| `CONFIG_PATH` | `/app/config` | Dynamic config directory or file |
| `STATIC_CONFIG_PATH` | - | Path to `traefik.yml` - enables static config R/W |

### Optional paths

| Variable | Default | Description |
|---|---|---|
| `ACME_JSON_PATH` | - | Path to `acme.json` - enables cert info reads |
| `ACCESS_LOG_PATH` | - | Path to Traefik access log file |
| `PLUGINS_DIR` | - | Path to Traefik plugins directory |
| `BACKUP_DIR` | `/app/backups` | Directory where local `.bak` backup files are stored |

### Traefik restart

| Variable | Default | Description |
|---|---|---|
| `RESTART_METHOD` | - | `proxy`, `poison-pill`, or `socket` |
| `TRAEFIK_CONTAINER` | `traefik` | Container name (used by `proxy` and `socket` methods) |
| `DOCKER_HOST` | - | e.g. `tcp://socket-proxy:2375` (used by `proxy` method) |
| `SIGNAL_FILE_PATH` | - | e.g. `/signals/restart.sig` (used by `poison-pill` method) |

### CrowdSec

| Variable | Default | Description |
|---|---|---|
| `CROWDSEC_LAPI_URL` | - | CrowdSec LAPI URL (e.g. `http://crowdsec:8080`) |
| `CROWDSEC_API_KEY` | - | CrowdSec bouncer API key - used to read **decisions** (active bans/captchas/bypasses) |
| `CROWDSEC_MACHINE_ID` | - | CrowdSec machine login - required to read **alerts** and to unban (delete decisions) |
| `CROWDSEC_MACHINE_PASSWORD` | - | Password for the machine login |

**Two credential types - why both?**

CrowdSec's LAPI uses two different authentication methods for different endpoints:

- **Bouncer key** (`CROWDSEC_API_KEY`) can read the active **decisions** list. This is all you need to see and filter bans, captchas, and bypasses in the CrowdSec tab.
- **Machine credentials** (`CROWDSEC_MACHINE_ID` + `CROWDSEC_MACHINE_PASSWORD`) are required to read the **alerts** list and to **unban** (delete a decision). Bouncer keys cannot access these endpoints - the LAPI returns `403 access forbidden` or an empty result.

Set both if you want the full CrowdSec tab (decisions **and** alerts plus unban). Set only the bouncer key if you only need the decisions view.

**Creating a machine login:**

On the CrowdSec host, register a machine and let CrowdSec generate the credentials:

```bash
sudo cscli machines add traefik-manager --auto
sudo cat /etc/crowdsec/local_api_credentials.yaml
```

Copy the `login` and `password` from that file into `CROWDSEC_MACHINE_ID` and `CROWDSEC_MACHINE_PASSWORD`. If the machine shows as unvalidated, run `sudo cscli machines validate traefik-manager`.

> **Compose gotcha**: if the generated password contains a `$`, escape it as `$$` in `docker-compose.yml` (Docker Compose treats a single `$` as a variable reference). No escaping is needed for a Docker `run` command or a systemd unit.

**If CrowdSec runs as a systemd service on the same host as the agent:**

The agent container cannot reach `127.0.0.1` on the host directly. Use `host.docker.internal` instead and add `extra_hosts` to the agent service:

```yaml
services:
  traefik-manager-agent:
    extra_hosts:
      - "host.docker.internal:host-gateway"
    environment:
      - CROWDSEC_LAPI_URL=http://host.docker.internal:8070
```

You also need to allow the agent's Docker network subnet to reach the CrowdSec LAPI port through the host firewall. Find the subnet and add the rule:

```bash
docker network inspect <your-network> | grep Subnet
sudo ufw allow from <subnet> to any port <crowdsec-port> proto tcp
```

### Git backup

| Variable | Default | Description |
|---|---|---|
| `GIT_BACKUP_ENABLED` | `false` | Enable autonomous git backup |
| `GIT_BACKUP_REPO` | - | HTTPS git repository URL |
| `GIT_BACKUP_BRANCH` | `main` | Branch to push to |
| `GIT_BACKUP_USERNAME` | - | Git username |
| `GIT_BACKUP_TOKEN` | - | Git access token |
| `GIT_BACKUP_COMMIT_MESSAGE` | `traefik-manager: {action} at {timestamp}` | Commit message template |
| `GIT_BACKUP_AUTO_PUSH` | `true` | Push after every config write |

### Agent server

| Variable | Default | Description |
|---|---|---|
| `TMA_PORT` | `8090` | Listening port |
| `TMA_RATE_LIMIT` | `300` | Requests per minute per IP (0 = disabled) |

`TMA_PORT` and `TMA_RATE_LIMIT` can also be set from the **Settings - Agents** wizard. They appear as optional fields in the configuration step; leave them blank to use the defaults. The generated Docker Compose only includes these env vars when a non-default value is entered.

### Domains (TM-side, not an env var)

The **Domains** field in Settings - Agents (Traefik tab) is a TM-side configuration - it is not passed to the agent container. It tells TM what domains are available on this agent when creating or editing routes. Enter one or more domains separated by commas (e.g. `example.com, example.net`). When set, the Add/Edit Route modal shows a domain chip selector exactly like the Host. When left blank, the Subdomain field becomes a free-form Hostname field for the full hostname.

## Storage

Agent registrations (name, URL, encrypted API key, and configuration) are stored in `agents.yml` in the same config directory as `manager.yml` (default `/app/config/agents.yml`). The file is created automatically when the first agent is added. If you are upgrading from a version before v1.5.0, agents are migrated automatically from `manager.yml` to `agents.yml` on first start - no manual action required.

Back up `agents.yml` alongside `manager.yml` to preserve agent registrations.

## Security

- The API key is the only credential - keep it secret and use HTTPS between TM and TMA
- Put TMA behind a reverse proxy (Traefik itself) with TLS for production use
- `TMA_RATE_LIMIT` defaults to 300 req/min - TM makes many API calls per tab switch so the default is intentionally generous; lower it only if you need to restrict access
- The `/health` endpoint is public (no auth required) - use it for uptime monitoring

## Updating

**Docker:**
```bash
cd /opt/traefik-manager-agent
docker compose pull && docker compose up -d
```

**Binary:**
```bash
curl -fsSL https://github.com/chr0nzz/traefik-manager/releases/latest/download/tma-linux-amd64 \
  -o /usr/local/bin/tma && chmod +x /usr/local/bin/tma
sudo systemctl restart tma
```

## Agent git backup

When `GIT_BACKUP_ENABLED=true`, the agent handles its own git backup cycle autonomously using the `GIT_BACKUP_*` env vars. You do not configure agent git backup through the TM Settings UI - the Settings - Agents wizard generates the Docker Compose with all env vars pre-filled based on your inputs.

When an agent is active in the TM server switcher, Settings - Backups shows the agent's backup data:

- **Dynamic Config tab** - lists and restores the agent's local `.bak` backups. The agent automatically creates a `.bak` file before every config write (route or middleware save), so changes can always be rolled back. Manual "Create Backup" backs up all config files at once. Backup files are named `filename.YYYYMMDD_HHMMSS.bak` and stored in `BACKUP_DIR`.
- **Git tab** - shows the agent's git history, status, and allows manual push and git restore; git configuration fields are hidden (managed by env vars on the agent)
- **Static Config tab** - not shown for agents (static config is part of the regular backup)

See [API Reference - Agent](api-agent.md) for the full endpoint list.

## Troubleshooting

**Switched to an agent but the Routes/Services tabs are empty ("No routes found")**

This almost always means the agent container can reach Traefik Manager, but the **agent itself cannot reach its Traefik API**. Routes from the Docker, Kubernetes, and other providers come from the Traefik API, so if `TRAEFIK_API_URL` is wrong or unreachable from inside the agent container, those routes all disappear. The Routes tab shows a banner with the exact connection error (e.g. `traefik unavailable at http://traefik:8080: connection refused`).

Check the agent's `TRAEFIK_API_URL`:

- It must be reachable **from inside the agent container**. `http://traefik:8080` only works when the agent shares Traefik's Docker network; from a different host or network, point it at the Traefik API's reachable address.
- Traefik's API must be enabled (`--api=true`) and listening where the URL points.
- Test it from the agent host: `docker exec <agent-container> wget -qO- http://traefik:8080/api/http/routers` - it should return JSON.

For HTTPS Traefik API URLs with a self-signed or Cloudflare Origin certificate, set `TRAEFIK_INSECURE_SKIP_VERIFY=true`.
