# Agent API Reference

The Traefik Manager Agent (TMA) exposes an HTTP API on port 8090. All endpoints except `/health` require authentication.

## Authentication

Include your API key in every request using the `X-Api-Key` header:

```http
X-Api-Key: your-api-key-here
```

Alternatively, use the `Authorization: Bearer <key>` header.

TM handles authentication automatically when proxying calls through `/api/agents/proxy/<id>/...`.

## Rate limiting

Requests are rate-limited per IP using `TMA_RATE_LIMIT` (default: 300 requests/minute). Returns `429 Too Many Requests` when exceeded. Set `TMA_RATE_LIMIT=0` to disable. TM makes many API calls per tab switch so the default is intentionally generous - lower it only if you need stricter access control.

## Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Health check - no auth required |
| GET | `/api/traefik/overview` | Traefik API overview |
| GET | `/api/traefik/routers` | Routers across all protocols - returns `{"http":[...],"tcp":[...],"udp":[...]}` |
| GET | `/api/traefik/services` | Services across all protocols - returns `{"http":[...],"tcp":[...],"udp":[...]}` |
| GET | `/api/traefik/middlewares` | Middlewares across all protocols - returns `{"http":[...],"tcp":[...]}` |
| GET | `/api/traefik/entrypoints` | Entrypoints |
| GET | `/api/traefik/version` | Traefik version |
| GET | `/api/traefik/logs` | Last N access log lines (requires `ACCESS_LOG_PATH`) - `?lines=100` |
| GET | `/api/traefik/certs` | Certificates from acme.json (requires `ACME_JSON_PATH`) |
| GET | `/api/configs` | Read dynamic config file(s) |
| POST | `/api/configs` | Write a dynamic config file (creates a `.bak` before writing) |
| GET | `/api/static` | Read static config (requires `STATIC_CONFIG_PATH`) |
| POST | `/api/static` | Write static config |
| GET | `/api/static/status` | Restart method info |
| POST | `/api/static/restart` | Restart Traefik (requires `RESTART_METHOD`) |
| GET | `/api/crowdsec/decisions` | CrowdSec active decisions (requires CrowdSec config) |
| GET | `/api/crowdsec/alerts` | CrowdSec recent alerts |
| DELETE | `/api/crowdsec/decisions/<id>` | Unban an IP |
| GET | `/api/backups` | List local `.bak` backup files |
| POST | `/api/backup/create` | Create `.bak` backups for all config files (one per file) |
| POST | `/api/restore/<filename>` | Restore a config file from a `.bak` backup |
| POST | `/api/backup/delete/<filename>` | Delete a `.bak` backup file |
| GET | `/api/backup/git/status` | Git backup status |
| POST | `/api/backup/git/push` | Manual git push |
| POST | `/api/backup/git/test` | Test git connectivity |
| GET | `/api/backup/git/commits` | Last 50 commits |
| GET | `/api/backup/git/commit/<sha>/diff` | Per-file diff for a commit |
| POST | `/api/backup/git/restore/<sha>` | Restore configs from a git commit |
| DELETE | `/api/backup/git/repo` | Reset (delete) local git repo clone |
| GET | `/api/routes/<id>/raw` | Raw YAML for a single route (router + service block) - `id` is the route name or `configFile::routeName` |
| POST | `/api/routes/<id>/raw` | Save raw YAML for a route - body: `{"content": "<yaml>"}` |
| GET | `/api/keys` | List API keys |
| POST | `/api/keys` | Create an API key |
| DELETE | `/api/keys/<id>` | Delete an API key |

## Health check

```http
GET /health
```

Response (no auth required):
```json
{"ok": true, "version": "1.5.1"}
```

## Error responses

| Status | Meaning |
|---|---|
| 401 | Missing or invalid API key |
| 404 | Endpoint not available (e.g. `STATIC_CONFIG_PATH` not set) |
| 429 | Rate limit exceeded |
| 500 | Internal error |
| 502 | Cannot reach Traefik (for proxy endpoints) |

All errors return `{"error": "message"}`.

## Backup format

Local backups use per-file `.bak` files, not zip archives. Each backup is named `filename.YYYYMMDD_HHMMSS.bak` (e.g. `dynamic.yml.20250601_143022.bak`). When restoring, the agent strips the timestamp suffix to recover the original filename and writes it back to `CONFIG_PATH`.

`POST /api/backup/create` creates one `.bak` file per config file found in `CONFIG_PATH` (and `STATIC_CONFIG_PATH` if configured) in a single request. `POST /api/configs` (config write) also creates a `.bak` for the affected file automatically before writing - this is the pre-write safety backup.

## Traefik data envelope

The `/api/traefik/routers`, `/api/traefik/services`, and `/api/traefik/middlewares` endpoints do NOT proxy the Traefik API directly. Instead they fetch all protocols and return a structured envelope:

- `/api/traefik/routers` - `{"http": [...], "tcp": [...], "udp": [...]}`
- `/api/traefik/services` - `{"http": [...], "tcp": [...], "udp": [...]}`
- `/api/traefik/middlewares` - `{"http": [...], "tcp": [...]}`

This matches the format TM expects for its own Traefik API calls, so agent data renders identically to local data.

If the agent cannot reach its Traefik API, or Traefik answers with a non-`200` status, these endpoints return `502` with `{"error": "traefik unavailable...", "ok": false}`. Earlier versions turned a non-`200` response into an empty list with status `200`, so a broken Traefik looked the same as one with nothing configured.

## API keys

The agent supports multiple named API keys stored in `BACKUP_DIR/keys.json` (encrypted). The primary `TMA_API_KEY` from the environment always works regardless of the key store. Additional keys can be created, listed, and deleted via `/api/keys`. This is useful when multiple TM instances need to connect to the same agent.

## Proxying through TM

TM proxies agent calls server-side via `/api/agents/proxy/<agent-id>/<path>`. For example:

```
GET /api/agents/proxy/abc123/api/traefik/routers
```

Routes to:
```
GET https://agent-host:8090/api/traefik/routers
```

TM injects the `X-Api-Key` header automatically using the stored (encrypted) key.
