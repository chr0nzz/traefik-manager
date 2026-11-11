# tm CLI

Install Traefik and Traefik Manager with a single interactive command. It installs `tm`, a CLI that asks what you want to install and how, generates all required config files, starts the services, and manages the install afterwards.

```bash
curl -fsSL https://get-traefik.xyzlab.dev | bash
```

`tm` lands in `/usr/local/bin`. Re-running the one-liner updates `tm` and opens `tm install`, which detects an existing install and offers to update or reconfigure it. Installs made by the old `setup.sh` are adopted automatically: run any `tm` command in the install directory (or pass `--dir`) for Docker installs; the Linux service and binary agent are picked up by any `tm` command when no Docker install is found, or by `tm install` with the same mode. Their secrets stay where they are until the first `tm reconfigure`, which moves them to `.env` (or the agent env file for the binary agent).

## Managing the install

| Command | What it does |
|---|---|
| `tm status` | Mode, directory, services, URLs, health, release channel |
| `tm update` | Pulls images, `git pull`, or downloads the agent binary, then restarts. On a Linux service install it skips reinstalling dependencies and rebuilding assets when git reports no change, `--force` does it anyway. `--channel beta` and `--channel stable` switch release channel, see [Beta releases](beta.md) |
| `tm logs [service]` | Follows the logs (`--no-follow`, `-n <lines>`) |
| `tm restart`, `tm start`, `tm stop` | Whole install, or one service |
| `tm password` | Prints the temporary password from the logs |
| `tm reconfigure [--section <id>]` | Re-runs the wizard pre-filled, regenerates the files it wrote, restarts (`--list` shows the sections) |
| `tm add crowdsec` | Adds CrowdSec to an existing install |
| `tm doctor` | Checks Docker, ports, DNS, `acme.json`, health endpoints, CrowdSec |
| `tm uninstall` | Stops the services and removes the files tm wrote, keeping any you changed. `--purge` also removes configs, data and volumes |
| `tm uninstall --self` | Removes `tm` itself. Any installs keep running, they just stop being managed |
| `tm self-update` | Updates `tm` itself |

Commands find the install from `--dir` or `TM_DIR`, then the current directory, then the installs `tm` already knows about.

### Removing tm

`tm uninstall` removes an install, not the CLI. To remove `tm` itself:

```bash
tm uninstall --self
```

It names any installs it still knows about first, since those keep running and serving traffic without it. Uninstall them first if that was the intent.

| Mode | Secrets | tm's record of the install |
|---|---|---|
| Docker modes | `<install dir>/.env` (mode 600) | `<install dir>/.tm/state.yml` |
| Linux service | - | `/etc/traefik-manager/tm-state.yml` |
| Binary agent | `/etc/traefik-manager-agent/env` | `/etc/traefik-manager-agent/tm-state.yml` |

### Non-interactive install

`tm install --answers answers.yml --yes` runs without prompts. `tm install --dump-answers answers.yml` writes the answers of a wizard run (no secrets) to start from, and `--dry-run` renders every file without starting anything. Secrets come from environment variables of the same name (`TMA_API_KEY`, `CF_DNS_API_TOKEN`, ...) or a `secrets:` map in the file. Schema and examples: [tm CLI README](https://github.com/chr0nzz/tm-cli#non-interactive).

## Install modes

The first question is what to install:

```
What would you like to install?
  1) Traefik + Traefik Manager (full stack)
  2) Traefik Manager only
  3) Traefik Manager Agent
```

**Traefik + Traefik Manager** and **Traefik Manager only** then both ask how to deploy:

```
Deployment method
  1) Docker
  2) Linux service (systemd)
```

| Answer | Mode | Documented as |
|---|---|---|
| Full stack, Docker | `full` | [Mode 1](#mode-1-traefik-traefik-manager-full-stack) |
| Full stack, Linux service | `full-native` | [Mode 2](#mode-2-traefik-traefik-manager-linux-services) |
| Traefik Manager only, Docker | `tm-docker` | [Mode 3](#mode-3-traefik-manager-only-docker) |
| Traefik Manager only, Linux service | `tm-native` | [Mode 4](#mode-4-traefik-manager-only-linux-service) |
| Traefik Manager Agent | `agent-docker`, `agent-docker-traefik`, `agent-binary` | [Mode 5](#mode-5-traefik-manager-agent) |

`tm install --mode <mode>` skips the menus, taking any mode above, or `agent` to pick only the agent method.

---

## Mode 1 - Traefik + Traefik Manager (full stack)

Installs both via Docker Compose. Best for a fresh server with nothing running yet.

### Prerequisites

- A Linux server (amd64 or arm64 - the container images are built for those two; only the standalone agent binary is built for armv7). Docker is installed for you on Debian/Ubuntu, RHEL/Fedora and Arch; anything else falls back to the `get.docker.com` script.
- A domain name with DNS pointing to your server
- Ports 80 and 443 open for internet-facing deployments (and 443/udp with HTTP/3)

### Sections and review screen

The setup runs through numbered sections (General, Deployment type, Domain, TLS / Certificates, Dynamic config, Optional mounts, CrowdSec, Docker network). After the last one a review table summarizes every answer:

```
  Review configuration
  ────────────────────────────────────────────────────────
   1  General             ~/traefik-stack
   2  Deployment type     external (internet-facing)
   3  Domain              example.com  dash:traefik.example.com  tm:manager.example.com
   4  TLS / Certificates  Let's Encrypt DNS (cloudflare)  you@example.com
   5  Dynamic config      Directory
   6  Optional mounts     logs certs static(restart:proxy)
   7  CrowdSec            install alongside
   8  Docker network      traefik-net  api:8080
  ────────────────────────────────────────────────────────

  Edit a section, or Continue
```

Pick a section to answer it again, or Continue to install. Nothing is written to disk until you continue.

### What the wizard configures

**Install directory** - where all files are created (default: `~/traefik-stack`)

**Deployment type**

- **External** - internet-facing, requires ports 80/443 open and DNS A records
- **Internal** - LAN, VPN, or Tailscale only

**Domain**

Your base domain and subdomains for:
- Traefik dashboard (default: `traefik.yourdomain.com`)
- Traefik Manager (default: `manager.yourdomain.com`)
- Whether to enable the Traefik API dashboard UI

**TLS / Certificates**

| Option                            | Requires                                                |
| -----------------------------------| ---------------------------------------------------------|
| Let's Encrypt - HTTP challenge    | Port 80 open. Simplest for most setups.                 |
| Let's Encrypt - DNS: Cloudflare   | A Cloudflare API token. Works without port 80.          |
| Let's Encrypt - DNS: Route 53     | AWS access key, secret, and region.                     |
| Let's Encrypt - DNS: DigitalOcean | A DigitalOcean API token.                               |
| Let's Encrypt - DNS: Namecheap    | Namecheap API user and key.                             |
| Let's Encrypt - DNS: DuckDNS      | A DuckDNS token.                                        |
| Let's Encrypt - DNS: deSEC        | A deSEC token. Works without port 80.                   |
| No TLS (HTTP only)                | Port 80 only. Suitable for internal LAN use.            |

**HTTP/3** - with TLS on, the wizard also asks **Enable HTTP/3 (QUIC)?**, off by default (`tls.http3` in an answers file). Yes adds `http3: {}` to the `websecure` entrypoint, publishes `443:443/udp` next to `443:443`, and adds `443/udp` to the firewall notice. Open 443/udp in any firewall in front of the server. See [HTTP/3](static.md#http3).

**Dynamic config layout**

| Option | Description |
|---|---|
| Single file (`dynamic.yml`) | All routes in one file. Simpler to start with. |
| Directory (one `.yml` per service) | One file per service. Easier to manage at scale. |

**Optional mounts**

| Mount | Default | Enables |
|---|---|---|
| Access logs | Yes | Logs tab in Traefik Manager |
| SSL certs (`acme.json`) | Yes | Certs tab in Traefik Manager |
| Traefik static config (`traefik.yml`) | No | Plugins tab + Static Config editor |
| Certificate removal | No | Mounts `acme.json` read-write so the Certs tab can remove certificates. Asked when certs are mounted |

**Docker network** - network name (default: `traefik-net`) and Traefik internal API port (default: `8080`)

**Static config editor** - enabling the static config mount also asks which restart method to use (socket proxy, poison pill, or direct socket). `tm` then writes every required compose addition - socket proxy service, shared signal volume, Traefik healthcheck, env vars on TM - so the editor works out of the box. It covers entrypoints, certificate resolvers, providers, plugins, API, logging, observability and system settings, plus a raw YAML editor for anything else. See [Static Config Editor](static.md).

**Certificate removal** - asks for the same restart method when the static config editor is off. See [Removing a certificate](tab-certs.md#removing-a-certificate).

For an existing install that skipped it:

- **`tm reconfigure --section mounts`** - answer the static config questions differently. `docker-compose.yml` is regenerated from your answers; config files and backups are preserved. If you edited the compose file by hand, `tm` asks before overwriting it and keeps a backup.
- **Enable manually** - see [Enable static config editor](static-enable.md) to add only the volume, env vars, and restart method to your existing compose.

**CrowdSec IDS**

| Option | What happens |
|---|---|
| Install as part of this stack | Adds a `crowdsec` service, generates a random bouncer API key, writes `crowdsec/acquis.yaml` pointing at the Traefik access log, and sets `CROWDSEC_LAPI_URL` + `CROWDSEC_API_KEY` on Traefik Manager. |
| Connect to existing instance | Prompts for the LAPI URL and bouncer key of a CrowdSec instance you already run, plus optional machine credentials for alerts and unban. No new service is added. |

Choosing the install option turns the access log mount on automatically - CrowdSec needs it. Both options then ask for the alert limit (0 to 100000, default 500), which becomes `CROWDSEC_ALERT_LIMIT`.

Once installed, enable the **CrowdSec** tab under **Settings → System Monitoring → Tab Visibility** to view active decisions, recent alerts, and unban IPs.

### CrowdSec bouncer plugin

CrowdSec on its own detects. The bouncer is what blocks. After the CrowdSec questions `tm` offers to install the [Traefik bouncer plugin](https://github.com/maxlerebourg/crowdsec-bouncer-traefik-plugin):

| What | Detail |
|---|---|
| Offered when | CrowdSec is set to install or connect, and `tm` can write `traefik.yml`: this mode and the agent with Traefik, or any other mode with the static config mount set |
| Declares | `experimental.plugins.crowdsec`, module `github.com/maxlerebourg/crowdsec-bouncer-traefik-plugin`, version `v1.7.1` |
| Writes | A `crowdsec` middleware in your dynamic config: `crowdsec.yml` in a config directory, or inlined in a single-file layout |
| Middleware holds | `CrowdsecMode: live`, the LAPI scheme and host, and the bouncer key in plain text. Keep that file with the rest of your Traefik config |
| Backup | An existing `traefik.yml` is copied to `traefik.yml.tm.bak` before the plugin block is added |

`tm` never attaches the middleware to a router. Nothing is blocked until you add it yourself:

```yaml
  middlewares:
    - crowdsec@file
```

Two things worth knowing:

- If the plugin is already declared in `traefik.yml` under another alias, `tm` reuses it and changes nothing.
- On an install where `tm` did not write `traefik.yml`, the plugin trusts the forwarded headers your entrypoints already trust. When none are set, the bouncer sees the address Traefik connects from and bans that instead of the real client. Set `forwardedHeaders.trustedIPs` on the entrypoint, then run `tm reconfigure`.

### Directory structure

```
~/traefik-stack/
- docker-compose.yml
- .env                   (secrets, mode 600)
- .tm/
  - state.yml            (tm's record of the install)
- traefik/
  - traefik.yml
  - acme.json
  - logs/
    - access.log
  - config/
    - dynamic.yml        (single file layout)
    - *.yml              (directory layout)
- traefik-manager/
  - config/
  - backups/
- crowdsec/              (only if CrowdSec install mode chosen)
  - acquis.yaml
```

### DNS records

Create A records before running `tm install` so Let's Encrypt can issue certificates:

```
traefik.yourdomain.com  A  <server-ip>
manager.yourdomain.com  A  <server-ip>
```

### Updating

| Option | Command |
|---|---|
| `tm` | `tm update` |
| Manual | `cd ~/traefik-stack && docker compose pull && docker compose up -d` |

### Useful commands

```bash
tm status
tm logs traefik-manager
tm doctor
tm password
tm restart
tm stop
```

Or directly with Compose from `~/traefik-stack`: `docker compose logs -f traefik-manager`, `docker compose down`, `docker compose restart`.

---

## Mode 2 - Traefik + Traefik Manager (Linux services)

Installs Traefik and Traefik Manager as systemd services on the host. No Docker anywhere. Use this on a server that does not run containers, or where Traefik should be an ordinary system service.

### Prerequisites

- Python 3.11 or newer, with the `venv` module (`sudo apt install python3-venv` on Debian and Ubuntu). `tm` checks for it before installing anything
- `git`, `curl`
- `systemd`
- amd64, arm64 or armv7. `tm` downloads the Traefik release for that architecture
- `sudo`, for the units, the service user, `/usr/local/bin/traefik`, `/etc/traefik`, `/var/lib/traefik` and `/var/log/traefik`

`tm` refuses to install when the host already has a `traefik.service` it did not write. Install Traefik Manager beside it with `--mode tm-native` instead.

### Sections and review screen

Seven sections: General, Deployment type, TLS / Certificates, Domain, Dynamic config, Static config editor, CrowdSec.

```
  Review configuration
  ────────────────────────────────────────────────────────
   1  General              /opt/traefik-manager  data:/var/lib/traefik-manager  tm::5000  api::8080
   2  Deployment type      external (internet-facing)
   3  TLS / Certificates   Let's Encrypt HTTP challenge  you@example.com
   4  Domain               example.com  dash:traefik.example.com
   5  Dynamic config       Single file
   6  Static config editor static editor on (restart:poison-pill)  cert removal on
   7  CrowdSec             install (CrowdSec package)  bouncer plugin
  ────────────────────────────────────────────────────────

  Edit a section, or Continue
```

Nothing is written to disk until you pick Continue.

### What the wizard configures

| Section | Asks |
|---|---|
| General | Install directory (default `/opt/traefik-manager`), data directory (default `/var/lib/traefik-manager`), Traefik Manager port (default `5000`), Traefik internal API port (default `8080`) |
| Deployment type | External (internet-facing) or internal only (LAN, VPN, Tailscale) |
| TLS / Certificates | Same choices as mode 1: Let's Encrypt HTTP or DNS challenge, or no TLS. With TLS on, also whether to enable [HTTP/3](static.md#http3), which makes Traefik listen on 443/udp as well |
| Domain | Optional. Leave it empty for no dashboard route. Otherwise the dashboard subdomain (default `traefik.<domain>`) and whether to serve the Traefik dashboard UI |
| Dynamic config | Single file (`/etc/traefik/dynamic/dynamic.yml`) or directory (`/etc/traefik/dynamic`). The paths are fixed |
| Static config editor | Whether Traefik Manager may edit `/etc/traefik/traefik.yml`. With TLS on it also offers certificate removal |
| CrowdSec | Install the CrowdSec package on this server, or connect to an existing instance |

There is no restart method question. Either answer in the Static config editor section installs a `traefik-restart.path` watcher: Traefik Manager writes `/var/lib/traefik-manager/signals/restart.sig` and the watcher restarts Traefik. No Docker socket is involved.

Unlike mode 1, Traefik Manager itself gets no hostname and no Traefik route. Reach it at `http://<server-ip>:5000`.

### What tm installs

- Downloads the latest Traefik release for this architecture, verifies its SHA-256, and installs `/usr/local/bin/traefik`. The version is recorded so `tm update` can compare
- Creates the `traefik-manager` system user. Traefik and Traefik Manager both run as it, which is what makes certificate removal work here: `acme.json` stays mode 600 and is owned by the user that writes it
- Writes `traefik.service` (with a systemd watchdog) and `traefik-manager.service`, plus `traefik-restart.path` and `traefik-restart.service` when a restart is needed
- Adds `/etc/logrotate.d/traefik`, rotating the access log daily and keeping 14

### Directory structure

```
/usr/local/bin/traefik         (binary, .prev kept after an update)
/etc/traefik/
- traefik.yml                  (static config)
- dynamic/
  - dynamic.yml                (single file layout)
  - *.yml                      (directory layout)
/var/lib/traefik/
- acme.json                    (certificates, mode 600)
- plugins-storage/
/var/log/traefik/
- access.log
/opt/traefik-manager/          (the app, a git clone and its venv)
/var/lib/traefik-manager/
- manager.yml
- backups/
- signals/
/etc/traefik-manager/
- env                          (secrets, mode 600)
- tm-state.yml                 (tm's record of the install)
/etc/systemd/system/
- traefik.service
- traefik-manager.service
- traefik-restart.path
- traefik-restart.service
```

### Useful commands

```bash
tm status
tm logs
tm logs traefik
tm doctor
tm password
tm restart
```

`tm restart` restarts both services; `tm restart traefik` takes one. With systemd directly: `sudo systemctl status traefik traefik-manager`, `sudo journalctl -u traefik-manager -f`.

### Updating

`tm update` pulls the app as the `traefik-manager` user, reinstalls dependencies, rebuilds the assets and restarts the service. It then checks for a newer Traefik release, keeps the old binary as `traefik.prev`, and rolls back to it if Traefik stops answering `/ping` within 30 seconds.

### Uninstalling

`tm uninstall` stops and removes the units, the Traefik binary and the install directory. It keeps `/etc/traefik`, `/var/lib/traefik`, `/var/log/traefik` and the data directory, so routes, certificates and logs survive. `tm uninstall --purge` removes those too and deletes the service user. An installed CrowdSec package is always left in place.

### What this mode does not do

| Not available | Instead |
|---|---|
| Traefik Manager behind Traefik with TLS | Reach it on its port, or add a route yourself |
| Docker provider, container label routing | The file provider only |
| A choice of restart method | Always the signal file watcher |
| Configurable config, log and certificate paths | The paths above are fixed |
| Several installs on one host | One, at fixed unit names and a fixed state file |

---

## Mode 3 - Traefik Manager only (Docker)

Installs just Traefik Manager as a Docker container. Use this when Traefik is already running on your server.

### Sections and review screen

Numbered sections (General, Network, Access, Dynamic config, Optional mounts) end with the same review table as the other modes:

```
  Edit a section, or Continue
```

### What the wizard configures

**Install directory** - default: `~/traefik-manager`

**Network** - connect to an existing Traefik Docker network (default: `traefik-net`) or create a new one (default: `traefik-manager-net`)

**Access**

- **Via Traefik labels** - expose Traefik Manager through your existing Traefik instance with a domain and TLS certificate (same TLS options as full stack mode)
- **Direct port** - expose a host port (default: 5000), no Traefik labels needed

**Dynamic config layout** - single file or directory, same options as the full stack mode

**Optional mounts** - you provide the host paths to your existing Traefik files:

| Mount | Default | Path asked |
|---|---|---|
| Access logs | Yes | Path to Traefik access log (default: `/var/log/traefik/access.log`) |
| SSL certs (`acme.json`) | Yes | Path to `acme.json` (default: `/etc/traefik/acme.json`) |
| Traefik static config | No | Path to `traefik.yml` (default: `/etc/traefik/traefik.yml`) |
| Certificate removal | No | Asked when certs are mounted. Mounts `acme.json` read-write |

**Static config editor** - mounting the static config or allowing certificate removal also asks for the restart method (socket proxy, poison pill, or direct socket) and the Traefik container name (default: `traefik`).

To add static config support later, either run `tm reconfigure --section mounts` (regenerates the compose file, preserving config and backups) or follow [Enable static config editor](static-enable.md).

**CrowdSec IDS**

| Option | What happens |
|---|---|
| Install alongside Traefik Manager (container) | Adds a `crowdsec` service, asks for the Traefik access log path and turns that mount on, generates a bouncer key, writes `crowdsec/acquis.yaml`, and sets `CROWDSEC_LAPI_URL` + `CROWDSEC_API_KEY` |
| Connect to existing instance | Asks for the LAPI URL and bouncer key, plus optional machine credentials for alerts and unban |

Both ask for the alert limit. The bouncer plugin is offered only when the static config mount is on, since the plugin is declared in `traefik.yml`. See [the bouncer plugin](#crowdsec-bouncer-plugin) under mode 1.

To add CrowdSec to an existing install, run `tm add crowdsec`.

### Directory structure

```
~/traefik-manager/
- docker-compose.yml
- .env                   (secrets, mode 600, only when there are any)
- .tm/
  - state.yml            (tm's record of the install)
- config/
  - dynamic.yml          (or config directory)
- backups/
```

### Updating

| Option | Command |
|---|---|
| `tm` | `tm update` |
| Manual | `cd ~/traefik-manager && docker compose pull && docker compose up -d` |

### Useful commands

```bash
tm status
tm logs
tm doctor
tm password
```

---

## Mode 4 - Traefik Manager only (Linux service)

Installs Traefik Manager as a native systemd service. No Docker required. Use this when you run Traefik natively or prefer not to use containers.

### Prerequisites

- Python 3.11 or newer, with the `venv` module (`sudo apt install python3-venv` on Debian and Ubuntu). `tm` checks for it before installing anything
- `git`, `curl`
- `systemd`

### Sections and review screen

Numbered sections (General, Service user, Dynamic config, Optional mounts) end with the same review table as the other modes:

```
  Edit a section, or Continue
```

### What the wizard configures

- **Install directory** - where the app is cloned (default: `/opt/traefik-manager`)
- **Data directory** - config and backups (default: `/var/lib/traefik-manager`)
- **Port** - default: 5000
- **Dedicated system user** - creates a `traefik-manager` system user to run the service (recommended)
- **Dynamic config layout** - single file (default: `/etc/traefik/dynamic.yml`) or directory (default: `/etc/traefik/conf.d`)

**Optional mounts** - asks for host paths to each:

| Mount | Default | Path asked |
|---|---|---|
| SSL certs (`acme.json`) | Yes | Path to `acme.json` (default: `/etc/traefik/acme.json`) |
| Access logs | Yes | Path to Traefik access log (default: `/var/log/traefik/access.log`) |
| Traefik static config | No | Path to `traefik.yml` (default: `/etc/traefik/traefik.yml`) |

**Static config editor** - mounting the static config asks how Traefik itself runs on this server:

| Traefik runs as | Restart method |
|---|---|
| Docker | Poison pill (recommended - signal file, no Docker socket) or direct Docker socket, which puts the `traefik-manager` user in the `docker` group. Direct socket also asks for the container name (default: `traefik`). |
| Linux service (systemd) | Poison pill only. `tm` installs a `traefik-restart.path` unit that restarts your Traefik service (default name: `traefik`) when the signal file appears. |

Poison pill asks for the signal file path (default: `/var/lib/traefik-manager/signals/restart.sig`).

Certificate removal is not offered in this mode. The service runs as a different user than Traefik, and Traefik refuses an `acme.json` that another user can write. Use a Docker mode for it.

To add static config support later, either run `tm reconfigure --section mounts` (regenerates the systemd unit and restarts the service) or follow [Enable static config editor](static-enable.md) to add the env vars by hand.

**CrowdSec IDS**

| Option | What happens |
|---|---|
| Install on this server (CrowdSec package) | Installs the CrowdSec package (the distro package on Arch, the CrowdSec repo script elsewhere), enables `crowdsec.service`, installs the `crowdsecurity/traefik` collection, registers a `traefik-manager` bouncer and a machine, and writes `/etc/crowdsec/acquis.d/traefik.yaml` pointing at your access log |
| Connect to existing instance | Asks for the LAPI URL and bouncer key, plus optional machine credentials for alerts and unban |

Both ask for the alert limit. Credentials go to `/etc/traefik-manager/env` (mode 600), the rest into the unit as `Environment=`.

The LAPI listens on `127.0.0.1:8080`. To move it, set `crowdsec.lapi_port` in an answers file: the wizard does not ask for it. `tm` then writes `/etc/crowdsec/config.yaml.local` and `/etc/crowdsec/local_api_credentials.yaml.local` with that port. It refuses a port already in use, or one that clashes with the Traefik Manager port.

The bouncer plugin is offered only when the static config mount is on. In a single-file dynamic config `tm` does not write the middleware, because it did not create that file: it prints the YAML for you to paste. See [the bouncer plugin](#crowdsec-bouncer-plugin) under mode 1.

`tm uninstall` removes the acquis file and leaves the CrowdSec package installed.

`tm` clones the repository, creates a Python venv, installs dependencies, builds the vendor assets and CSS, writes the systemd unit, and enables the service. Its record of the install is `/etc/traefik-manager/tm-state.yml`.

### Useful commands

```bash
tm status
tm logs
tm doctor
tm password
tm restart
```

Or with systemd directly: `sudo systemctl status traefik-manager`, `sudo journalctl -u traefik-manager -f`, `sudo systemctl restart traefik-manager`.

### Updating

| Option | Command |
|---|---|
| `tm` | `tm update` |
| Manual | run as the owner of the install directory (`traefik-manager` when a service user was created): `git pull`, `venv/bin/pip install -q -r requirements.txt gunicorn`, `scripts/setup-assets.sh`, then `sudo systemctl restart traefik-manager` |

---

## Mode 5 - Traefik Manager Agent

Installs the [TMA agent](agent.md) on a remote server so a central Traefik Manager can manage it. This mode does not install TM itself.

### Install methods

After choosing **Traefik Manager Agent**, `tm` shows an arrow-key menu:

```
Install method
▸ Docker - Agent only (alongside existing Traefik)
  Docker - Agent + Traefik (deploy both together)
  Binary - Agent only (systemd service, no Docker)
```

Use `↑`/`↓` to move, `Enter` to select, or type a number.

To skip the menus, pass the mode and the agent settings as flags:

```bash
tm install --mode agent-docker --api-key <key> --traefik-url http://traefik:8080
```

### Sections and review screen

```
  Review configuration
  ────────────────────────────────────────────────────────
   1  Install method     Agent only
   2  API key            sk-••••••••
   3  Traefik connection http://traefik:8080
   4  Optional paths     logs
   5  Restart method     none
   6  CrowdSec           disabled
   7  Git backup         disabled
   8  Install location   /opt/traefik-manager-agent  :8090
  ────────────────────────────────────────────────────────

  Edit a section, or Continue
```

Pick a section to answer it again, or Continue to install. The binary method has no **Install location** section, so it shows 7.

### What the wizard asks

**Traefik connection (section 3)**
- Traefik API URL (default: `http://traefik:8080`)
- Dynamic config path (default: `/app/config`)
- Skip TLS verification - shown only when the URL starts with `https://`; sets `TRAEFIK_INSECURE_SKIP_VERIFY` for self-signed or Cloudflare Origin certs
- Traefik API basic auth - username and password, if the API is behind it
- Mount static config (`traefik.yml`) - toggle; if enabled, asks for the path

**Traefik install (Docker - Agent + Traefik only)** replaces section 3
- Enable HTTPS on port 443
- TLS certificate method: Let's Encrypt HTTP challenge, Let's Encrypt Cloudflare DNS, or no TLS
- ACME email (if Let's Encrypt)
- Enable HTTP/3 (QUIC) (if TLS) - adds `http3: {}` to `websecure` and publishes `443:443/udp`
- Cloudflare DNS API token (if Cloudflare DNS)
- Cert resolver name (default: `letsencrypt`)
- Enable Traefik dashboard and hostname
- Docker network name (default: `traefik-net`)

**Optional paths (section 4)** - all off by default
- Mount ACME / certs (default: `/etc/traefik/acme.json`)
- Mount access logs (default: `/var/log/traefik/access.log`)
- Mount plugins directory (default: `/etc/traefik/plugins`)
- Allow certificate removal - asked when acme.json is mounted, or TLS is on for Agent + Traefik. Mounts it read-write

**Restart method (section 5)**
- None, socket proxy, poison pill, or direct Docker socket. None is not offered when certificate removal is on

**CrowdSec (section 6)**

| Option | What it does |
|---|---|
| None | Skip CrowdSec |
| Install alongside agent | Docker methods: adds a `crowdsec` service, generates a bouncer key, writes `crowdsec/acquis.yaml`. Binary method: installs the CrowdSec package, registers a `tma` bouncer, writes `/etc/crowdsec/acquis.d/traefik.yaml`. Requires the access log mount (prompts if not set) |
| Connect to existing | Enter LAPI URL and API key |

All three ask for the alert limit. Agents never get machine credentials, so alerts and unban stay with the Traefik Manager that owns them. On the binary method, `crowdsec.lapi_port` in an answers file moves the LAPI off `8080`, which matters when the agent port or the Traefik API port already uses it.

The bouncer plugin is offered with the agent + Traefik method, or with any method where the static config mount is set. See [the bouncer plugin](#crowdsec-bouncer-plugin) under mode 1.

**Git backup (section 7)** - repo URL, branch, username, token, auto-push toggle

**Install location (section 8, Docker only)** - install directory and agent port (default: `8090`)

### Docker - Agent only output

Generates `docker-compose.yml` with only the env vars and volumes for the options you enabled, puts the API key and other secrets in `.env`, then runs `docker compose up -d`. If CrowdSec install was chosen, adds a `crowdsec` service and writes `crowdsec/acquis.yaml`.

### Docker - Agent + Traefik output

Creates this structure and starts both containers:

```
/opt/traefik-manager-agent/
  docker-compose.yml           (traefik + traefik-manager-agent services)
  .env                         (secrets, mode 600)
  .tm/state.yml                (tm's record of the install)
  backups/
  traefik/
    traefik.yml                (static config - entrypoints, file provider, cert resolver)
    acme.json                  (created empty, chmod 600 - if TLS enabled)
    config/                    (dynamic config dir, shared between Traefik and agent)
    logs/
      access.log
  crowdsec/                    (only if CrowdSec install chosen)
    acquis.yaml
```

Traefik's API port (8080) is not published - the agent reaches it over the internal Docker network (`http://traefik:8080`).

### Binary output

Downloads the `tma` binary from GitHub Releases to `/usr/local/bin/tma`, writes a systemd unit with the non-secret `Environment=` lines and `EnvironmentFile=/etc/traefik-manager-agent/env` for the secrets, then runs `systemctl enable --now tma`.

### Useful commands

Both install methods:

```bash
tm status
tm logs
tm doctor
tm update
tm reconfigure --section apikey
```

**Docker:**
```bash
cd /opt/traefik-manager-agent
docker compose logs -f
docker compose pull && docker compose up -d
```

**Binary:**
```bash
sudo systemctl status tma
sudo journalctl -u tma -f
sudo systemctl restart tma
```

### Next steps after install

1. In TM **Settings → Agents**, click **Add Agent** and choose **Install with the tm CLI**
2. Enter a name and the agent URL (e.g. `http://server-ip:8090`). Traefik Manager mints the key and hands you the whole install command; **Verify connection** checks it once the agent is up. If the agent is already installed with a different key, take the key from that screen and run `tm reconfigure --section apikey`. **Configure manually** is the other path, and prints a compose file instead.
3. Use the **server switcher** in the TM nav bar to switch to this agent

---

## First login

Once `tm install` completes it prints a temporary password:

```
Temporary password  abc123xyz
```

If it is not shown, run `tm password`, or read it from the logs:

:::tabs
== Docker
```bash
docker logs traefik-manager | grep -A3 "AUTO-GENERATED"
```
== Linux service
```bash
sudo journalctl -u traefik-manager | grep -A3 "AUTO-GENERATED"
```
:::

Log in with the temporary password. You are taken straight to the setup wizard, and a forced password-change screen appears as soon as you finish it.
