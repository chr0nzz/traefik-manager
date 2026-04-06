# Logs Tab

The **Logs** tab displays Traefik's access log - a record of every HTTP request routed through Traefik, including status codes, response times, upstream targets, and client IPs.

## What it shows

- Recent access log entries (tail of the log file)
- Color-coded HTTP status codes: green (2xx/3xx), yellow (4xx), red (5xx)
- Method highlighting (GET, POST, PUT, DELETE, etc.)
- Request path, upstream service, duration

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

## Notes

- Only the most recent entries are shown (tail view)
- The log is not streamed live - refresh the tab to see new entries
- For real-time log output, use the **Live Monitor** tab
