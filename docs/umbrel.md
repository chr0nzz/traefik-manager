# Running on umbrelOS

Traefik Manager and its agent are in a community app store for umbrelOS, kept in [chr0nzz/tm-UmbrelOS](https://github.com/chr0nzz/tm-UmbrelOS). Each app brings its own Traefik.

| App | Install it when |
|---|---|
| Traefik Manager | You want Traefik Manager and a Traefik on your Umbrel |
| Traefik Manager Agent | You run Traefik Manager on another machine and want it to manage a Traefik on your Umbrel. Needs umbrelOS 2.0 or later. See [Agent](agent.md) |

::: warning Setup outside umbrelOS is required
umbrelOS keeps ports 80 and 443 for its own reverse proxy, so the Traefik in these apps listens on other ports. Nothing outside your network reaches it until you forward ports on your router, point your DNS at your public IP, and route your apps as described below.
:::

---

## Add the app store

1. In umbrelOS, open the **App Store**.
2. Open the menu in the top right corner and choose **Community App Stores**.
3. Paste `https://github.com/chr0nzz/tm-UmbrelOS` and click **Add**.
4. Open **Traefik Manager App Store** and install the app you want.

---

## Required setup

### Forward ports on your router

| App | External port 80 to | External port 443 to |
|---|---|---|
| Traefik Manager | `42080` on your Umbrel | `42443` on your Umbrel |
| Traefik Manager Agent | `43080` on your Umbrel | `43443` on your Umbrel |

The two apps use different ports, so they can be installed side by side.

### DNS and certificates

Point an `A` record (and `AAAA` for IPv6) for each domain at your public IP. Certificates come from Let's Encrypt through the certificate resolver `letsencrypt`, using the HTTP challenge. The challenge arrives on port 80, so it works once port 80 is forwarded. New routes use this resolver by default.

### Routing to other Umbrel apps

Route to an app's **container**, not to `umbrel.local`: a request through `umbrel.local` goes through that app's Umbrel login page. The container and port are `APP_HOST` and `APP_PORT` under `app_proxy` in the app's `docker-compose.yml` in the [official Umbrel app repository](https://github.com/getumbrel/umbrel-apps).

| App | Backend URL |
|---|---|
| Immich | `http://immich_server_1:2283` |
| Jellyfin | `http://jellyfin_server_1:8096` |
| Nextcloud | `http://nextcloud_web_1:80` |
| Vaultwarden | `http://vaultwarden_server_1:8089` |

Apps that use host networking, such as Home Assistant and Plex, have no container to route to. Reach them through the host:

| App | Backend URL |
|---|---|
| Home Assistant | `http://host.docker.internal:8123` |
| Plex | `http://host.docker.internal:32400` |

::: tip
If a `host.docker.internal` route times out, a firewall on the Umbrel is blocking containers from reaching the host. umbrelOS does not run one by default.
:::

::: danger
A route published through this Traefik is not behind the Umbrel login. Protect anything sensitive with the app's own login or an authentication middleware.
:::

---

## Traefik Manager app

The first time you open it, the setup wizard asks you to create a Traefik Manager login. The Umbrel login is switched off for this app, so the Traefik Manager login, API keys and the [mobile app](mobile.md) all work.

Changes to the static config restart Traefik through the [poison pill](docker.md#method-2-poison-pill) method, with no Docker socket access.

Data lives in `~/umbrel/app-data/tm-traefik-manager/data/` by default. App updates never overwrite it.

| Path | Holds |
|---|---|
| `traefik/traefik.yml` | Traefik's static config, editable in Traefik Manager |
| `traefik/dynamic/` | Your routes, middlewares and services |
| `traefik/acme/` | Certificates |
| `tm/config/` | `manager.yml`, its companion files and the generated keys |
| `tm/backups/` | Backups taken before every change |

---

## Traefik Manager Agent app

1. Install the app. It keeps restarting until step 3 is done, which is expected.
2. In your Traefik Manager, open **Settings**, **Agents**, add an agent and copy the API key it shows.
3. In umbrelOS, open this app's settings and paste the key into **TMA_API_KEY**. The agent starts.
4. In Traefik Manager, use `http://umbrel.local:4490` as the agent's URL, or your Umbrel's IP address with port `4490`.

The agent has no web interface of its own. Opening it from the Umbrel dashboard shows its health status.

---

## How this fits with umbrelOS

This Traefik runs next to the reverse proxy built into umbrelOS and does not replace it. umbrelOS keeps serving its dashboard and your apps on ports 80 and 443. Traefik only answers on its own ports, for the domains you route through it.

## Limitations

- The **Docker** provider is not available, because the apps do not mount the Docker socket. Routes go through Traefik's file provider, which is what Traefik Manager edits.
- The apps are in a community app store, not the official Umbrel App Store.

## Password reset

Open a terminal on the Umbrel, either over SSH or from **Settings**, **Advanced settings**, **Terminal** in umbrelOS, then run:

```bash
sudo docker exec -it tm-traefik-manager_web_1 flask reset-password --prompt
```

Other recovery methods: [Reset Password](reset-password.md).

## Updating

New versions arrive through the umbrelOS App Store like any other app update. Your routes, settings and certificates are kept.
