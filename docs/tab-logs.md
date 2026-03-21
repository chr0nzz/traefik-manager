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
Go to **Settings → Optional Tabs** and enable Logs.

## Requirements

Traefik must have access logging enabled and the log file must be accessible to traefik-manager.

Enable access logging in `traefik.yml`:

```yaml
accessLog:
  filePath: "/logs/access.log"
  format: common
```

Mount the log directory into both the Traefik container and the traefik-manager container at the same path:

```yaml
services:
  traefik:
    volumes:
      - ./logs:/logs

  traefik-manager:
    volumes:
      - ./logs:/logs:ro
```

traefik-manager reads the log file directly from disk (read-only mount). The path it reads from is configured via the `ACCESS_LOG_PATH` environment variable (default: `/logs/access.log`).

## Notes

- Only the most recent entries are shown (tail view)
- The log is not streamed live - refresh the tab to see new entries
- For real-time log output, use the **Live Monitor** tab
