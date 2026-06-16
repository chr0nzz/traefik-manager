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

### Option 1 - Settings UI

Go to **Settings → System Monitoring → CrowdSec** and fill in:

- **LAPI URL** - the base URL of your CrowdSec LAPI (e.g. `http://crowdsec:8080`)
- **API key** - a bouncer API key (see below)

Values are stored encrypted in `manager.yml`.

### Option 2 - Environment variables

```bash
CROWDSEC_LAPI_URL=http://crowdsec:8080
CROWDSEC_API_KEY=your-bouncer-api-key
```

### Generating a bouncer API key

```bash
docker exec <crowdsec-container> cscli bouncers add traefik-manager
```

Copy the key that is printed - it is only shown once.

::: warning Alerts permission
Bouncer keys created with `cscli bouncers add` have read access to decisions but not alerts by default. If the Alerts section shows a permissions error, you need a key with `read:alerts` scope or use the CrowdSec console to generate a key with full read permissions.

On a [remote agent](agent.md#crowdsec), alerts and unban are instead handled with CrowdSec machine credentials (`CROWDSEC_MACHINE_ID` / `CROWDSEC_MACHINE_PASSWORD`) alongside the bouncer key, since the agent reads decisions with the bouncer key and alerts with the machine login.
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
The [traefik-stack installer](traefik-stack.md) can configure CrowdSec automatically during installation, including generating the bouncer key and wiring up the environment variables.
:::
