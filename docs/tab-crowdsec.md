# CrowdSec Tab

The **CrowdSec** tab connects to a CrowdSec Local API (LAPI) and shows active security decisions, recent alerts, and a summary of enforcement activity. You can unban IPs and add manual decisions directly from the tab without touching the CLI.

The tab is optional and must be enabled in Settings or during the setup wizard.

## What it shows

### Stats cards

Six cards at the top of the tab give an at-a-glance summary:

| Card | Description |
|---|---|
| **Total Alerts** | Number of alerts from the LAPI |
| **Active Decisions** | Total active decisions across all types |
| **LAPI Status** | Online / Offline - whether TM can reach the LAPI |
| **Active Bans** | Number of IPs currently blocked |
| **Captchas** | Number of IPs currently served a captcha challenge |
| **Bypasses** | Number of IPs currently whitelisted from enforcement |

### Active Decisions view

The decisions table lists every active (non-expired) decision fetched from the LAPI. All pages are fetched automatically - there is no hard limit.

| Column | Description |
|---|---|
| **IP / Scope** | Source IP address or CIDR range |
| **Type** | Decision type - ban, captcha, or bypass |
| **Origin** | Source of the decision (e.g. `crowdsec`, `CAPI`, blocklist name) |
| **Scenario** | The CrowdSec scenario that triggered the decision |
| **Expires** | Timestamp when the decision expires |
| **Action** | **Unban** button to delete the decision immediately |

Use the **All / Ban / Captcha / Bypass** type filter and the search box to narrow down the list. Results are paginated at 100 rows per page.

#### Adding a manual decision

Click **+ Add Decision** to open the decision form:

- **IP / Range** - single IP or CIDR (e.g. `1.2.3.4` or `10.0.0.0/8`)
- **Type** - Ban, Captcha, or Bypass
- **Duration** - 1h, 4h, 24h, 7 days, 30 days, or 1 year
- **Reason** - optional label stored as the decision scenario

Manual decisions require the bouncer key to have write permissions on the LAPI.

### Recent Alerts view

Switch to **Recent Alerts** using the toggle next to the search box. The alerts table shows events that triggered decisions:

| Column | Description |
|---|---|
| **Time** | When the alert was created |
| **Source IP** | The IP that triggered the alert |
| **Scenario** | The scenario that matched |
| **Decisions** | Number of decisions created from the alert |

## Not configured state

If CrowdSec is not configured, the tab shows a placeholder message with a link to **Settings → System Monitoring → CrowdSec**.

## Enabling the tab

### During setup wizard

Toggle **CrowdSec** on in the "Optional monitoring" step.

### After setup

Go to **Settings → System Monitoring** and enable the CrowdSec toggle.

## Configuration

Settings fields take priority over environment variables.

CrowdSec's LAPI uses **two different credentials** depending on the operation:

| Operation | Credential | Why |
|---|---|---|
| **Decisions** (active bans/captchas/bypasses) | Bouncer API key | Bouncers read the decisions stream |
| **Alerts** + **unban** (delete decision) | Machine login | Bouncer keys get `403 access forbidden` on these endpoints |

The Decisions view works with just the bouncer key. To also see **Alerts** and to unban from the UI, add CrowdSec **machine credentials**. Without them the Alerts section shows `403 access forbidden`.

### Option 1 - Settings UI

Go to **Settings → System Monitoring → CrowdSec** and fill in:

- **LAPI URL** - the base URL of your CrowdSec LAPI (e.g. `http://crowdsec:8080`)
- **API key** - a bouncer API key, reads decisions (see below)
- **Machine Credentials** (optional) - machine ID + password, enables the Alerts view and unban

Values are stored encrypted in `manager.yml`.

### Option 2 - Environment variables

```bash
CROWDSEC_LAPI_URL=http://crowdsec:8080
CROWDSEC_API_KEY=your-bouncer-api-key
# Optional - enables the Alerts view and unban:
CROWDSEC_MACHINE_ID=traefik-manager
CROWDSEC_MACHINE_PASSWORD=your-machine-password
```

### Generating a bouncer API key

```bash
docker exec <crowdsec-container> cscli bouncers add traefik-manager
```

Copy the key that is printed - it is only shown once.

### Generating machine credentials (for Alerts and unban)

```bash
cscli machines add traefik-manager --auto
cat /etc/crowdsec/local_api_credentials.yaml
```

Copy the `login` and `password` from that file into the Machine Credentials fields (or the `CROWDSEC_MACHINE_ID` / `CROWDSEC_MACHINE_PASSWORD` env vars). If the machine shows as unvalidated, run `cscli machines validate traefik-manager`.

> **Compose gotcha**: if the machine password contains a `$`, escape it as `$$` in `docker-compose.yml` - Docker Compose treats a single `$` as a variable reference. No escaping is needed in the Settings UI.

::: tip Why two credentials?
This mirrors CrowdSec's own auth model: `cscli decisions list` uses the bouncer/LAPI path while `cscli alerts list` uses the machine credential. Traefik Manager reads decisions with the bouncer key and alerts with the machine login, so both must be set for the full tab.
:::

## Docker Compose example

```yaml
services:
  crowdsec:
    image: crowdsecurity/crowdsec:latest
    container_name: crowdsec
    networks:
      - proxy

  traefik-manager:
    image: ghcr.io/chr0nzz/traefik-manager:latest
    environment:
      - CROWDSEC_LAPI_URL=http://crowdsec:8080
      - CROWDSEC_API_KEY=your-bouncer-api-key
    networks:
      - proxy

networks:
  proxy:
    external: true
```

::: tip Automated setup
The [traefik-stack installer](traefik-stack.md) can configure CrowdSec automatically during installation. When you choose to install CrowdSec as part of the stack, it generates the bouncer key (for decisions) and also registers a **machine** and wires up `CROWDSEC_MACHINE_ID` / `CROWDSEC_MACHINE_PASSWORD` (for alerts and unban), so both views work out of the box. When connecting to an existing CrowdSec instance, the installer prompts for an optional machine ID and password.
:::
