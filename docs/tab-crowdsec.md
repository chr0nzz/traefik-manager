# CrowdSec Tab

The **CrowdSec** tab connects to a CrowdSec Local API (LAPI) and shows active security decisions, recent alerts, and a summary of enforcement activity. You can unban IPs directly from the tab without touching the CLI.

The tab is optional and must be enabled in Settings or during the setup wizard.

## What it shows

### Stats bar

A row of counters at the top of the tab shows the current totals by decision type:

- **Bans** - number of IPs currently blocked
- **Captchas** - number of IPs currently served a captcha challenge
- **Bypasses** - number of IPs currently whitelisted from enforcement

### Decisions table

The main table lists every active decision from the LAPI:

| Column | Description |
|---|---|
| **IP** | Source IP address or CIDR range |
| **Type** | Decision type - ban, captcha, or bypass |
| **Duration** | Time remaining until the decision expires |
| **Scenario** | The CrowdSec scenario that triggered the decision |
| **Origin** | Source of the decision (e.g. `crowdsec`, `cscli`, `console`) |
| **Actions** | **Unban** button to delete the decision immediately |

Clicking **Unban** sends a delete request to the LAPI and removes the row from the table without a page reload.

### Alerts section

Below the decisions table, recent alerts are listed in reverse chronological order:

- **Time** - when the alert was created
- **Source IP** - the IP that triggered the alert
- **Scenario** - the scenario that matched
- **Decisions** - number of decisions created from the alert

## Not configured state

If CrowdSec is not configured, the tab shows a placeholder message instead of data. The placeholder includes a link to **Settings → System Monitoring** where you can enter your LAPI URL and API key.

## Enabling the tab

### During setup wizard

Toggle **CrowdSec** on in the "Optional monitoring" step.

### After setup

Go to **Settings → System Monitoring** and enable the CrowdSec toggle.

## Configuration

There are two ways to configure the LAPI connection. Settings fields take priority; environment variables are the fallback.

### Option 1 - Settings UI

Go to **Settings → System Monitoring → CrowdSec** and fill in:

- **LAPI URL** - the base URL of your CrowdSec LAPI (e.g. `http://crowdsec:8080`)
- **API key** - a bouncer API key (see below for how to generate one)

Values entered here are stored encrypted in `manager.yml`.

### Option 2 - Environment variables

Set the following environment variables on the traefik-manager container:

```bash
CROWDSEC_LAPI_URL=http://crowdsec:8080
CROWDSEC_API_KEY=your-bouncer-api-key
```

### Generating a bouncer API key

Run the following command inside your CrowdSec container to create a key for traefik-manager:

```bash
docker exec <crowdsec-container> cscli bouncers add traefik-manager
```

Copy the key that is printed - it is only shown once.

## Docker Compose example

The following snippet shows traefik-manager and CrowdSec running on the same network with the connection configured via environment variables:

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
