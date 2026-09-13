# Traefik Manager Agent (TMA)

TMA is a lightweight Go daemon that runs alongside Traefik on a remote server. It exposes an HTTP API on port 8090 that lets a central Traefik Manager instance manage that server's routes, config files, backups and more, without direct access to its Traefik API or config files.

## How it works

1. In TM Settings - Agents, click **Add Agent** and pick one of the two paths
2. **Install with the tm CLI** (recommended) - enter a name and URL, TM mints the key and hands you a one-line command to run on the remote server, then a **Verify connection** button checks that TM can reach it
3. **Configure manually** - enter a name and URL, save the API key (shown once), set it as `TMA_API_KEY` on the remote server, and copy out the generated Docker Compose or `docker run` command
4. Use the **server switcher** in the TM navigation bar to switch between the Host and remote servers

Each agent card in Settings - Agents carries three buttons on the right:

| Control | Action |
|---|---|
| Key icon | Manage API keys for this agent |
| Gear icon | Agent Settings - edit the name and URL, verify the connection, rotate the key, and configure Traefik, paths, restart method, git backup and CrowdSec |
| Trash icon | Remove the agent from TM. Its git clone under the Host's `BACKUP_DIR` and its per-agent entries in `manager.yml` go with it (see [Storage](#storage)); the agent service on the remote machine keeps running |

When a remote agent is active:

- **Routes** - Fetched live from the remote Traefik instance. Add, edit, delete and toggle work exactly as they do locally; changes are written to the agent's config files, with a `.bak` backup before every write. The Config File selector lists the agent's own files, fetched live, and entrypoints come from the agent's Traefik API. If the agent has **Domains** configured (Settings - Agents - Traefik tab) or existing routes to detect domains from, the form shows the same domain chip selectors as the Host, including auto-detected domains and a **+** chip for ad-hoc entry. Without any domains the Subdomain field becomes a free-form **Hostname** field (enter the full hostname, e.g. `app.example.com`). The **Security headers** and **Optimize for streaming** presets write their middleware and `serversTransport` into that agent's own config. Cert resolvers are detected automatically from the agent's Traefik API - any resolver already used by one of that server's routers is offered - merged with the resolvers in its static config when that is mounted. The optional **Certificate Resolver** field (Settings - Agents - Traefik tab) adds resolver names that no route uses yet.
- **Middlewares** - Shows only middlewares managed by TM: those in config files under `CONFIG_PATH` with the `@file` provider suffix. Traefik built-in and other provider middlewares are excluded from the badge count and the chip selector. Add and edit work as they do locally.
- **Services** - The agent's services from the remote Traefik API. Create, edit, rename, delete and take over management work as they do locally; changes are written to the agent's config files. Ownership is recorded per server, so a service managed on one agent is not managed on another or on the Host.
- **Route Map** - Renders the agent's routes and services.
- **Tab visibility** - Provider and monitoring tab toggles (Docker, Kubernetes, Certs, Plugins, etc.) are stored per server: an agent's toggles are saved with its registration in `agents.yml`, the Host's in `manager.yml`. Changes made while on an agent do not affect the Host or other agents.
- **Static Config** - Available if the agent has `STATIC_CONFIG_PATH` set and `traefik.yml` mounted read-write. With that agent selected, the Off / Settings / Tab choice appears under **Settings - Interface** and offers the same section editing as the Host. Changes are staged and written to the agent's file on save, with a `.bak` backup first. Traefik restart after save works if the agent has `RESTART_METHOD` configured. See [Static config editing](#static-config-editing).
- **Plugins** - Lists and manages the plugins declared under `experimental.plugins` in the agent's static config (requires `STATIC_CONFIG_PATH`). Install from a pasted snippet, edit and remove all work against the agent's `traefik.yml`; the generated middleware snippet is written to the agent config file you pick in the install form (default `plugin-middlewares.yml`).
- **Backups** (Settings - Backups) - Shows the agent's local `.bak` files. The agent creates one automatically before every config write, and you can create a manual backup at any time. In the Git sub-tab, **Use Host Repository** has the Host push this agent's config to the Host's git repository on a dedicated branch (no agent-side git config needed); otherwise the agent stays autonomous via its `GIT_BACKUP_*` env vars. The Static Config sub-tab appears when the agent has `STATIC_CONFIG_PATH` set (or already has static backups) and lists the `traefik.yml` backups separately from the route config backups.
- **Logs** - Shows the agent's access log when `ACCESS_LOG_PATH` is set on the agent. The installer sets it when it deploys Traefik alongside the agent.
- **Certificates** - Shows certs from the agent's `acme.json` when `ACME_JSON_PATH` is set, and marks the ones nothing uses. The installer sets it when it deploys Traefik alongside the agent. To remove certificates on this server, mount its `acme.json` read-write and give the agent a `RESTART_METHOD`; the Certs tab reads both from the agent rather than assuming.
- **CrowdSec** - If the agent has `CROWDSEC_LAPI_URL` plus a bouncer key, machine credentials, or both, the CrowdSec tab shows that server's attack surface: who is hitting it, from which networks, which scenarios fired, what they were going after, and the bans in force. The Host needs no access to that CrowdSec instance - every call is proxied through the agent. See [CrowdSec on an agent](#crowdsec-on-an-agent).
- **Settings sidebar** - Authentication, Connection, Notifications and the CrowdSec credentials sub-tab are hidden while an agent is active; they only apply to the Host. An **API Keys** entry appears under Remote for the agent's own keys. CrowdSec on an agent is configured with env vars on the agent itself, not from the Host UI.

## Install via installer script

The fastest way is the `tm` CLI installer, which opens its wizard:

```bash
curl -fsSL https://get-traefik.xyzlab.dev | bash
```

Choose **Traefik Manager Agent** from the menu. To skip the menu entirely:

```bash
export TMA_INSTALL=1
curl -fsSL https://get-traefik.xyzlab.dev | bash
```

`TMA_INSTALL=1` is the same as `tm install --mode agent`. Once `tm` is installed you can also pass the mode and the agent settings directly:

```bash
tm install --mode agent-docker --api-key <key> --traefik-url http://traefik:8080
```

Modes: `agent-docker`, `agent-docker-traefik`, `agent-binary`.

**Add Agent - Install with the tm CLI** generates exactly this, with the key already filled in:

```bash
export TMA_API_KEY='<key>'
curl -fsSL https://get-traefik.xyzlab.dev | bash -s -- --mode agent
```

`tm` reads the key from the environment, so it never appears in `ps` output.

## Installer wizard

The wizard uses an arrow-key menu and a review screen - type a section number to go back and edit it, or press Enter to proceed. It covers:

- **Install method** - Docker agent only, Docker agent + Traefik (deploys both), or binary (systemd)
- **Traefik connection** - API URL, config path, static config mount, and TLS skip-verify (prompted automatically when the URL is `https://`)
- **Traefik install** (Agent + Traefik mode) - TLS method, Let's Encrypt email, Cloudflare token, dashboard hostname, network name
- **CrowdSec** - install alongside the agent (Docker only) or connect to an existing instance
- **Git backup**, **optional paths**, **restart method**, **install location**

## Managing an agent

Traefik Manager's Agents panel writes the agent's **configuration**. The agent process itself - updating,
restarting, diagnosing - is managed on the agent's own machine, with `tm` installed there:

| Command | What it does |
|---|---|
| `tm status` | what is installed, and whether it is healthy |
| `tm logs` | follow the agent log |
| `tm update` | update the agent to the current release |
| `tm reconfigure` | change any answer from the installer |
| `tm doctor` | diagnose a broken install |
| `tm add crowdsec` | add CrowdSec to this agent |

`tm` adopts an install it did not create, so this works even if the agent was set up by hand. See
[tm CLI](tm-cli.md#managing-the-install).

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
      # Optional - enable the CrowdSec tab for this server:
      - CROWDSEC_LAPI_URL=http://crowdsec:8080
      - CROWDSEC_API_KEY=your-bouncer-api-key
      - CROWDSEC_MACHINE_ID=traefik-manager
      - CROWDSEC_MACHINE_PASSWORD=your-machine-password
    volumes:
      - /host/config:/app/config
      # Required by STATIC_CONFIG_PATH above. Must be the same traefik.yml Traefik
      # itself reads, and must be writable - no :ro
      - /etc/traefik/traefik.yml:/etc/traefik/traefik.yml
      - tma_backups:/app/backups

volumes:
  tma_backups:
```

> **Backup persistence**: always include the `tma_backups` named volume (or a bind mount to a host path via `BACKUP_DIR`). Without it everything under `/app/backups` is lost when the container is recreated, for example on an image update. The Settings - Agents wizard generates this volume automatically.

## Static config editing

Two things enable the **Static Config** tab for an agent: the env var, and a volume that puts the file inside the agent container.

```yaml
services:
  traefik-manager-agent:
    environment:
      - STATIC_CONFIG_PATH=/etc/traefik/traefik.yml
    volumes:
      - /etc/traefik/traefik.yml:/etc/traefik/traefik.yml
```

The two must agree: `STATIC_CONFIG_PATH` is the path **inside the agent container**, which is the right-hand side of the volume. Mount it wherever you like, as long as the env var names the same place.

The left-hand side is the host path, and it must be the very file your Traefik reads. If Traefik runs in Docker, use the same host path its own compose mounts:

```yaml
services:
  traefik:
    volumes:
      - /srv/traefik/traefik.yml:/traefik.yml:ro      # Traefik reads it here

  traefik-manager-agent:
    environment:
      - STATIC_CONFIG_PATH=/traefik.yml
    volumes:
      - /srv/traefik/traefik.yml:/traefik.yml          # agent edits the same file
```

Only the host path has to match. Traefik may keep its copy read-only; the agent's must not be.

- The agent's mount must be **writable** - no `:ro`. A `.bak` is written to the agent's backup directory before every save. Single-file bind mounts are supported.
- The Off / Settings / Tab choice appears under **Settings - Interface** while that agent is the active server, and only when the agent reports the file as readable. Recreate the agent after adding the env var, then check again.
- To restart Traefik after a save, set `RESTART_METHOD` on the agent. `proxy` needs `TRAEFIK_CONTAINER` plus `DOCKER_HOST` pointing at a docker socket proxy (e.g. `tcp://socket-proxy:2375`) with `CONTAINERS=1` and `POST=1`, reachable from the agent's network.
- Agents get the same section editing as the Host: entrypoints, providers, cert resolvers, API and dashboard, logging, observability and system sections, plugin cards, the trusted-IPs helper and the raw YAML editor.
- Setting `STATIC_CONFIG_PATH` also enables plugin management in the agent's **Plugins** tab.

## CrowdSec on an agent

Each agent talks to its own CrowdSec LAPI. The Host never connects to it - every request is proxied through the agent - so a CrowdSec that only listens on a private network is fine, and each server shows its own attacks under its own entry in the server switcher.

Point the agent at the LAPI and give it credentials:

```yaml
services:
  traefik-manager-agent:
    environment:
      - CROWDSEC_LAPI_URL=http://crowdsec:8080
      - CROWDSEC_API_KEY=your-bouncer-api-key
      - CROWDSEC_MACHINE_ID=traefik-manager
      - CROWDSEC_MACHINE_PASSWORD=your-machine-password
    networks:
      - traefik-net
```

### Generating the credentials

Run both on the machine hosting CrowdSec. In Docker, prefix with `docker exec <crowdsec-container>`.

```bash
cscli bouncers add traefik-manager
cscli machines add traefik-manager --auto -f-
```

Both are printed once - copy the bouncer key into `CROWDSEC_API_KEY`, and the machine's `login` and `password` into `CROWDSEC_MACHINE_ID` and `CROWDSEC_MACHINE_PASSWORD`. If the machine shows as unvalidated, run `cscli machines validate traefik-manager`. Escape a `$` in the password as `$$` in `docker-compose.yml` (Compose reads a single `$` as a variable reference); no escaping is needed for `docker run` or a systemd unit.

> `-f-` prints the credentials. Without it `cscli` overwrites `/etc/crowdsec/local_api_credentials.yaml`, which is what CrowdSec's own log processor logs in with.

### What each credential gets you

The LAPI accepts each on different endpoints, so the two are complementary, not tiered: the machine token is refused on `/v1/decisions`, the bouncer key on `/v1/alerts`. Set either one alone and the tab says plainly what it cannot see.

| Configured | What the CrowdSec tab shows |
|---|---|
| Bouncer key only | Bans in force, and the decisions view. No alerts, so no attacking sources, networks, scenarios, paths or tooling |
| Machine credentials only | The full attack surface from alerts, but no ban state - sources are reported as *unknown* rather than guessed as unbanned |
| Both | Everything, including unbanning from the UI and adding manual decisions |

**LAPI behind mutual TLS?** Set `CROWDSEC_CLIENT_CERT`, `CROWDSEC_CLIENT_KEY` and `CROWDSEC_CA_CERT` instead (paths as mounted inside the agent container, added as read-only volumes). One client certificate covers decisions and alerts when its OU is listed in both `bouncers_allowed_ou` and `agents_allowed_ou`, and the LAPI auto-provisions the bouncer and machine on first contact - no key or password needed.

**CrowdSec running as a systemd service on the agent's host?** The agent container cannot reach `127.0.0.1` on the host directly. Use `host.docker.internal` and add `extra_hosts`:

```yaml
services:
  traefik-manager-agent:
    extra_hosts:
      - "host.docker.internal:host-gateway"
    environment:
      - CROWDSEC_LAPI_URL=http://host.docker.internal:8070
```

You also need to allow the agent's Docker network subnet to reach the CrowdSec LAPI port through the host firewall:

```bash
docker network inspect <your-network> | grep Subnet
sudo ufw allow from <subnet> to any port <crowdsec-port> proto tcp
```

### Notes

- The tab is enabled per server. With the agent active, toggle **CrowdSec** under **Settings - System Monitoring - Tab Visibility**.
- If the agent cannot reach the LAPI at all, the tab says so rather than reporting zero decisions as fact.

## Install via binary

The easy path is `tm install --mode agent-binary`: it downloads the binary for your architecture, verifies the checksum, installs it to `/usr/local/bin/tma`, writes the unit, and puts the secrets in `/etc/traefik-manager-agent/env` (mode 600, referenced by `EnvironmentFile=`) rather than inline in the unit.

Manually: download the binary for your platform from the [GitHub Releases](https://github.com/chr0nzz/traefik-manager/releases) page (`tma-linux-amd64`, `tma-linux-arm64`, `tma-linux-armv7`) and create a systemd unit:

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
| `TMA_API_KEY` | API key generated in TM Settings - Agents. The agent refuses to start without it |

### Traefik connection

| Variable | Default | Description |
|---|---|---|
| `TRAEFIK_API_URL` | `http://traefik:8080` | Traefik API URL. Use `http://traefik:8080` when TMA runs alongside Traefik on the same Docker network, or a public HTTPS URL for a remote Traefik instance |
| `TRAEFIK_API_USER` | - | Username for a Traefik API behind basic auth. Set together with `TRAEFIK_API_PASSWORD`; when both are set the agent sends HTTP Basic Auth on every Traefik API call |
| `TRAEFIK_API_PASSWORD` | - | Password paired with `TRAEFIK_API_USER` |
| `TRAEFIK_INSECURE_SKIP_VERIFY` | `false` | Skip TLS verification for HTTPS Traefik API URLs. For self-signed or Cloudflare Origin certificates |
| `CONFIG_PATH` | `/app/config` | Dynamic config directory or file. This is the **only** config-location variable the agent has - see the note below |
| `STATIC_CONFIG_PATH` | - | Path to `traefik.yml` - enables static config R/W |

::: warning CONFIG_DIR and CONFIG_PATHS are Host-only
The agent reads **`CONFIG_PATH` only**. `CONFIG_DIR` and `CONFIG_PATHS`, which the Host supports, do not exist in the agent and are ignored if you set them.

`CONFIG_PATH` covers both cases on its own:

```ini
# a directory - every .yml/.yaml file directly inside it is managed
Environment=CONFIG_PATH=/etc/traefik/conf.d

# or a single file
Environment=CONFIG_PATH=/etc/traefik/dynamic.yml
```

A directory is read **one level deep**, not recursively. Point it at the folder that actually holds your router files: pointing at a parent like `/etc/traefik` picks up `traefik.yml` (your *static* config, which has no routers) and never descends into `conf.d`, so the Routes and Middlewares tabs come back empty with no error.
:::

### Optional paths

| Variable | Default | Description |
|---|---|---|
| `ACME_JSON_PATH` | - | Path to `acme.json` - enables cert info reads. Accepts several files comma-separated, or a directory whose `.json` files are all read (Traefik writes one storage file per cert resolver). Mount it read-write, and set `RESTART_METHOD`, to allow removing certificates from this agent |
| `ACCESS_LOG_PATH` | - | Path to Traefik access log file |
| `PLUGINS_DIR` | - | Path to Traefik plugins directory |
| `BACKUP_DIR` | `/app/backups` | Agent data directory. `.bak` files are written to `<BACKUP_DIR>/backups`, the API key store to `<BACKUP_DIR>/api_keys.json`, and the git clone to `<BACKUP_DIR>/git-repo` |
| `BACKUP_KEEP_COUNT` | `0` | Keep only the last N `.bak` files per config file (0 = keep all) |

### Traefik restart

| Variable | Default | Description |
|---|---|---|
| `RESTART_METHOD` | - | `proxy`, `poison-pill`, or `socket`. `socket` talks to `/var/run/docker.sock`, so mount it into the agent |
| `TRAEFIK_CONTAINER` | `traefik` | Container name (used by `proxy` and `socket`) |
| `DOCKER_HOST` | - | e.g. `tcp://socket-proxy:2375` (used by `proxy`) |
| `SIGNAL_FILE_PATH` | - | e.g. `/signals/restart.sig` (used by `poison-pill`) |

### CrowdSec

Setup, credential generation and what each credential unlocks are in [CrowdSec on an agent](#crowdsec-on-an-agent).

| Variable | Default | Description |
|---|---|---|
| `CROWDSEC_LAPI_URL` | - | CrowdSec LAPI URL (e.g. `http://crowdsec:8080`) |
| `CROWDSEC_API_KEY` | - | Bouncer API key - reads **decisions** (active bans/captchas/bypasses) |
| `CROWDSEC_MACHINE_ID` | - | Machine login - required to read **alerts** and to unban (delete decisions) |
| `CROWDSEC_MACHINE_PASSWORD` | - | Password for the machine login |
| `CROWDSEC_CLIENT_CERT` | - | TLS client certificate for a LAPI behind mTLS, replaces the API key and machine login |
| `CROWDSEC_CLIENT_KEY` | - | The client certificate's private key |
| `CROWDSEC_CA_CERT` | - | CA certificate that signed the LAPI's own certificate (private PKI) |
| `CROWDSEC_READ_TIMEOUT` | `20` | Seconds to wait for the LAPI to answer, clamped to 1-120. Raise it on a busy or large LAPI |
| `CROWDSEC_ALERT_LIMIT` | `500` | How many of the most recent alerts to read. `0` reads every alert, which is slow on a large LAPI. Traefik Manager passes its own **Alert limit** as `?limit=` when reading this agent's alerts, so a non-blank, non-zero setting there overrides this. This value applies when that setting is blank or `0` |

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

::: warning
Do not point multiple servers (Host or agents) at the same repository and branch - they push to the same file paths and will overwrite each other. Use a separate repository or a distinct `GIT_BACKUP_BRANCH` per server (e.g. `agent-vps1`). See [Git Repository Backup](git-backup.md).
:::

::: tip Prefer Host-managed backup
Instead of configuring `GIT_BACKUP_*` on every agent, enable **Use Host Repository** in Settings - Backups - Git while the agent is active: the Host pushes the agent's config to its own repository on a per-agent branch, using the Host's credentials.
:::

### Agent server

| Variable | Default | Description |
|---|---|---|
| `TMA_PORT` | `8090` | Listening port |
| `TMA_RATE_LIMIT` | `300` | Requests per minute per IP on `/api/` (0 = disabled) |
| `TMA_DEBUG` | `false` | Log each failed Traefik API call (request URL and returned status) to the journal. Turn it on when a tab shows "could not load" and you need to see why, for example a `401` from an authenticated API |

`TMA_PORT` and `TMA_RATE_LIMIT` can also be set in **Settings - Agents - gear icon - Configure manually**, along with the paths, restart method and git backup fields. The generated Docker Compose only includes them when you enter a non-default value. Saving there rewrites the compose text only: the running agent keeps its current values until it is redeployed or reconfigured with `tm reconfigure`.

### Domains (TM-side, not an env var)

The **Domains** field in Settings - Agents (Traefik tab) is TM-side configuration - it is not passed to the agent container. It tells TM which domains are available on this agent when creating or editing routes. Enter one or more domains separated by commas (e.g. `example.com, example.net`). Domains found in the agent's existing routes are added to the route form automatically, so this field is optional seeding. With no configured domains and no routes to detect them from, the Subdomain field becomes a free-form Hostname field.

## Storage

Agent registrations (name, URL, encrypted API key, and configuration) live in `agents.yml`, in the same config directory as `manager.yml` (default `/app/config/agents.yml`). The file is created when the first agent is added. Upgrading from a version before v1.5.0 migrates agents from `manager.yml` to `agents.yml` on first start, with no manual action.

Back up `agents.yml` alongside `manager.yml` to preserve agent registrations.

Removing an agent also deletes the state the Host kept for it, all of it on the Traefik Manager server:

| What | Where |
|---|---|
| The Host's clone of the agent's config | `{BACKUP_DIR}/git-agent-<id>` (the Host's `BACKUP_DIR`) |
| Its disabled-route snapshots | `manager.yml`, `disabled_routes` keys starting `agent_<id>::` |
| Its managed-middleware and transport entries | `manager.yml`, `managed_middlewares` keys starting `agent_<id>::` |

The agent service on the remote machine keeps running, and a branch already pushed to the git remote is left alone.

## Failure reporting

An agent answers Traefik Manager before it finishes the work behind the request, so a git push or
a Traefik restart can fail after the reply has already gone. The agent records those on its own
side and the Host collects them:

| What | Behaviour |
|---|---|
| Where they are kept | A ring of the 100 most recent events on the agent, read back through `GET /api/events` |
| How they arrive | The Host polls every agent every two minutes and raises what it has not seen, up to ten per cycle |
| Where they show up | Notifications under the **Agents** category, prefixed with the agent's name |
| What is reported | Failed git pushes, failed Traefik restarts, failed backups, and unwritable directories |

At startup the agent also probes its config directory, its `BACKUP_DIR` and, when set, its static
config path. Anything it cannot write is logged and raised as an event, so a bad mount is visible
before it costs you a config write.

## Security

- The API key is the only credential - keep it secret and use HTTPS between TM and TMA
- TM verifies the agent's TLS certificate on every call and has no skip-verify for the TM to agent hop. A self-signed or private-CA certificate fails the health check, the routes fetch and proxied calls with `TLS verification failed - the agent certificate is not trusted by Traefik Manager`. Use a publicly trusted certificate, or add your CA to the TM container's trust store
- Put TMA behind a reverse proxy (Traefik itself) with TLS for production use
- `TMA_RATE_LIMIT` defaults to 300 req/min because TM makes many API calls per tab switch; lower it only if you need to restrict access
- The `/health` endpoint is public (no auth required) - use it for uptime monitoring

## Updating

With `tm`, which also picks up agents installed by the old `setup.sh`:

```bash
tm update
```

Manually:

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

With `GIT_BACKUP_ENABLED=true` the agent runs its own git backup cycle from its `GIT_BACKUP_*` env vars. There is no agent git configuration in the TM Settings UI - the Settings - Agents wizard generates the Docker Compose with those env vars pre-filled from your answers.

With an agent active, Settings - Backups shows that agent's backup data:

- **Dynamic Config** - lists and restores the agent's local `.bak` files, named `filename.YYYYMMDD_HHMMSS.bak` under `<BACKUP_DIR>/backups`. "Create Backup" backs up all config files at once.
- **Git** - the agent's git history and status, with manual push and git restore. The configuration fields are hidden, since env vars on the agent own them.
- **Static Config** - shown when the agent has `STATIC_CONFIG_PATH` configured; lists and restores the agent's `traefik.yml` backups.

See [API Reference - Agent](api-agent.md) for the full endpoint list.

## Troubleshooting

**Switched to an agent but the Routes/Services tabs are empty ("No routes found")**

This almost always means the agent container can reach Traefik Manager, but the **agent itself cannot reach its Traefik API**. Routes from the Docker, Kubernetes and other providers come from the Traefik API, so if `TRAEFIK_API_URL` is wrong or unreachable from inside the agent container, those routes all disappear. The Routes tab shows a banner with the exact connection error (e.g. `traefik unavailable at http://traefik:8080: connection refused`).

Check the agent's `TRAEFIK_API_URL`:

- It must be reachable **from inside the agent container**. `http://traefik:8080` only works when the agent shares Traefik's Docker network; from a different host or network, point it at the Traefik API's reachable address.
- Traefik's API must be enabled (`--api=true`) and listening where the URL points.
- Test it from the agent host: `docker exec <agent-container> wget -qO- http://traefik:8080/api/http/routers` - it should return JSON.

For HTTPS Traefik API URLs with a self-signed or Cloudflare Origin certificate, set `TRAEFIK_INSECURE_SKIP_VERIFY=true`.

**The Traefik API is behind basic auth (returns `401`)**

If your Traefik API sits behind a `basicAuth` middleware or a protected dashboard route, every agent call comes back `traefik returned status 401` and the tabs show "could not load". Either point `TRAEFIK_API_URL` at the internal, unauthenticated API (usually `http://localhost:8080` with `api.insecure: true` bound to localhost, on the same host as Traefik), or keep the authenticated URL and give the agent credentials:

```
TRAEFIK_API_USER=youruser
TRAEFIK_API_PASSWORD=yourpassword
```

The setup wizard also asks for these when you tell it the Traefik API is behind basic auth. **Settings - Agents - gear icon - Configure manually - Traefik** has a matching **Traefik API basic auth** username and password pair, which writes `TRAEFIK_API_USER` and `TRAEFIK_API_PASSWORD` into the generated compose. The password is redacted when the form is read back, and saving there only rewrites the compose text - redeploy or run `tm reconfigure` on the agent to apply it.

**Switched to an agent and got an "is offline" toast**

Switching to an agent that is down names the reason it reported, or says it is not responding. If a route load fails, the Routes and Middlewares grids are emptied and a banner names the server, so nothing on screen belongs to the previous server. Rotate the key from **Settings - Agents - gear icon** if the key is being rejected.

**Viewing the agent's logs (binary install)**

The binary install runs the agent as a systemd service, so its output is in the journal, not a file:

```bash
sudo journalctl -u tma -n 200 --no-pager
sudo journalctl -u tma -f
```

By default the agent logs its startup line, fatal errors and background failures (git push, Traefik restart, pre-write backup). Per-request failures are returned to the Manager instead. Set `TMA_DEBUG=true` to log each failed Traefik API call (URL and status), then reproduce the error. The startup line also shows the active config, e.g. `traefik=http://localhost:8080, insecure-tls=false, traefik-auth=true, debug=true`.
