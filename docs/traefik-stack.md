# Traefik Stack

Install Traefik and Traefik Manager with a single interactive command. The script asks what you want to install and how, then generates all required config files and starts the services.

```bash
curl -fsSL https://get-traefik.xyzlab.dev | bash
```

## Install modes

The first thing the script asks is what you want to install:

```
What would you like to install?
  1) Traefik + Traefik Manager (full stack)
  2) Traefik Manager only
```

If you choose **Traefik Manager only**, it then asks how to deploy it:

```
Deployment method
  1) Docker
  2) Linux service (systemd)
```

---

## Mode 1 - Traefik + Traefik Manager (full stack)

Installs both Traefik and Traefik Manager via Docker Compose. Best for a fresh server with nothing running yet.

### Prerequisites

- A Linux server (Debian/Ubuntu, RHEL/Fedora, or Arch)
- A domain name with DNS pointing to your server
- Ports 80 and 443 open for internet-facing deployments

### What the script configures

**Deployment type**

- **External** - internet-facing, requires ports 80/443 open and DNS A records
- **Internal** - LAN, VPN, or Tailscale only

**Domain**

Your base domain and subdomains for:
- Traefik dashboard (default: `traefik.yourdomain.com`)
- Traefik Manager (default: `manager.yourdomain.com`)

**TLS / Certificates**

| Option | Description |
|---|---|
| Let's Encrypt - HTTP challenge | Port 80 must be open. Simplest for most setups. |
| Let's Encrypt - DNS: Cloudflare | Requires a Cloudflare API token. Works without port 80. |
| Let's Encrypt - DNS: Route 53 | Requires AWS access key and secret. |
| Let's Encrypt - DNS: DigitalOcean | Requires a DigitalOcean API token. |
| Let's Encrypt - DNS: Namecheap | Requires Namecheap API user and key. |
| Let's Encrypt - DNS: DuckDNS | Requires a DuckDNS token. |
| No TLS (HTTP only) | Port 80 only. Suitable for internal LAN use. |

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
| Traefik static config (`traefik.yml`) | No | Plugins tab in Traefik Manager |

### Directory structure

```
~/traefik-stack/
- docker-compose.yml
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
```

### DNS records

Create A records before running the script so Let's Encrypt can issue certificates:

```
traefik.yourdomain.com  A  <server-ip>
manager.yourdomain.com  A  <server-ip>
```

### Updating

```bash
cd ~/traefik-stack
docker compose pull
docker compose up -d
```

### Useful commands

```bash
cd ~/traefik-stack
docker compose logs -f traefik-manager
docker compose down
docker compose restart
```

---

## Mode 2 - Traefik Manager only (Docker)

Installs just Traefik Manager as a Docker container. Use this when Traefik is already running on your server.

### What the script configures

**Network**

- Connect to an existing Traefik Docker network (e.g. `traefik-net`) or create a new one

**Access**

- **Via Traefik labels** - expose Traefik Manager through your existing Traefik instance with a domain and TLS
- **Direct port** - expose a host port (default: 5000) without needing Traefik labels

**Dynamic config** and **optional mounts** - same options as the full stack mode, but you provide the paths to your existing Traefik files on the host.

### Directory structure

```
~/traefik-manager/
- docker-compose.yml
- config/
  - dynamic.yml          (or config directory)
- backups/
```

### Updating

```bash
cd ~/traefik-manager
docker compose pull
docker compose up -d
```

---

## Mode 3 - Traefik Manager only (Linux service)

Installs Traefik Manager as a native systemd service. No Docker required. Use this when you are running Traefik natively or prefer not to use containers.

### Prerequisites

- Python 3.11 or newer
- `git`
- `systemd`

### What the script configures

- **Install directory** - where the app is cloned (default: `/opt/traefik-manager`)
- **Data directory** - where config and backups are stored (default: `/var/lib/traefik-manager`)
- **Port** - default: 5000
- **Dedicated system user** - creates a `traefik-manager` system user to run the service (recommended)
- **Dynamic config** - path to your Traefik `dynamic.yml` or config directory
- **Optional mounts** - paths to `acme.json`, `access.log`, and `traefik.yml` on the host

The script clones the repository, creates a Python venv, installs dependencies, writes a systemd unit file, and enables the service.

### Useful commands

```bash
sudo systemctl status traefik-manager
sudo journalctl -u traefik-manager -f
sudo systemctl restart traefik-manager
```

### Updating

```bash
cd /opt/traefik-manager
git pull
venv/bin/pip install -q -r requirements.txt gunicorn
sudo systemctl restart traefik-manager
```

---

## First login

Once the script completes it prints a temporary password:

```
Temporary password  abc123xyz
```

If it is not shown, retrieve it from the logs:

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

Log in with the temporary password. On your next login you will be redirected to a forced password-change screen before you can access the dashboard.
