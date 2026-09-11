# CrowdSec Tab

The **CrowdSec** tab connects to a CrowdSec Local API (LAPI) and answers one question: who is hitting this host, how, and what were they going after. Alerts are the evidence and lead the page; the bans they produced are one click behind. You can unban addresses and add manual decisions without touching the CLI.

The tab is optional and must be turned on in Settings.

## Using it

The tab works like the [Logs tab](tab-logs.md): read the verdict, click whatever looks wrong, and the feed below narrows to it.

Some worked examples:

**"Am I actually under attack, or is this background noise?"** The verdict answers directly. A host probed constantly but absorbed cleanly renders grey and says so - that is not a problem, it is CrowdSec working. Colour only appears when something got through unhandled: yellow when a source tripped a scenario and holds no ban, red when a whole vector produced no ban at all.

**"Who is hitting me?"** **Attacking sources** ranks addresses worst-first, where "worst" means still unbanned rather than merely loud. Click one to see every alert it raised. From the row detail you can jump to its network or its country in one more click.

**"What are they going after?"** **Targeted paths** ranks the URIs from the alert metadata, so you can see whether someone is sweeping for `/.env` and `/wp-login.php` or hammering one real endpoint. On an SSH-only host the same card becomes **Targeted accounts** and ranks usernames instead.

**"Is this one person or a botnet?"** **Networks** ranks by ASN. A single AS with many distinct addresses is usually one actor on a cloud provider; many ASNs hitting the same path is usually a distributed scan. **Tooling** tells you what they used - `curl`, `masscan` and friends are unambiguous, a copied browser string less so.

**"Why is this address still allowed in?"** Click `loose` on the Attacking sources card: sources that tripped a scenario and hold no active decision, which is the gap worth looking at. Add a ban with **+ Add Decision**, or leave it if the scenario was a false positive.

**"What is CrowdSec actually blocking for me?"** **Bans in force** is the doorway to the decisions view. Its footer splits your own detections from the community blocklist, which matters: a typical install has tens of thousands of subscribed entries and only a handful earned locally. Click `crowdsec` to see the ones your own rules produced.

## How the page reads

Everything lives in one panel, rendered from a single state:

1. **Verdict** - one plain-language line with the headline numbers next to it, and a red or yellow spine when something is wrong.
2. **Window row** - how many alerts the LAPI still retains, the span they cover, how many bans are in force, any active filters, and a scope note that is honest about what is being summarised.
3. **Seven cards** - the attack narrative, left to right.
4. **Runtime row** - six capability facts, green when present and muted when not.
5. **Geography** - the shared map and country list, fed from what CrowdSec already resolved.
6. **Attack evidence** - the alert feed, paginated, with a row detail panel.

Colour is rationed and means one thing everywhere: **colour marks what is not handled**. A host that CrowdSec is absorbing successfully renders grey even while being probed hard, because that is the truth. Yellow means a source tripped a scenario and holds no active decision. Red means a whole vector produced no ban at all. Bans in force are never red, because a ban is not a problem.

The **compact stat cards** setting (**Settings → Interface**) applies here exactly as it does on the Dashboard and Logs tabs.

### Cards

| Card | Hero | What it shows |
|---|---|---|
| **Attacking sources** | distinct source addresses | One strip cell per source, worst first: red for a repeat offender with no active ban, yellow for any unbanned source, grey for handled. Flags split `loose` from `banned`; the footer splits `repeat` from `one-shot`, and adds `simulated` when any scenario ran in simulation mode. |
| **Networks** | distinct ASNs | Ranked by `source.as_name`, with the AS number as the row kind and a country flag glyph. A `ranges` flag counts distinct `source.range` CIDRs. |
| **Scenarios** | alerts | Ranked on **alerts**, not decisions. The row kind carries the real bucket shape, `leaky 10/10s` or `trigger`. Flags count leaky against trigger buckets. |
| **Targeted paths** | distinct paths | URIs from the alert-level `meta[]`. The verb flags (`GET`, `POST`, ...) are deep links. On an SSH-only host the same card becomes **Targeted accounts** and ranks `target_user` instead. |
| **Targeted routes** | distinct routers | Which Traefik router and host an attack came through, from `traefik_router_name_leaf` (or the full chain) and `target_fqdn` in the alert `meta[]`. The host flags are deep links. A row whose router matches a route you have gets a route glyph; one that does not gets a question mark. See [Context](#context) below, since CrowdSec only writes these when you ask it to. |
| **Tooling** | distinct user agents | Shortened product tokens (`curl/8.5.0`, `masscan/1.3`). The row kind separates a real `tool` from a copied `browser string`. |
| **Bans in force** | active decisions | The doorway to the decisions view. The strip covers every decision grouped by origin: solid for your own detections, yellow for hand-added, rings for subscribed. The footer is four deep links, plus static `other` and `wide` items when a decision falls outside the four known origins or is Range or Country scoped. |

Ranking is **worst first**: rows with the most sources holding no active decision sort above rows with the highest raw count. The percentage column and the row tooltip carry the volume.

### Deep links

Every count is clickable and filters the feed below. Filters combine with AND, clicking the same one twice clears it, and the window row lists whatever is active with a **clear** button.

| Click | Filter applied |
|---|---|
| `loose` / `banned` / `simulated` | `outcome` |
| A source address, or **source** in a row detail | `ip` |
| A network row, or **network** in a row detail | `asn` |
| A country in the Geography panel | `cc` |
| A scenario row | `scenario` |
| A path row | `uri` |
| An account row on an SSH-only host | `user` |
| A verb flag | `verb` |
| A tooling row | `agent` |
| A targeted route row, or **router** in a row detail | `router` |
| A host flag, or **host** in a row detail | `host` |
| `crowdsec` / `by hand` / `CAPI` / `lists` | `origin`, and switches to the decisions view |
| `ban` / `captcha` on the Bans card | `type`, and switches to the decisions view |
| `local detections only` in the window row | `origin=subscribed` in the decisions view, the CAPI and blocklist rows the cards leave out |

`origin` and `type` only exist on decisions, so following one switches the view automatically unless the link named a view itself. `asn`, `cc`, `uri`, `verb`, `user`, `agent`, `router`, `host` and `outcome` only exist on alerts; if one is still active while you are looking at decisions the window row says so rather than silently dropping it.

### Attack evidence

The feed is the alert stream, twenty rows to a page, newest first. Each row carries the source address, the scenario, the country flag and AS name, a proportional strip of that alert's events, `events_count`, the ban state, and how long ago it fired. Clicking a row opens a detail panel where source, network, scenario, path, verb, agent and outcome are each themselves deep links:

`source`, `network`, `country`, `scenario`, `bucket`, `events`, `window`, `paths` and `verbs` (or `accounts`), `agent`, `outcome`, `reported by`.

### Bans in force

The section header carries a single flat button to the decisions view, and flips to a back button once you are there. Decision rows are deliberately thinner and show the value, the scope, the scenario, the live countdown from `duration`, the type and a trash button. Subscribed blocklist rows are dimmed, so your own bans stand out against tens of thousands of background rows.

Decisions are sorted with your own first, newest first, so a ban you just added is on page one rather than the last page.

#### Adding a manual decision

Click **+ Add Decision**:

- **IP / Range** - single IP or CIDR (e.g. `1.2.3.4` or `10.0.0.0/8`)
- **Type** - Ban, Captcha, or Bypass
- **Duration** - 1 hour, 4 hours, 24 hours, 7 days, 30 days, or 1 year
- **Reason** - optional label stored as the decision scenario

Below the form, **Custom Decisions** lists every decision you added by hand, each with an unban button. CrowdSec labels these `cscli` or `manual` depending on its version, and both count as added by hand.

## What the numbers do and do not mean

- **Retained, not total.** Alert counts describe the alerts the LAPI still holds. CrowdSec prunes on its own schedule and does not report how many it removed, so the oldest alert is the edge of retention, not the start of activity.
- **Loose versus banned is an exact-address join.** Alerts are matched against decisions on the source address. A source covered only by a Range or Country scoped decision therefore reads as loose. The `wide` footer item on the Bans card exists to make that gap visible.
- **`events_count`, not `events.length`.** The `events` array the LAPI returns is a truncated sample; `events_count` is the bucket counter and is the number used everywhere.
- **Paths, agents and verbs count hits, not alerts.** Alert-level `meta[]` is already deduplicated per alert, so one alert naming four paths lands on four rows. Those cards state the noun as `hits` and use the hit total as the denominator.
- **Capacity and leakspeed only mean something above zero.** A trigger bucket has capacity 0 and fires on the first matching event, so the burst-versus-prober read does not apply to it. The row kind says `trigger` rather than pretending otherwise.
- **`duration` counts down live.** It is not the length originally requested, so a `4h` ban reads back as `3h57m11s`.
- **Decisions carry no enrichment.** `/v1/decisions` returns seven fields: `value`, `type`, `scope`, `origin`, `scenario`, `duration`, `id`. No country, no ASN, no events, no time.

## Context

The alert `meta[]` is the only place this tab can learn what an attacker went after, and CrowdSec
writes into it only the fields listed in its context file, normally
`/etc/crowdsec/console/context.yaml`. That is why the Targeted paths, Tooling and Targeted routes
cards can be empty on a working setup: nothing is broken, the fields were never asked for.

To name the router and host in the evidence, add:

```yaml
traefik_router_name_leaf:
  - evt.Meta.traefik_router_name_leaf
traefik_router_name:
  - evt.Meta.traefik_router_name
target_fqdn:
  - evt.Meta.target_fqdn
```

The `crowdsecurity/traefik-logs` parser fills these from Traefik's access log. It also exposes
`traefik_router_name_root` and `traefik_router_name_intermediate` when a request passes through a
chain of routers. Reload CrowdSec after editing, and note that only alerts raised after the change
carry the new fields.

Where a router matches a route in Traefik Manager, the row detail offers a link that opens it.

## Geolocation

Countries come from `source.cn`, which CrowdSec resolves itself in the `crowdsecurity/geoip-enrich` parser on the machine that raised the alert. Nothing is sent anywhere.

If no alert carries a country and [IP geolocation](geoip.md) is enabled, the tab falls back to the host database for the alert source addresses only. It never geolocates the decisions list, because a community blocklist describes the internet rather than your host.

Click a country on the map or in the list to filter the whole tab to it.

## Degraded states

Each of these is a designed screen, not a grid of zeroes.

| Situation | What you see |
|---|---|
| **Bouncer key only** | Verdict reads "Bans visible, attacks are not". The five alert-derived cards go blind, each naming the exact reason, and the feed explains that the LAPI refused `/v1/alerts` as a permission boundary rather than an absence of attacks. The Bans card, the decisions view and the window row all still work. |
| **Machine credentials only** | Verdict reads "Attacks visible, bans are not". Every attack card is live; the ban state of each source is reported as unknown rather than guessed, and the Bans card names the missing bouncer key. |
| **Agent has no geoip-enrich** | The Networks card goes blind, names the parser, and says the LAPI stores whatever the agent sent rather than computing these fields. |
| **SSH-only host** | Targeted paths becomes Targeted accounts from `target_user`, and the Tooling card goes blind because SSH buckets share none of the HTTP meta keys. |
| **No alert carries meta** | Targeted paths goes blind and names `cscli` and blocklist alerts as the cause. |
| **Nothing has attacked** | A calm verdict, calm cards, and prose saying that every ban in force was subscribed rather than earned. Empty is not treated as an error. |
| **LAPI unreachable** | One panel saying nothing was read, with a link to Settings and a refetch button. No card invents a zero. The host returns HTTP 502 for this, matching what an agent already returned. |
| **Not configured** | A placeholder with a link to **Settings → System Monitoring → CrowdSec**. |

## Enabling the tab

Go to **Settings → System Monitoring** and turn on the **CrowdSec** toggle.

The setup wizard's **CrowdSec** step only stores the LAPI connection - leave its URL blank to skip it. The tab itself is turned on in Settings afterwards.

## Configuration

Settings fields take priority over environment variables.

CrowdSec's LAPI uses **two different credentials**, and they are **complementary rather than tiered**:

| Operation | Credential | Why |
|---|---|---|
| **Decisions** (active bans/captchas/bypasses) | Bouncer API key | Bouncers read the decisions stream. CrowdSec answers `403 access forbidden` to a machine token here |
| **Alerts** + **unban** (delete decision) | Machine login | Bouncer keys get `403 access forbidden` on these endpoints |

Neither credential is a superset of the other, so set **both** for the full tab. The tab counts as configured as soon as the LAPI URL plus either credential is present, and it says plainly which half is missing.

A **TLS client certificate** is the third option: if your LAPI authenticates with mutual TLS (`bouncers_allowed_ou` / `agents_allowed_ou`), one certificate covers both halves of the table and no key or password is needed. See below.

### Option 1 - Settings UI

Go to **Settings → System Monitoring → CrowdSec** and fill in:

- **LAPI URL** - the base URL of your CrowdSec LAPI (e.g. `http://crowdsec:8080`)
- **Alert limit** - how many of the most recent alerts to read, 0 to 100000. Blank falls back to `CROWDSEC_ALERT_LIMIT`, or 500; `0` reads every alert
- **API Key** - a bouncer API key, reads decisions (see below)
- **Machine Credentials** - machine ID + password, reads alerts and enables unban
- **Client Certificate mTLS** - cert, key and CA paths for a LAPI behind mutual TLS, replaces both credentials above

The API key and machine password are stored encrypted in `manager.yml`; the certificate fields are paths, not secrets.

### Option 2 - Environment variables

```bash
CROWDSEC_LAPI_URL=http://crowdsec:8080
CROWDSEC_API_KEY=your-bouncer-api-key
# Reads alerts, which is where every attack card comes from:
CROWDSEC_MACHINE_ID=traefik-manager
CROWDSEC_MACHINE_PASSWORD=your-machine-password
```

Or with a LAPI behind mutual TLS, a client certificate instead of both credentials - mount the PEM files into the container read-only:

```bash
CROWDSEC_LAPI_URL=https://crowdsec:8080
CROWDSEC_CLIENT_CERT=/certs/tm-client.crt
CROWDSEC_CLIENT_KEY=/certs/tm-client.key
CROWDSEC_CA_CERT=/certs/ca.crt
```

The certificate's OU must be listed in the LAPI's `bouncers_allowed_ou` to read decisions and `agents_allowed_ou` to read alerts and unban - list the same OU in both to do it all with one certificate. CrowdSec auto-provisions the bouncer and the machine on first contact, so nothing is created up front.

### Generating a bouncer API key

```bash
docker exec <crowdsec-container> cscli bouncers add traefik-manager
```

Copy the key that is printed - it is only shown once.

### Generating machine credentials (for alerts and unban)

```bash
cscli machines add traefik-manager --auto -f-
```

Copy the `login` and `password` from the output into the Machine Credentials fields (or the `CROWDSEC_MACHINE_ID` / `CROWDSEC_MACHINE_PASSWORD` env vars). If the machine shows as unvalidated, run `cscli machines validate traefik-manager`.

> `-f-` prints the credentials. Without it `cscli` overwrites `/etc/crowdsec/local_api_credentials.yaml`, which is what CrowdSec's own log processor logs in with.

> **Compose gotcha**: if the machine password contains a `$`, escape it as `$$` in `docker-compose.yml` - Docker Compose treats a single `$` as a variable reference. No escaping is needed in the Settings UI.

::: tip Why two credentials?
This mirrors CrowdSec's own auth model: `cscli decisions list` uses the bouncer/LAPI path while `cscli alerts list` uses the machine credential. Traefik Manager reads decisions with the bouncer key and alerts with the machine login, so both must be set for the full tab.
:::

## Fetching

- **Decisions** come from `/v1/decisions/stream` - a full sync on first read, then cached deltas, resynced hourly. On a LAPI with no stream endpoint it falls back to cursor pagination (`id_gt`), 1000 rows per page up to 200 pages. Expired rows are dropped. There is no display cap: every active decision is fetched, and the strip on the Bans card rescales rather than truncating, printing its own `1 cell = N` legend.
- If a refresh fails, the last good decisions are still shown rather than a screen of zeroes. Once they are more than 15 minutes old the **Bans in force** card says so and names the reason, so an expired machine login reads as an authentication problem rather than as no bans. The cache lives in the config directory, so it survives a restart.
- **The tab reads a summary**, not the list: counts by origin and type, the decisions added by hand, and the trimmed alerts, a few hundred KB instead of the whole blocklist. The decisions view is paged and searched on the server, twenty rows at a time. While the tab is open it asks for changes once a minute and gets a one-line answer when there are none.
- **Alerts** come from one request with `with_decisions=false` and a row limit - 500 by default, set under **Settings → System Monitoring → CrowdSec → Alert limit** or with the `CROWDSEC_ALERT_LIMIT` env var (0-100000, the setting wins). When a response hits the limit the alert counts show an **alert cap reached** flag rather than quietly truncating. A blank or `0` setting is not passed to an agent, which then uses its own `CROWDSEC_ALERT_LIMIT`. That flag stays: a single community blocklist alert can embed 15,000 decision objects.
- Alerts are cached beside the decisions and refreshed with the LAPI's `since` filter, so a refresh only pulls what is new; a full resync runs hourly and after a manual decision.
- Both are refetched together when you open the tab or press Refresh. The feed renders one page at a time, so a busy instance never builds tens of thousands of rows at once.

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
      - CROWDSEC_MACHINE_ID=traefik-manager
      - CROWDSEC_MACHINE_PASSWORD=your-machine-password
    networks:
      - proxy

networks:
  proxy:
    external: true
```

::: tip Automated setup
The [tm CLI installer](tm-cli.md) can configure CrowdSec during installation. Installing CrowdSec as part of the stack generates the bouncer key (for decisions), registers a **machine**, and wires up `CROWDSEC_MACHINE_ID` / `CROWDSEC_MACHINE_PASSWORD` (for alerts and unban), so both views work out of the box. When connecting to an existing CrowdSec instance, the installer prompts for an optional machine ID and password. To add CrowdSec to an install that does not have it, run `tm add crowdsec`.
:::
