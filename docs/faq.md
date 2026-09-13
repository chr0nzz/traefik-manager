---
title: FAQ
description: The questions that come up most often in Traefik Manager issues and discussions, with short answers.
---

# FAQ

## Traefik connection

### "Traefik API unavailable", or routes that never go live

Two different faults. Open the route's detail panel: its banner names which one you have.

**API unreachable**: Traefik Manager cannot call the Traefik API. Check the URL under **Settings → Connection → Traefik API URL** (it must be reachable from inside the container, e.g. `http://traefik:8080`, not a public dashboard URL behind auth), and that Traefik has `api: {}` enabled. Add `TRAEFIK_API_USER` / `TRAEFIK_API_PASSWORD` if the API sits behind basic auth.

**Traefik is up but has loaded nothing from the file provider**: Traefik is not reading the file Traefik Manager writes. Both must point at the same file:

```yaml
# traefik.yml
providers:
  file:
    filename: /etc/traefik/dynamic.yml    # or directory: /etc/traefik/dynamic/
    watch: true
```

| Check | What goes wrong without it |
|---|---|
| The host file is mounted into **both** containers | Traefik Manager writes its own private copy that Traefik never sees |
| `CONFIG_PATH` names the exact file that is mounted | `dynamic.yaml` and `dynamic.yml` are different files. Traefik Manager writes one, Traefik watches the other |
| A **bind mount**, not a named volume, when mounting a single file | Docker creates a *directory* at a named volume's target, so both sides see an empty directory instead of your config |
| `watch: true` on `providers.file` | Traefik reads the file once at boot and ignores every later save |

The Static Config editor's **Providers** section has a File card with a **Directory** field and a **Watch** toggle if you would rather set this from the UI. It covers `directory` only; a `filename:` provider has to be edited in the raw YAML editor.

---

## Config files and routes

### Where does Traefik Manager write my routes, and are my hand edits kept?

To the file chosen in the **Config File** selector on the Add/Edit Route form, defaulting to `CONFIG_PATH` (or the first entry of `CONFIG_PATHS`). Saves merge rather than rewrite: comments, key order and anything Traefik Manager does not manage survive. Editing an existing router touches only `rule`, `entryPoints`, `service`, `middlewares`, `tls` and, when Traefik Manager manages the route's backends, `priority`. A timestamped copy goes to `BACKUP_DIR` before every write.

### Can I manage several dynamic config files? Several static configs?

Dynamic, yes. Set one of these, in priority order `CONFIG_DIR` > `CONFIG_PATHS` > `CONFIG_PATH`:

| Variable | What it takes |
|---|---|
| `CONFIG_PATH` | One file. Default `/app/config/dynamic.yml` |
| `CONFIG_PATHS` | Comma-separated list of files |
| `CONFIG_DIR` | A directory. Every `.yml` and `.yaml` inside it, recursively, plus a **+ New file...** option in the forms |

A **Config File** picker appears in the route, middleware and TLS option forms once more than one file is loaded. See [Environment Variables](env-vars.md#config-files).

Static, no. `STATIC_CONFIG_PATH` takes a single `traefik.yml`. To edit another server's static config, register an [agent](agent.md) for it and switch to it in the server switcher.

### What do `DOMAINS` and `CERT_RESOLVER` actually control?

The route form, and nothing else. Neither changes Traefik's configuration, your DNS, or which certificates get issued.

| Variable | Controls | Does not control |
|---|---|---|
| `DOMAINS` | Base domains offered when building a `Host()` rule | Routing or TLS. Domains found in existing routes are added automatically, and the **+** chip accepts any other domain, so the list is optional |
| `CERT_RESOLVER` | Which resolver names the form offers. The first is the default for new routes | Whether the resolver exists. It must be defined under `certificatesResolvers` in `traefik.yml` |

Both seed `manager.yml` on first start only. After that the Settings values win and changing the variable does nothing.

---

### Why can't I edit this route's backend?

The route points at a `weighted`, `mirroring`, `failover` or `highestRandomWeight` service that
Traefik Manager does not manage, so the target field is locked rather than silently ignored. Edit
the service on the [Services tab](tab-services.md), or open its detail panel and choose **Manage
this service** to let Traefik Manager take it over. Composites built by Traefik Manager itself are
editable directly from the route form.

## Certificates

### The Certs tab says permission denied on acme.json

Traefik Manager only reads `acme.json` unless you switch on certificate removal, so mount it `:ro` unless you want that. Under Docker the container runs as root, so Traefik's required mode 600 reads fine and a permission error there means you gave the container a non-root `user:`. On a native Linux install the `traefik-manager` service user needs read access:

```bash
chmod o+r /etc/traefik/acme.json
```

Traefik writes one storage file per resolver, so `ACME_JSON_PATH` also accepts a comma-separated list or a directory. See [Certs Tab](tab-certs.md#requirements).

### My custom cert resolver is missing from the dropdown

The list is your **Settings → Connection → Certificate resolver** value (comma-separated, first is the default) plus every key under `certificatesResolvers` in the `traefik.yml` that `STATIC_CONFIG_PATH` points at. Add it to either. Editing a route that already names some other resolver keeps that resolver in the dropdown regardless.

---

## Static config and middlewares

### How do I enable the static config editor, and what does Restart actually do?

Three things: mount `traefik.yml` read-write (no `:ro`), set `STATIC_CONFIG_PATH` to it, and set `RESTART_METHOD`. Then pick where it appears in **Settings → Interface → Tabs → Static Config**: `Off`, `Settings` (inside the settings window) or `Tab` (its own side-nav entry).

| `RESTART_METHOD` | How Traefik is restarted |
|---|---|
| `proxy` (default) | Restarts `TRAEFIK_CONTAINER` through a `docker-socket-proxy` sidecar at `DOCKER_HOST`. Traefik Manager never sees the full socket |
| `socket` | The same restart call, against the Docker socket directly |
| `poison-pill` | Writes `SIGNAL_FILE_PATH`. Traefik's own healthcheck finds the file and kills the container, and its restart policy brings it back |

Saving alone changes nothing: Traefik reads static config at boot only, so the editor shows **Saved. Traefik is still running the previous config.** until you restart. Full detail in [Static Config Editor](static.md#restart-methods) and [Enable Static Config Editor](static-enable.md).

### Can I attach a middleware to an entry point instead of to every route?

Yes, in the static config. Open **Static Config → Entrypoints**, edit the entry point and fill in **Middleware chain** with a comma-separated list, provider suffix included (`secure-headers@file`). That writes `entryPoints.<name>.http.middlewares` and needs a Traefik restart. Every router on that entry point then gets the chain, and no route can opt out of it.

---

## Authentication

### OIDC sign-in fails

| Symptom | Usual cause |
|---|---|
| Provider rejects the redirect URI | Register exactly `https://<your-tm-host>/auth/oidc/callback`. It is derived from the incoming request, so behind a proxy set `PROXY_FIX_HOPS` and forward `X-Forwarded-Proto` and `X-Forwarded-Host` |
| "the provider rejected the token request" | Client ID or secret mismatch. Traefik Manager tries `client_secret_post` and `client_secret_basic` before giving up, then logs the client ID it sent and the secret's length to compare against the provider |
| Login works, then access is denied | With both allow-lists empty, access is denied by default. Set **Allowed Emails** or **Allowed Groups**, or turn on **Allow any authenticated account** |
| Groups never match | The claim name. Set **Groups Claim Key** to whatever your provider actually sends |

The provider's own error text is shown on the login page and written to the log. See [OIDC / SSO Login](oidc.md).

### I turned off built-in auth and OIDC is still required

That is intended. `AUTH_ENABLED=false` turns off the password form only; OIDC then becomes the sole login. Turn OIDC off as well to leave the UI open to a forward-auth proxy in front of it, and Traefik Manager will warn at startup that nothing authenticates. Your password hash is kept either way, so if the provider goes down you can set `auth_enabled: true` in `manager.yml` and restart. See [Authentication modes](security.md#authentication-modes).

---

## CrowdSec

### Why does the CrowdSec tab need both a bouncer key and machine credentials?

They read different halves of the LAPI, mirroring how `cscli` works:

| Data | Credential |
|---|---|
| Decisions (active bans, captchas, bypasses) | Bouncer API key. The LAPI answers `403` to a machine token here |
| Alerts, and unbanning | Machine ID + password |

With only one set the tab runs degraded and names the missing half. A TLS client certificate can replace both if its OU is listed in the LAPI's `bouncers_allowed_ou` and `agents_allowed_ou`. See [CrowdSec Tab](tab-crowdsec.md#configuration).

---

## Agents

### What is the agent for, and do I need one?

Only if Traefik runs on more than one host. One Traefik Manager manages one Traefik directly. The agent (TMA) is a small Go daemon that runs next to a remote Traefik, listens on port 8090, and lets a central Traefik Manager reach that server's API, config files and backups without exposing them. Register each one under **Settings → Agents** and switch between them with the server switcher. See [Agent](agent.md).

### Where are the agent's logs on a binary install?

In the journal, not a file:

```bash
sudo journalctl -u tma -n 200 --no-pager
sudo journalctl -u tma -f
```

The Docker agent logs to `docker logs <container>` instead. By default the agent logs only its startup line, fatal errors and background failures; set `TMA_DEBUG=true` to log every failed Traefik API call with its URL and status, then reproduce the problem.

---

## Running Traefik Manager

### Is it safe to point at a production Traefik, and what does it change on disk?

It writes to a fixed set of paths, and backs up every config file before it touches it.

| Path | What it writes there |
|---|---|
| `CONFIG_PATH` / `CONFIG_PATHS` / `CONFIG_DIR` | Routers, services and middlewares you add or edit, merged into the existing YAML |
| `BACKUP_DIR` (`/app/backups`) | A timestamped copy of each config file before every write. `BACKUP_KEEP_COUNT` prunes old ones |
| The `SETTINGS_PATH` directory (`/app/config`) | `manager.yml` plus `agents.yml`, `templates.yml`, `notifications.yml`, `dashboard.yml`, `.secret_key`, `.otp_key`, a `cache/` directory, and a `geoip/` directory with a `.geoip.lock` beside it when IP geolocation is on |
| `STATIC_CONFIG_PATH` | Your `traefik.yml`, only when it is mounted read-write and only when you save in the Static Config editor |
| `ACME_JSON_PATH` | Your `acme.json`, only when it is mounted read-write, a restart method is set, and you switch removal on in Settings, and only when you remove a certificate or restore one |

The access log is only ever read. Leave `STATIC_CONFIG_PATH` unset and Traefik's own config file is never opened for writing; mount `acme.json` `:ro` and the certificate store never is either.

### How do I set the theme without opening the UI?

Set `default_theme` in `manager.yml` to `dark`, `light` or `system`. There is no environment variable for it.

```yaml
default_theme: system
```

It covers the login page and every browser that has not already used the nav bar theme toggle, which pins a per-browser choice. `POST /api/settings/theme` does the same thing over the API.
