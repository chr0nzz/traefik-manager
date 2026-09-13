# Environment Variables

All supported environment variables for Traefik Manager.

## Precedence

Each variable below is labelled with one of these:

| Label         | Behaviour                                                                                              |
| ---------------| --------------------------------------------------------------------------------------------------------|
| **Overrides** | Env always wins. `AUTH_ENABLED` and `ADMIN_PASSWORD` only.                                             |
| **Seeds**     | Used on first start only. Once the setting is saved, `manager.yml` wins - even if you clear the field. |
| **Fallback**  | The Settings field wins while it has a value. Clear it and the variable takes over.                    |
| **-**         | Env-only, never written to `manager.yml`.                                                              |

Adding a **Seeds** variable to an existing install does nothing. Change the value in Settings, or delete the key
from `manager.yml` and restart.

---

## Quick Reference

### Connection & Traefik

| Variable | Default | Precedence | Description |
|---|---|---|---|
| `TRAEFIK_API_URL` | `http://traefik:8080` | Seeds `traefik_api_url` | Traefik API URL |
| `TRAEFIK_API_USER` | _(unset)_ | Seeds `traefik_api_user` | Username for Traefik API basic auth |
| `TRAEFIK_API_PASSWORD` | _(unset)_ | Seeds `traefik_api_password` | Password for Traefik API basic auth (stored encrypted) |
| `TRAEFIK_INSECURE_SKIP_VERIFY` | `false` | - | Skip TLS certificate verification when calling the Traefik API (for self-signed certs) |
| `REQUESTS_CA_BUNDLE` | `/etc/ssl/certs/ca-certificates.crt` | - | CA bundle for outbound HTTPS, so mounted private CAs are trusted |

### Authentication

| Variable | Default | Precedence | Description |
|---|---|---|---|
| `COOKIE_SECURE` | `false` | - | Mark session cookie as `Secure` - required for HTTPS |
| `AUTH_ENABLED` | `true` | Overrides `auth_enabled` | Set to `false` to disable built-in login entirely |
| `ADMIN_PASSWORD` | _(unset)_ | Overrides `password_hash` | Admin password in plain text |

### OIDC

| Variable | Default | Precedence | Description |
|---|---|---|---|
| `OIDC_ENABLED` | `false` | Seeds `oidc_enabled` | Turn on OIDC login |
| `OIDC_PROVIDER_URL` | _(unset)_ | Seeds `oidc_provider_url` | Issuer URL, without `/.well-known/openid-configuration` |
| `OIDC_CLIENT_ID` | _(unset)_ | Seeds `oidc_client_id` | Client ID from your provider |
| `OIDC_CLIENT_SECRET` | _(unset)_ | Seeds `oidc_client_secret` | Client secret (stored encrypted) |
| `OIDC_DISPLAY_NAME` | `OIDC` | Seeds `oidc_display_name` | Name on the login button |
| `OIDC_ALLOWED_EMAILS` | _(unset)_ | Seeds `oidc_allowed_emails` | Comma-separated email allowlist |
| `OIDC_ALLOWED_GROUPS` | _(unset)_ | Seeds `oidc_allowed_groups` | Comma-separated group allowlist |
| `OIDC_GROUPS_CLAIM` | `groups` | Seeds `oidc_groups_claim` | Claim holding the user's groups |
| `OIDC_ALLOW_ANY_AUTHENTICATED` | `false` | Seeds `oidc_allow_any_authenticated` | Accept any account the provider authenticates |
| `OIDC_AUTO_LOGIN` | `false` | Seeds `oidc_auto_login` | Skip the login page and go straight to the provider |

### Routes & Domains

| Variable | Default | Precedence | Description |
|---|---|---|---|
| `DOMAINS` | `example.com` | Seeds `domains` | Comma-separated base domains for the Add Route form |
| `CERT_RESOLVER` | `cloudflare` | Seeds `cert_resolver` | Default ACME resolver name. Use `none` for external certs |

### Config Files

| Variable | Default | Precedence | Description |
|---|---|---|---|
| `CONFIG_DIR` | _(unset)_ | - | Directory - all `.yml` and `.yaml` files loaded automatically |
| `CONFIG_PATHS` | _(unset)_ | - | Comma-separated list of config file paths |
| `CONFIG_PATH` | `/app/config/dynamic.yml` | - | Single config file (default) |
| `BACKUP_DIR` | `/app/backups` | - | Directory for timestamped config backups |
| `BACKUP_KEEP_COUNT` | `0` | Seeds `backup_keep_count` | Keep only the last N `.bak` files per config file (0 = keep all) |
| `SETTINGS_PATH` | `/app/config/manager.yml` | - | Path to the TM settings file |

### Static Config & Restart

| Variable | Default | Precedence | Description |
|---|---|---|---|
| `STATIC_CONFIG_PATH` | _(unset)_ | Fallback `static_config_path` | Traefik static config - required for the Plugins tab and Static Config editor |
| `RESTART_METHOD` | `proxy` | - | `proxy`, `socket`, or `poison-pill` |
| `TRAEFIK_CONTAINER` | `traefik` | - | Container name for `proxy` and `socket` restart methods |
| `DOCKER_HOST` | _(unset - uses `/var/run/docker.sock`)_ | - | Docker socket URL - set to `tcp://socket-proxy:2375` for proxy method |
| `SIGNAL_FILE_PATH` | `/signals/restart.sig` | - | Signal file path for `poison-pill` method |

### Monitoring

| Variable | Default | Precedence | Description |
|---|---|---|---|
| `ACME_JSON_PATH` | `/app/acme.json` | Fallback `acme_json_path` | Path to `acme.json` for the Certificates tab. Accepts several files comma-separated, or a directory |
| `ACCESS_LOG_PATH` | `/app/logs/access.log` | Fallback `access_log_path` | Path to access log for the Logs tab |
| `PLUGINS_DIR` | _(unset)_ | - | Adds Traefik's plugins directory to the paths TM is allowed to read. Not needed for the Plugins tab, which reads `experimental.plugins` from the static config |
| `GEOIP_DB_PATH` | _(auto-downloaded)_ | Fallback `geoip_db_path` | Path to a custom GeoIP `.mmdb` for [IP geolocation](geoip.md) |
| `CROWDSEC_LAPI_URL` | _(unset)_ | Fallback `crowdsec_lapi_url` | CrowdSec LAPI base URL (e.g. `http://crowdsec:8080`) |
| `CROWDSEC_API_KEY` | _(unset)_ | Fallback `crowdsec_api_key` | CrowdSec bouncer API key, reads decisions (stored encrypted) |
| `CROWDSEC_MACHINE_ID` | _(unset)_ | Fallback `crowdsec_machine_id` | CrowdSec machine login, reads alerts and enables unban |
| `CROWDSEC_MACHINE_PASSWORD` | _(unset)_ | Fallback `crowdsec_machine_password` | Password for the machine login (stored encrypted) |
| `CROWDSEC_CLIENT_CERT` | _(unset)_ | Fallback `crowdsec_client_cert` | Path to a TLS client certificate for a LAPI behind mTLS, replaces the API key and machine login |
| `CROWDSEC_CLIENT_KEY` | _(unset)_ | Fallback `crowdsec_client_key` | Path to the client certificate's private key |
| `CROWDSEC_CA_CERT` | _(unset)_ | Fallback `crowdsec_ca_cert` | Path to the CA certificate that signed the LAPI's own certificate (private PKI) |
| `CROWDSEC_READ_TIMEOUT` | `20` | - | Seconds to wait for the LAPI to answer. Capped at 25 |
| `CROWDSEC_CONNECT_TIMEOUT` | `5` | - | Seconds to wait for the TCP/TLS connection itself |
| `CROWDSEC_ALERT_LIMIT` | `500` | Fallback `crowdsec_alert_limit` | How many of the most recent alerts to read. `0` reads every alert, which is slow on a large LAPI |

### Agents

| Variable | Default | Precedence | Description |
|---|---|---|---|
| `AGENT_API_RATE_LIMIT` | `30` | Seeds `agent_api_rate_limit` | Stored in `manager.yml` but not enforced in this release. The agent's own limit is `TMA_RATE_LIMIT`, set on the agent - see [Agent](agent.md) |

### Security

| Variable | Default | Precedence | Description |
|---|---|---|---|
| `SECRET_KEY` | _(auto-generated)_ | - | Flask session signing key |
| `INACTIVITY_TIMEOUT_MINUTES` | `120` | - | Log out after this many minutes of inactivity |
| `OTP_ENCRYPTION_KEY` | _(auto-generated)_ | - | Fernet key for every secret stored encrypted in `manager.yml` |
| `PROXY_FIX_HOPS` | `1` | - | Number of trusted proxy hops in front of Traefik Manager for `X-Forwarded-For` |
| `WEB_CONCURRENCY` | `2` | - | Worker processes. Each costs about 50 MB. Raise for more fault isolation, not for speed |
| `GUNICORN_THREADS` | `4` | - | Requests served at once per worker. Traefik Manager spends most of its time waiting on Traefik and on agents, so threads are what make pages load in parallel. `WEB_CONCURRENCY x GUNICORN_THREADS` is the total |
| `GUNICORN_TIMEOUT` | `60` | - | Seconds before the supervisor restarts a worker that has stopped responding. A restart drops every request that worker is handling, so leave room above the 15 second agent timeout |
| `GUNICORN_KEEPALIVE` | `5` | - | Seconds an idle connection is held open |
| `GUNICORN_WORKER_CONNECTIONS` | `200` | - | Connections a worker will accept before new ones wait in the kernel backlog |
| `GUNICORN_LOG_LEVEL` | `info` | - | Gunicorn's own log level |
| `BASE_PATH` | _(none)_ | - | Serve Traefik Manager under a sub path, for example `/traefik-manager` |
| `LOG_LEVEL` | `INFO` | - | Python log level: `DEBUG`, `INFO`, `WARNING`, `ERROR` |

---

## Connection & Traefik

### `TRAEFIK_API_URL`

**Default:** `http://traefik:8080`  
**Seeds:** `traefik_api_url`

The URL of the Traefik API. Must be reachable from the host running Traefik Manager.

:::tabs
== Docker / Podman
```yaml
environment:
  - TRAEFIK_API_URL=http://traefik:8080
```
== Linux (systemd)
```ini
Environment=TRAEFIK_API_URL=http://localhost:8080
```
:::

---

### `TRAEFIK_API_USER` / `TRAEFIK_API_PASSWORD`

**Default:** _(unset)_  
**Seeds:** `traefik_api_user` / `traefik_api_password` (password stored encrypted)

HTTP Basic Auth credentials for the Traefik API. Set them when `api.insecure: false` and basic auth is configured on the Traefik dashboard. Both are required together.

Can also be set via **Settings → Connection** without a restart; leave the password blank there to keep the existing value.

---

## Authentication

### `COOKIE_SECURE`

**Default:** `false`

Set to `true` when Traefik Manager is served over HTTPS.

:::tabs
== Docker / Podman
```yaml
environment:
  - COOKIE_SECURE=true
```
== Linux (systemd)
```ini
Environment=COOKIE_SECURE=true
```
:::

::: warning
If you are behind a reverse proxy with HTTPS and do not set this, logins will fail silently.
:::

---

### `AUTH_ENABLED`

**Default:** `true`  
**Overrides:** `auth_enabled`

Set to `false` to disable the built-in login entirely. Use when TM is protected by an external auth provider (Authentik, Authelia, Traefik `basicAuth`, etc.). Only `true`/`1`/`yes` and `false`/`0`/`no` are recognised; anything else falls through to `manager.yml`.

:::tabs
== Docker / Podman
```yaml
environment:
  - AUTH_ENABLED=false
```
== Linux (systemd)
```ini
Environment=AUTH_ENABLED=false
```
:::

::: danger
When disabled and OIDC is off, the UI is fully open. Only use this behind another authentication layer.
:::

---

### `ADMIN_PASSWORD`

**Default:** _(unset)_  
**Overrides:** `password_hash`

Set the admin password in plain text. Useful for scripted deployments.

:::tabs
== Docker / Podman
```yaml
environment:
  - ADMIN_PASSWORD=mysecretpassword
```
== Linux (systemd)
```ini
Environment=ADMIN_PASSWORD=mysecretpassword
```
:::

::: info
When set, the in-UI password change and 2FA are bypassed. `flask reset-password` with `--prompt`, `--stdin` or `--password` exits with an error and writes nothing; with no password option it still writes a temporary password, which login then ignores. Remove the variable to switch back to `manager.yml`-managed passwords.
:::

---

## OIDC

### `OIDC_*`

**Seeds:** the ten `oidc_*` keys in `manager.yml`

Configure OIDC without opening Settings. Each variable seeds its matching key, so it applies while that key is absent from `manager.yml` and stops applying once the key is written there. Booleans accept `true`/`1`/`yes`/`on` and `false`/`0`/`no`/`off`.

:::tabs
== Docker / Podman
```yaml
environment:
  - OIDC_ENABLED=true
  - OIDC_PROVIDER_URL=https://id.example.com/application/o/tm/
  - OIDC_CLIENT_ID=traefik-manager
  - OIDC_CLIENT_SECRET=your-client-secret
  - OIDC_DISPLAY_NAME=Authentik
  - OIDC_ALLOWED_GROUPS=admins
```
== Linux (systemd)
```ini
Environment=OIDC_ENABLED=true
Environment=OIDC_PROVIDER_URL=https://id.example.com/application/o/tm/
Environment=OIDC_CLIENT_ID=traefik-manager
Environment=OIDC_CLIENT_SECRET=your-client-secret
Environment=OIDC_DISPLAY_NAME=Authentik
Environment=OIDC_ALLOWED_GROUPS=admins
```
:::

`OIDC_CLIENT_SECRET` is encrypted the first time it is written to `manager.yml`. See [OIDC](oidc.md) for the provider setup and [manager.yml](manager-yml.md) for each key.

::: warning
Leaving both `OIDC_ALLOWED_EMAILS` and `OIDC_ALLOWED_GROUPS` empty denies every login unless `OIDC_ALLOW_ANY_AUTHENTICATED` is `true`.
:::

---

## Routes & Domains

### `DOMAINS`

**Default:** `example.com`  
**Seeds:** `domains`

Comma-separated list of base domains shown in the Add Route form. A form convenience only - it does not affect Traefik configuration, TLS, or routing. Domains found in existing routes are added to the form automatically, and the form's **+** chip accepts any other domain, so this list is optional.

:::tabs
== Docker / Podman
```yaml
environment:
  - DOMAINS=example.com,home.lab
```
== Linux (systemd)
```ini
Environment=DOMAINS=example.com,home.lab
```
:::

---

### `CERT_RESOLVER`

**Default:** `cloudflare`  
**Seeds:** `cert_resolver`

One or more ACME cert resolver names, comma-separated. The first is the default for new routes. Each route can override this individually in the Add/Edit Route form.

Set to `none` if you manage certificates externally (cert files, internal CA, `tls.yml`). Routes will use `tls: {}` with no `certResolver`.

:::tabs
== Docker / Podman
```yaml
environment:
  - CERT_RESOLVER=letsencrypt

  - CERT_RESOLVER=letsencrypt, cloudflare

  - CERT_RESOLVER=none
```
== Linux (systemd)
```ini
Environment=CERT_RESOLVER=letsencrypt, cloudflare
```
:::

---

## Config Files

### `CONFIG_DIR`, `CONFIG_PATHS`, `CONFIG_PATH`

Traefik Manager can manage one or many dynamic config files. Three variables control this in priority order:

```
CONFIG_DIR  >  CONFIG_PATHS  >  CONFIG_PATH
```

Only one should be set. When multiple config files are loaded, a **Config File** dropdown appears in the Add/Edit Route and Middleware forms. `CONFIG_DIR` also adds a **+ New file...** option to create files on the fly.

---

### `CONFIG_DIR`

**Default:** _(unset)_

Point to a directory and every `.yml` and `.yaml` file inside it, including subdirectories, is loaded automatically.

:::tabs
== Docker / Podman
```yaml
environment:
  - CONFIG_DIR=/app/config/traefik
volumes:
  - /host/traefik/config:/app/config/traefik
```
:::

---

### `CONFIG_PATHS`

**Default:** _(unset)_

Comma-separated list of full config file paths. Good for 2-5 named files.

:::tabs
== Docker / Podman
```yaml
environment:
  - CONFIG_PATHS=/app/config/routes.yml,/app/config/services.yml
volumes:
  - /host/routes.yml:/app/config/routes.yml
  - /host/services.yml:/app/config/services.yml
```
:::

---

### `CONFIG_PATH`

**Default:** `/app/config/dynamic.yml`

Single config file. Default for most setups.

:::tabs
== Docker / Podman
```yaml
environment:
  - CONFIG_PATH=/data/traefik/dynamic.yml
volumes:
  - /path/to/traefik/dynamic.yml:/data/traefik/dynamic.yml
```
== Linux (systemd)
```ini
Environment=CONFIG_PATH=/etc/traefik/dynamic.yml
```
:::

---

### `BACKUP_DIR`

**Default:** `/app/backups`

Where timestamped backups are written before every config save.

:::tabs
== Docker / Podman
```yaml
environment:
  - BACKUP_DIR=/data/backups
volumes:
  - /path/to/backups:/data/backups
```
== Linux (systemd)
```ini
Environment=BACKUP_DIR=/var/lib/traefik-manager/backups
```
:::

---

### `BACKUP_KEEP_COUNT`

**Default:** `0` (keep all)  
**Seeds:** `backup_keep_count`

How many timestamped `.bak` files to keep per config file. Older ones are pruned after each backup. On the host this is also **Settings → Backups**; on a remote agent it is set via this variable.

:::tabs
== Docker / Podman
```yaml
environment:
  - BACKUP_KEEP_COUNT=30
```
== Linux (systemd)
```ini
Environment=BACKUP_KEEP_COUNT=30
```
:::

---

### `SETTINGS_PATH`

**Default:** `/app/config/manager.yml`

Path to the Traefik Manager settings file. Its directory also holds the companion files - `agents.yml`, `templates.yml`, `notifications.yml`, `dashboard.yml`, `.secret_key` and `.otp_key`.

:::tabs
== Docker / Podman
```yaml
environment:
  - SETTINGS_PATH=/data/manager.yml
volumes:
  - /path/to/manager.yml:/data/manager.yml
```
== Linux (systemd)
```ini
Environment=SETTINGS_PATH=/var/lib/traefik-manager/manager.yml
```
:::

---

## Static Config & Restart

If TM can reach the Docker socket, it reads the `traefik-manager.restart-method` and `traefik-manager.static-config` labels off your Traefik container at startup and uses them for any of these variables you left unset.

### `STATIC_CONFIG_PATH`

**Default:** _(unset)_  
**Fallback:** `static_config_path`

Path to Traefik's static config (`traefik.yml` or `traefik.toml`). Required for the **Plugins** tab and **Static Config** editor - both stay unavailable until this or the Settings field is set. Mount **read-write** (no `:ro`) to allow editing. Can also be set via **Settings → System Monitoring → File Paths** without a restart.

:::tabs
== Docker / Podman
```yaml
environment:
  - STATIC_CONFIG_PATH=/app/traefik.yml
volumes:
  - /path/to/traefik.yml:/app/traefik.yml
```
== Linux (systemd)
```ini
Environment=STATIC_CONFIG_PATH=/etc/traefik/traefik.yml
```
:::

---

### `RESTART_METHOD`

**Default:** `proxy`

How TM restarts Traefik after static config changes. Drives the Restart button in the Static Config editor.

| Value | Description |
|---|---|
| `proxy` | Via a Docker socket proxy sidecar (recommended) |
| `socket` | Via a directly mounted Docker socket |
| `poison-pill` | Writes a signal file; Traefik's healthcheck detects it and restarts |

:::tabs
== Docker / Podman
```yaml
environment:
  - RESTART_METHOD=proxy
```
== Linux (systemd)
```ini
Environment=RESTART_METHOD=poison-pill
```
:::

See [Static Config](static.md#restart-methods) for full compose snippets for each method.

---

### `TRAEFIK_CONTAINER`

**Default:** `traefik`

The name of the Traefik container to restart. Used by the `proxy` and `socket` restart methods.

:::tabs
== Docker / Podman
```yaml
environment:
  - TRAEFIK_CONTAINER=traefik
```
:::

---

### `DOCKER_HOST`

**Default:** _(unset - uses `/var/run/docker.sock`)_

Docker socket URL. Set to `tcp://socket-proxy:2375` when using the `proxy` restart method.

:::tabs
== Docker / Podman
```yaml
environment:
  - DOCKER_HOST=tcp://socket-proxy:2375
```
:::

---

### `SIGNAL_FILE_PATH`

**Default:** `/signals/restart.sig`

Signal file path for the `poison-pill` restart method. Must be on a shared volume between TM and Traefik.

:::tabs
== Docker / Podman
```yaml
environment:
  - SIGNAL_FILE_PATH=/signals/restart.sig
```
== Linux (systemd)
```ini
Environment=SIGNAL_FILE_PATH=/var/lib/traefik-manager/signals/restart.sig
```
:::

---

## Monitoring

### `ACME_JSON_PATH`

**Default:** `/app/acme.json`  
**Fallback:** `acme_json_path`

Path to Traefik's `acme.json`. Required for the **Certificates** tab. Can also be set via **Settings → System Monitoring → File Paths** without a restart.

Traefik writes one storage file per certificate resolver. Give them comma-separated, or point this at a directory and every `.json` file in it is read:

```yaml
# comma-separated
- ACME_JSON_PATH=/letsencrypt/ovh.json,/letsencrypt/lan.json
# or a directory
- ACME_JSON_PATH=/letsencrypt
```

Certificates from every file are shown together, each tagged with the file it came from.

This is also how you read certificates out of a Docker named volume. Docker cannot mount a single
file from one, so mount the volume as a directory and name the file here:

```yaml
environment:
  ACME_JSON_PATH: /traefik-certs/acme.json
volumes:
  - traefik_certs:/traefik-certs:ro
```

:::tabs
== Docker / Podman
```yaml
environment:
  - ACME_JSON_PATH=/letsencrypt/acme.json
volumes:
  - /path/to/acme.json:/letsencrypt/acme.json:ro
```
== Linux (systemd)
```ini
Environment=ACME_JSON_PATH=/etc/traefik/acme.json
```
:::

---

### `ACCESS_LOG_PATH`

**Default:** `/app/logs/access.log`  
**Fallback:** `access_log_path`

Path to Traefik's access log. Required for the **Logs** tab. Enable access logging in your Traefik static config first:

```yaml
accessLog:
  filePath: /var/log/traefik/access.log
```

:::tabs
== Docker / Podman
```yaml
environment:
  - ACCESS_LOG_PATH=/logs/access.log
volumes:
  - /path/to/access.log:/logs/access.log:ro
```
== Linux (systemd)
```ini
Environment=ACCESS_LOG_PATH=/var/log/traefik/access.log
```
:::

If Traefik writes its log into a Docker named volume, mount the volume as a directory and name the
file here, since Docker cannot mount a single file out of one:

```yaml
environment:
  ACCESS_LOG_PATH: /traefik-logs/access.log
volumes:
  - traefik_logs:/traefik-logs:ro
```

---

### `GEOIP_DB_PATH`

**Default:** _(auto-downloaded to `/app/config/geoip/dbip-country-lite.mmdb`, next to `manager.yml`. The location follows `SETTINGS_PATH`, not `CONFIG_DIR`.)_  
**Fallback:** `geoip_db_path`

Path to a MaxMind DB format (`.mmdb`) GeoIP database for [IP geolocation](geoip.md) in the Logs and CrowdSec tabs. Leave unset to use the free DB-IP Lite country database TM downloads automatically; set it to use your own (e.g. MaxMind GeoLite2). Geolocation must be enabled in **Settings → Interface → Geolocation**.

:::tabs
== Docker / Podman
```yaml
environment:
  - GEOIP_DB_PATH=/data/GeoLite2-Country.mmdb
volumes:
  - /path/to/GeoLite2-Country.mmdb:/data/GeoLite2-Country.mmdb:ro
```
== Linux (systemd)
```ini
Environment=GEOIP_DB_PATH=/var/lib/traefik-manager/GeoLite2-Country.mmdb
```
:::

---

### `CROWDSEC_LAPI_URL`

**Default:** _(unset)_  
**Fallback:** `crowdsec_lapi_url`

Base URL of the CrowdSec Local API. Required to enable the CrowdSec tab, together with a bouncer API key, machine credentials, or a client certificate. The matching field in **Settings → System Monitoring → CrowdSec** takes priority.

:::tabs
== Docker / Podman
```yaml
environment:
  - CROWDSEC_LAPI_URL=http://crowdsec:8080
```
== Linux (systemd)
```ini
Environment=CROWDSEC_LAPI_URL=http://crowdsec:8080
```
:::

---

### `CROWDSEC_API_KEY`

**Default:** _(unset)_  
**Fallback:** `crowdsec_api_key`

CrowdSec bouncer API key, used to read decisions. Generate one with `cscli bouncers add traefik-manager` inside the CrowdSec container.

:::tabs
== Docker / Podman
```yaml
environment:
  - CROWDSEC_API_KEY=your-bouncer-key
```
== Linux (systemd)
```ini
Environment=CROWDSEC_API_KEY=your-bouncer-key
```
:::

---

### `CROWDSEC_MACHINE_ID` / `CROWDSEC_MACHINE_PASSWORD`

**Default:** _(unset)_  
**Fallback:** `crowdsec_machine_id` / `crowdsec_machine_password`

CrowdSec machine credentials. Required to read **alerts** and to **unban** (delete decisions) - bouncer keys get `403 access forbidden` on those endpoints. Alerts are where every attack card on that tab comes from, so without these the tab can only show the bans already in force. The two credentials are complementary rather than tiered: CrowdSec refuses the machine token on `/v1/decisions`, so `CROWDSEC_API_KEY` is still needed alongside these. Create a machine with `cscli machines add traefik-manager --auto -f-` and copy the `login` / `password` from the output.

:::tabs
== Docker / Podman
```yaml
environment:
  - CROWDSEC_MACHINE_ID=traefik-manager
  - CROWDSEC_MACHINE_PASSWORD=your-machine-password
```
== Linux (systemd)
```ini
Environment=CROWDSEC_MACHINE_ID=traefik-manager
Environment=CROWDSEC_MACHINE_PASSWORD=your-machine-password
```
:::

> If the password contains a `$`, escape it as `$$` in `docker-compose.yml`.

---

### `CROWDSEC_CLIENT_CERT` / `CROWDSEC_CLIENT_KEY` / `CROWDSEC_CA_CERT`

**Default:** _(unset)_  
**Fallback:** `crowdsec_client_cert` / `crowdsec_client_key` / `crowdsec_ca_cert`

Mutual TLS for the LAPI connection. If your LAPI authenticates bouncers and machines with client certificates (`tls` auth, `bouncers_allowed_ou` / `agents_allowed_ou`), point these at the PEM files mounted into the container. The certificate replaces the API key for **decisions** and the machine login for **alerts** - one certificate covers both when its OU is allowed on both sides, and the LAPI auto-provisions the bouncer and machine on first contact. `CROWDSEC_CA_CERT` verifies the LAPI's own server certificate when it comes from a private PKI. Certificate, API key and machine credentials can be mixed; any one of them makes the tab configured.

:::tabs
== Docker / Podman
```yaml
environment:
  - CROWDSEC_LAPI_URL=https://crowdsec:8080
  - CROWDSEC_CLIENT_CERT=/certs/tm-client.crt
  - CROWDSEC_CLIENT_KEY=/certs/tm-client.key
  - CROWDSEC_CA_CERT=/certs/ca.crt
volumes:
  - ./certs:/certs:ro
```
== Linux (systemd)
```ini
Environment=CROWDSEC_LAPI_URL=https://crowdsec:8080
Environment=CROWDSEC_CLIENT_CERT=/etc/traefik-manager/certs/tm-client.crt
Environment=CROWDSEC_CLIENT_KEY=/etc/traefik-manager/certs/tm-client.key
Environment=CROWDSEC_CA_CERT=/etc/traefik-manager/certs/ca.crt
```
:::

---

### `CROWDSEC_READ_TIMEOUT` / `CROWDSEC_CONNECT_TIMEOUT`

**Defaults:** `20` / `5` seconds

How long to wait for the CrowdSec LAPI. Raise the read timeout if the CrowdSec tab reports the LAPI as unreachable on an instance that is simply busy. It is capped at 25 because the web worker is recycled at 30 - a higher value would be killed before it could return.

```yaml
environment:
  - CROWDSEC_READ_TIMEOUT=25
```

---

### `CROWDSEC_ALERT_LIMIT`

**Default:** `500`

How many of the most recent alerts the CrowdSec tab reads, newest first. The default keeps the tab responsive on a LAPI holding a large community blocklist. Set it to `0` to read every alert the LAPI still retains - on a large instance that can take longer than the read timeout allows, which is what the limit exists to prevent.

**Alert limit** under **Settings - System Monitoring - CrowdSec** wins when it is set. It is written to `manager.yml` as `crowdsec_alert_limit` and survives a Settings save; this env var applies when the field is blank.

```yaml
environment:
  - CROWDSEC_ALERT_LIMIT=1000
```

Decisions are not limited. They are read through the LAPI's own streaming endpoint, which sends the full set once and then only what changed, so a refresh stays cheap no matter how many decisions the LAPI holds.

---

## Security

### `SECRET_KEY`

**Default:** _(auto-generated and persisted as `.secret_key` alongside `SETTINGS_PATH`)_

Flask session signing key. Set this to keep sessions alive across container restarts without re-login.

:::tabs
== Docker / Podman
```yaml
environment:
  - SECRET_KEY=your-random-32-byte-hex-string
```
== Linux (systemd)
```ini
Environment=SECRET_KEY=your-random-32-byte-hex-string
```
:::

::: tip Generating a key
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```
:::

---

### `OTP_ENCRYPTION_KEY`

**Default:** _(auto-generated and stored as `.otp_key` alongside `SETTINGS_PATH`)_

Fernet key for every secret TM stores encrypted: the TOTP secret, Traefik API password, OIDC client secret, notification channel tokens and passwords, CrowdSec credentials, git backup token and agent API keys.

:::tabs
== Docker / Podman
```yaml
environment:
  - OTP_ENCRYPTION_KEY=your-32-byte-url-safe-base64-key
```
== Linux (systemd)
```ini
Environment=OTP_ENCRYPTION_KEY=your-32-byte-url-safe-base64-key
```
:::

::: tip Generating a key
```bash
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```
:::

::: warning
Lose this key and every stored secret becomes unreadable - 2FA must be re-enrolled and the other credentials re-entered. Back up `.otp_key` alongside your config volume.
:::

---

### `BASE_PATH`

**Default:** _(none)_

Serves Traefik Manager under a sub path instead of the root of a host, for example
`https://example.com/traefik-manager`. Leave it unset to serve from the root, which is the default
and needs no configuration.

The value must be a path starting with a single `/`, with no trailing slash and no scheme. Anything
else is ignored and logged at startup.

```yaml
services:
  traefik-manager:
    environment:
      BASE_PATH: /traefik-manager
```

A `stripPrefix` middleware in front is optional. Traefik Manager accepts the prefixed path whether or
not Traefik has already removed it.

::: warning OIDC redirect URI
If you use OIDC, the callback URL changes when you set this. Update the redirect URI at your identity
provider to include the prefix, or sign in will fail after the redirect.
:::

Use a sub domain instead where you can. It needs no configuration on either side.

---

### `PROXY_FIX_HOPS`

**Default:** `1`

How many trusted reverse-proxy hops sit in front of Traefik Manager. TM reads the client IP from the right of `X-Forwarded-For`; this value is how many positions it trusts. With a single proxy in front (Traefik → app) the default of `1` is correct. With two hops (e.g. Cloudflare → Traefik → app) the app's own login and audit logs would otherwise record the intermediate proxy's IP - set it to `2`.

The active value is shown in the startup log as `Trusted Hops` and in the Client IP Diagnostic.

:::tabs
== Docker / Podman
```yaml
environment:
  - PROXY_FIX_HOPS=2
```
== Linux (systemd)
```ini
Environment=PROXY_FIX_HOPS=2
```
:::

::: warning
Only count hops you actually control. Each trusted hop is one more `X-Forwarded-For` entry a client could forge, so setting this higher than your real proxy chain lets callers spoof their source IP past the login rate-limiter and audit log. Set it to `0` to ignore `X-Forwarded-For` entirely and use the direct connection IP.
:::
