# Logs Tab

The **Logs** tab displays Traefik's access log - a record of every HTTP request routed through Traefik, including status codes, response times, upstream targets, and client IPs.

## Analytics panel

Above the log list, an analytics panel summarises the currently loaded entries across two rows:

**Row 1 - Summary cards**
- **Status Codes** - counts and percentages for 2xx / 3xx / 4xx / 5xx with a stacked proportion bar
- **Response Time** - average and maximum duration, plus fast (<100 ms) / medium (100-500 ms) / slow (>500 ms) buckets
- **Methods** - breakdown of HTTP verbs (GET, POST, PUT, DELETE, PATCH, etc.) with bar charts

**Row 2 - Top lists**
- **Top IPs** - the 6 client IPs with the most requests, each tagged with its scope (**Public**, **Private**, **CGNAT**, **Loopback** or **Link-local**) so local noise - such as a gateway's `192.168.x.1` from hairpin NAT - is easy to tell apart from real public clients
- **Top Paths** - the 6 most frequently requested paths
- **Top Services** - the 6 Traefik services that handled the most requests

The panel updates each time you change the line count or search filter.

## What it shows

Each log entry is parsed into a card showing:

- **Method badge** - color-coded HTTP verb (GET, POST, DELETE, etc.)
- **Status badge** - status code with description (e.g. `404 Not Found`, `502 Bad Gateway`)
- **Path** - request path, truncated if long
- **IP** - client IP address
- **Service name** - Traefik service that handled the request (when available)
- **Duration** - response time

Click any card to open a detail panel with all fields (path, IP, date, size, duration, service, backend URL) and the full raw log line.

## Enabling the tab

### During setup wizard
Toggle **Logs** on in the "Optional monitoring" step.

### After setup
Go to **Settings → System Monitoring** and enable Logs.

## Requirements

Traefik must have access logging enabled. Add this to your `traefik.yml`:

```yaml
accessLog:
  filePath: "/logs/access.log"
  format: common
```

Both the `common` (CLF text) and `json` access log formats are parsed into cards. Lines that match neither are shown as-is.

Then point traefik-manager at the log file via the `ACCESS_LOG_PATH` environment variable (default: `/app/logs/access.log`).

:::tabs
== Docker / Podman
Mount the log file into both containers at the same path:

```yaml
services:
  traefik:
    volumes:
      - ./logs:/logs

  traefik-manager:
    volumes:
      - ./logs:/app/logs:ro
    # ACCESS_LOG_PATH defaults to /app/logs/access.log - no env var needed
```

Or use a custom path:
```yaml
  traefik-manager:
    environment:
      - ACCESS_LOG_PATH=/logs/access.log
    volumes:
      - ./logs:/logs:ro
```

== Linux (systemd)
```ini
Environment=ACCESS_LOG_PATH=/var/log/traefik/access.log
```

Make sure the `traefik-manager` user has read access:
```bash
chmod o+r /var/log/traefik/access.log
# or add to the owning group:
usermod -aG adm traefik-manager
```
:::

## Geolocation

When [IP geolocation](geoip.md) is enabled (**Settings → Interface → Geolocation**), the Logs tab adds a country flag next to each client IP, a **Top Countries** breakdown, and a shaded **world map** of where the requests came from. Click a country on the map or in the list to filter the log entries to it. Lookups run on the server against a local database, so no IP addresses are sent to any third party.

## Client IP diagnostic

The **network** icon in the top navigation bar opens a read-only **Client IP Diagnostic** for your own request. It shows:

- **App sees (client)** - the IP traefik-manager treats as the client after `ProxyFix`. This is the address that feeds the login/audit log, and the one your `ipAllowList` and CrowdSec rules match against.
- **Socket peer** - the IP on the other end of the raw TCP connection (your reverse proxy, or the real client if there is none).
- **Trusted hops** - how many proxy hops the app trusts when reading `X-Forwarded-For`.
- **Forwarding headers** - the raw `X-Forwarded-For`, `X-Real-IP`, `CF-Connecting-IP`, `X-Forwarded-Proto` and `X-Forwarded-Host` values as received.

Each IP is tagged with the same scope classification as the Top IPs list. If the client IP the app trusts is private, loopback or CGNAT while you expect public clients, the panel warns you - that usually means the upstream proxy's `trustedIPs` or the trusted-hop count is off, and the real client IP is being lost before it reaches logs, CrowdSec and `ipAllowList`.

For hairpin-NAT'd LAN traffic the real client IP is already gone at the network layer, so it cannot be recovered here - the panel only reports what actually arrives.

## Notes

- Only the most recent entries are shown (tail view)
- The log is not streamed live - refresh the tab to see new entries
- For real-time log output, use the **Live Monitor** tab
