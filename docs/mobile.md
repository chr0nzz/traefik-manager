# Mobile App

**traefik-manager-mobile** is the companion app for managing Traefik Manager from your phone or tablet, native on both platforms: Kotlin and Jetpack Compose on Android, Swift and SwiftUI on iPhone and iPad. Both share one version number and the same features, and the iOS app starts at 2.5.0.

<div class="shot-grid">
  <img class="screenshot dark-only" src="/images/mobile-dark.gif" alt="Android phone">
  <img class="screenshot light-only" src="/images/mobile-light.gif" alt="Android phone">
  <img class="screenshot dark-only" src="/images/ios-dark.gif" alt="iPhone">
  <img class="screenshot light-only" src="/images/ios-light.gif" alt="iPhone">
</div>

Every screen on Android, tablet, iPhone and iPad is in the [UI examples](/ui-examples#android).

::: info Using external auth (Authentik, Authelia, etc.)?
A `forwardAuth` middleware in front of Traefik Manager blocks the app before Traefik Manager ever sees the request, so no API key can help. See [external auth providers](#external-auth-providers) for the route split that fixes it.
:::

---

## Download

<MobileRelease />

<a href="https://play.google.com/store/apps/details?id=dev.chr0nzz.traefikmanager">
  <img src="https://github.com/chr0nzz/traefik-manager/raw/main/static/icons/GetItOnGooglePlay.svg" alt="Get it on Google Play" style="height:50px;width:auto" />
</a>

**iPhone and iPad:** coming soon to the App Store.

---

## Setup

### 1. Generate an API key

In the Traefik Manager web UI go to **Settings → Authentication → API Keys** and click **Add Key**. Enter a device name (e.g. `My Phone`) and click **Generate**. Copy the full key - it is only shown once.

::: tip One key per device
Each device should have its own key, up to 10 at once. Keys are identified by their device name in the settings list, so you can revoke a single device without affecting others.
:::

### 2. Configure the app

Open the mobile app and enter:

| Field | Value |
|---|---|
| Instance URL | Base URL of your Traefik Manager instance, e.g. `https://traefik-manager.example.com` |
| API Key | The key generated in step 1 |

Tap **Connect**.

### Do I need an API key?

The server decides whether a request must be authenticated at all:

| Built-in auth | OIDC | Authentication required |
|---|---|---|
| Off | Off | No - every request is accepted |
| Off | On | Yes |
| On | Either | Yes |

The app asks a narrower question - *does this server have any API keys* - and makes your entry match:

- **At least one key exists** - enter one, even if built-in auth is off. An empty field is rejected.
- **No keys exist** - leave the field empty. A key is rejected with *"API key auth is not enabled on this server"*, because there is nothing to check it against.

In practice: **if you have generated a key, use it.**

::: warning OIDC with no API keys
The one combination the app cannot resolve on its own. The server requires authentication, no keys exist, and the connect check itself needs authentication, so the app reports **"This server requires an API key"**. Generate one under **Settings → Authentication → API Keys**. OIDC covers the browser only.
:::

::: info Internal CAs and plain HTTP
Since v2.0.0 the Android app trusts CA certificates installed on the device, so instances secured by an internal/private CA work: install your root CA on the phone under **Settings → Security → Encryption & credentials → Install a certificate → CA certificate**, then connect with your `https://` URL. Plain `http://` URLs (LAN-only setups) are also supported.

On iPhone and iPad, install the root CA as a profile, then turn on full trust for it under **Settings → General → About → Certificate Trust Settings**. The iOS app also connects to plain `http://` URLs, and asks for local network access the first time it reaches a server on your LAN.
:::

---

## Navigation

### Android

Navigation adapts to the screen. On a phone the bar sits at the bottom; on a tablet or an unfolded device it becomes a side rail. Everything else lives in a drawer, opened from the menu icon in the top bar.

The bar holds five destinations. By default those are **Dashboard**, **Routes**, **Middleware**, **Logs** and **CrowdSec**; pick your own five, and their order, under **Settings → Appearance and security → Choose items**. The same screen can hide the bar entirely, leaving the drawer as the way around.

### iPhone and iPad

On iPhone the tab bar holds **Dashboard**, **Routes**, **Middleware** and **Logs**, and **More** lists everything else. On iPad, and on a large iPhone in landscape, a sidebar lists every screen in the same four sections as the Android drawer, with the server switcher at the top.

### Drawer

The drawer holds every destination, grouped into four sections, plus the server switcher:

| Section | Destinations |
|---|---|
| Traffic | Dashboard, Routes, Middleware, Services, Route map |
| Observability | Logs, CrowdSec |
| Infrastructure | Certificates, Plugins |
| System | Backups, Settings |

::: tip Tabs follow the server
There is nothing to switch on in the app. Route map, Logs, CrowdSec, Certificates and Plugins each map to an optional tab in Traefik Manager, and appear as soon as that tab is enabled on the server you are connected to. Switch to an agent with a different set enabled and the destinations change with it.
:::

---

## Features

### Dashboard

The overview: router, service and middleware counts with their health, the providers in use, and your entry points. Below them your routes appear as an app launcher, grouped and tappable, sharing its configuration with the web Dashboard tab. A bell in the top bar carries unread notifications, and pull to refresh reloads.

### Routes

- Every HTTP, TCP and UDP route, with status, domain, target and attached middlewares
- Search, and filter by protocol or status
- Ping a route to check the backend is answering; a route with some backend servers down reads as degraded
- Tap a route for its detail pane; edit it, delete it, enable or disable it, or edit its raw YAML
- When its service has a health check, the detail pane marks each backend server up or down and counts them
- Disabling preserves the configuration - Traefik simply stops routing until you re-enable
- Add a route with the form, or drop to raw YAML for anything the form does not cover
- Multiple backends, sticky sessions, health checks and router priority
- Per-route certificate resolver, editable certificate and extra domains, and **Skip TLS verification** for self-signed backends
- Backend scheme `http`, `https` or `h2c`
- **Use a service** lists this config's services, services from other providers such as `whoami@docker`, and `noop@internal` for a router with no backend
- Composite services (`weighted`, `mirroring`, `failover`) are shown but edited on the web - the app keeps their configuration intact when saving a route

### Middleware

- Every middleware with its type, protocol and config
- Search, and filter by type
- **30 built-in wizards** covering Basic and Digest Auth, Forward Auth with Authentik, Authelia and Gatekeeper presets, OIDC Auth, IP Allow List, Rate Limit, In-Flight Requests, Secure Headers, CORS, redirects, prefix and path rewriting including the regex forms, Retry, Circuit Breaker, Buffering, Compress, Chain, Encoded Characters, Custom Error Pages, Content Type, gRPC-Web and Pass TLS Client Cert - the same set as the web app
- **Templates** - your saved YAML templates, managed from the middleware screen
- Raw YAML for anything the wizards do not cover

### Services

Every service Traefik knows about, with its backends, health and the routers using it. Search and filter by provider. Tap for the detail pane.

From 1.13.0 the tab also authors them. **+** builds a load balancer, weighted, mirroring or failover service; each backend row takes an address or a reference to another service, with per-row weights and mirror percentages. The detail pane edits, renames and deletes, and offers to manage a composite Traefik Manager did not write, or to hand it back. A load balancer can carry a health check with the same fields as the web app: path, interval, timeout, method, expected status, interval when down, scheme, port, host header, mode, redirects and headers.

| | |
|---|---|
| Managed here | Editable, and marked as managed by Traefik Manager |
| In the config file | Read only until you choose **Manage this service** |
| TCP and UDP | Read only. Authoring writes HTTP services |
| Highest random weight | Read only. Traefik Manager does not author this type anywhere |

Works against the host or any agent. A service written to an agent lives in that agent's config files and is managed independently, so the same name can exist on both.

### Providers

One read-only page per provider, shown in the drawer under Providers when its tab is on for the selected server. Tabs turn on by themselves the first time Traefik reports the provider, on the host and on each agent, and are switched in Settings like any other tab.

| Page | Lists routers from |
|---|---|
| Docker, Swarm, Nomad, ECS, Consul Catalog | That provider |
| Kubernetes | Kubernetes CRD, Ingress and Gateway API |
| Redis, etcd, Consul KV, ZooKeeper | That KV store |
| HTTP Provider | Traefik's HTTP provider |
| File (external) | File provider configs Traefik Manager does not manage |
| Internal | Traefik itself: dashboard, API, ping |

Each page shows how many routes are live or not serving, search, a protocol filter, the route cards with their target, the provider's middlewares, and a detail sheet per route.

### Logs

The access log as analytics rather than a wall of text, mirroring the web app. Seven cards - status codes, response time, methods, domains, paths, clients and services - each with counts you can tap to filter the list. A **Where it fails** panel names the worst status-and-path pairs. Tap any entry for its full detail.

Domains need a JSON access log; on `common` format the card says so.

### CrowdSec

Built around the attack rather than the ban list, as the web app is. Cards for **attacking sources**, **networks**, **scenarios**, **targeted paths** (or accounts on an SSH host), **tooling** by user agent, and **bans in force**. Colour marks only what is not already handled, so a host being probed but absorbed cleanly reads calm.

- Search by address, scenario, network, path, route or host
- **Targeted routes** names the routers and hosts attackers went through, when CrowdSec's context file lists `traefik_router_name` and `target_fqdn`
- **Bans in force** pages through decisions on the server, 50 at a time, so a large blocklist is never downloaded whole
- **Add decision** to ban an address, with type, duration and reason
- Remove a decision to unban
- Country flags and a ranked country strip when GeoIP is enabled; tap a country to filter

The screen states plainly when the LAPI is unreachable, or when only decisions or only alerts could be read, rather than showing zero as if it were fact.

### Certificates

Every certificate from your resolvers, with domains and expiry. Search, copy the domain list, and pull to refresh.

- Filter by **Unused**, **No resolver** or **Expiring**
- Remove a certificate, or every unused one at once, when `acme.json` is writable and a restart method is set. A copy of `acme.json` is saved to Backups and Traefik restarts
- Deleting a route offers to remove the certificates nothing else uses

### Plugins

The plugins declared in your static config, with their module name and version. Search, copy a module name, and see which middlewares reference each plugin - or that none do.

Install one with **+**: paste the static config snippet from the plugin's page, paste and edit the middleware snippet, and choose the file the middleware is written to. Existing plugins can be renamed, repointed at another module, or pinned to a different version, and removed. Each of those writes the static config on whichever server is selected, host or agent.

Nothing reaches Traefik until it restarts, so the tab says so and offers **Restart now**.

### Backups

Four tabs: **Dynamic**, **Static**, **Certificates** and **Git**.

- Create a backup on demand, restore one, or delete it
- Restoring asks for confirmation first, and the server takes a backup of the current config before overwriting
- After restoring a static backup the screen tells you Traefik is still running the old config, and offers **Restart Traefik**
- **Certificates** lists the `acme.json` copies taken before a certificate is removed. Restoring one replaces every certificate and restarts Traefik; if the restart fails the screen offers **Restart Traefik**
- The Git tab shows commit history with the changed files, pushes on demand, and restores from a commit

### Notifications

Channels, matching **Settings - Notifications** in the web UI. Every enabled channel gets its own copy of an event, filtered by the categories, minimum severity, digest and quiet hours set on it.

| Action | Where |
|---|---|
| Add a channel | The **+** button, then pick a type and fill in its fields |
| Edit filters | The pencil on a channel |
| Send a test | The paper plane on a channel, or **Test** in the editor |
| Remove | The bin on a channel |

Stored secrets read back masked. Leave a masked field alone and it is kept; clear it and it is removed.

Servers older than 1.12.0 have no channels, and the screen shows the single webhook those versions take instead.

#### Push to this device (Android)

**Push to this device** delivers events to the phone through [UnifiedPush](https://unifiedpush.org).

1. Install a UnifiedPush distributor, the app that holds the connection and hands out endpoints. Any from the [distributor list](https://unifiedpush.org/users/distributors/) works:

   | Distributor | Backed by |
   |---|---|
   | ntfy | An ntfy server, self-hosted or ntfy.sh |
   | NextPush | Your Nextcloud |
   | Sunup | Mozilla's autopush, self-hostable |
   | Conversations | Your XMPP account |

2. Turn on **Push to this device** and allow notifications.
3. The app registers, then creates its own channel pointing at the endpoint it was given.

That channel appears in the list as a **Mobile app** channel marked **this device**, and its filters can be edited like any other, so the phone can take errors only while a Discord channel takes everything. Turning the toggle off removes it. Each notification is titled with the category it came from.

Without a distributor installed the toggle stays off, and the app says so rather than polling in the background.

::: warning
Traefik Manager posts to the endpoint in plain text. On a self-hosted ntfy that is your own server; on a shared one the operator can read the message. Notifications are also truncated at 4096 bytes.
:::

#### Alerts on this device (iPhone and iPad)

iOS has no UnifiedPush, and a self-hosted server cannot send Apple push notifications. Instead, **Settings → Notifications → Alerts on this device** lets the app check the notification history in the background and show anything new as an iOS notification, from a minimum severity you choose. Nothing changes on the server.

iOS decides how often the app may check, from every 15 minutes to a few hours, and less often for an app you rarely open. For instant alerts on an iPhone, add an ntfy, Pushover or Telegram channel; their own apps deliver the push.

Marking the history read clears the alerts, and anything already in the history when you turn alerts on stays quiet.

### Servers and agents

The server switcher sits at the top of the drawer, and the same list is under **Settings → Servers**. Switch between the host and any registered TMA agent, each with a live health indicator. Every screen then reflects that server's Traefik instance, and the destinations change to match its enabled tabs.

**Settings → Servers** also adds, renames and removes agents, and generates the compose snippet for a new one.

### Widgets

#### Android

Two home screen widgets, from the same data as the app. Add one from your launcher's widget picker and its setup screen opens as you place it.

| Widget | Setup |
|---|---|
| Traefik Manager (small and large) | Which server, which card, and how often it refreshes. Stack up to four and tap to cycle. |
| App launcher | Your dashboard apps as a grid: which servers it lists, and whether names show. |

Both resize freely and re-flow to fit.

#### iPhone and iPad

Three widgets: long-press the home screen, tap **Edit → Add Widget** and pick Traefik Manager.

| Widget | Sizes | Setup |
|---|---|---|
| Status card | Small, medium, large, Lock Screen | Edit the widget to pick the card (HTTP or TCP/UDP routers, services, middlewares, entry points, certificates, or a CrowdSec card) and the server |
| All servers | Small, medium, large | Routers, problems and bans on every server |
| Launcher | Medium, large | Your dashboard apps with their icons; tap one to open it |

The app refreshes the widgets when you open it and when iOS runs its background check, so they show what the app last saw.

### Demo mode

**Try Demo** on the connect screen runs the app against built-in sample data, with no server required. Useful for looking around before you point it at anything real.

### Languages

The app opens in the phone's language when it has it: Chinese (Simplified), Czech, Danish, Dutch, French, French (Canada), German, Portuguese, Portuguese (Brazil), Russian and Spanish, plus British and American English spellings. Any other language shows English. To use a different language than the phone, pick it in **Settings → Appearance and security → App language** on Android, or under **Traefik Manager → Language** in the iOS Settings app.

The app sends its language to the server, so error and status messages from Traefik Manager v1.15.0 or newer arrive in the same language; older servers answer in English. Translations happen on [Weblate](https://hosted.weblate.org/projects/traefik-manager/mobile/).

---

## Settings

**Settings** sits in the drawer under System, and opens a list of pages.

| Page | What is on it |
|---|---|
| Traefik connection | How this device reaches the server, plus domains, certificate resolvers and the direct Traefik API URL, with a **Test connection** button. Changing the API URL asks for the saved password again |
| Servers | The server list, and the compose snippet for a new agent (see [Servers and agents](#servers-and-agents)) |
| Authentication | Login status, the API keys registered on the server, and **Sign out other sessions** for browsers |
| Notifications | Push to this device on Android or alerts on iOS, route checks, the notification channels, and the history (see [Notifications](#notifications)) |
| Appearance and security | See below |
| Static config | The raw `traefik.yml`, and the restart that applies it (see [Static config](#static-config)) |
| Diagnostics | See below |
| About | Versions, and the open source licences |

### Appearance and security

| Setting | What it does |
|---|---|
| Theme | Light, Dark or System |
| Dynamic colour | Android 12+ only. Takes the palette from your wallpaper, while status colours stay semantically distinct |
| App language | Follow system, or one of the app's languages. On iOS this opens the app's page in the Settings app |
| Hide the navigation bar | Android only. Frees the bottom of the screen; the drawer still reaches everything |
| Choose items | Android only. Which five screens sit in the bar, and their order |
| Dashboard layout | Rows or icons for the app launcher, shared with the web UI |
| Require unlock | Gates the app behind biometrics (Face ID or Touch ID on iOS) or your device PIN or passcode |

Everything here except the dashboard layout is stored on the device only.

### Static config

**Settings - Static config** edits Traefik's own `traefik.yml` as text, for the server currently selected.

The file is read whole and written whole. Nothing is written until you press **Save**, and while there are unsaved changes the screen says so and offers **Discard** to reload from the server. The server parses the YAML before writing and refuses anything that will not load, so a syntax error comes back as an error rather than a broken Traefik.

After a save, Traefik is still running the previous config until it restarts, which the screen says with a **Restart Traefik** button.

::: warning
A valid file can still be a broken one. Removing an entry point or disabling the Traefik API will parse cleanly and take your setup down. A backup is taken before every save and can be restored from Backups.
:::

### Diagnostics

What the server sees for your request: the trusted client IP that feeds the login rate limiter, audit log, `ipAllowList` and CrowdSec; the raw socket peer before any header is trusted; the trusted proxy hop count (`PROXY_FIX_HOPS`) and whether the socket peer is a trusted proxy (`TRUSTED_PROXIES`); the `X-Forwarded-For` chain and the forwarding headers as received. Each address is tagged public, private, CGNAT, loopback or link-local, so a private trusted IP alongside forwarding headers - the signature of a wrong `trustedIPs` or hop count - is visible at a glance.

---

## External auth providers

A `forwardAuth` middleware (Authentik, Authelia, Keycloak, etc.) intercepts **all** requests, including the mobile app's API calls, and redirects them to the provider's login page. The app cannot complete that OAuth/OIDC flow.

Split the Traefik route in two: one with `forwardAuth` for the web UI, and one without for `/api/*` that relies on Traefik Manager's own API key auth.

```yaml
http:
  routers:
    traefik-manager-web:
      rule: Host(`manager.example.com`) && !PathPrefix(`/api`)
      middlewares: [authentik]
      entryPoints: [websecure]
      service: traefik-manager
      tls:
        certResolver: cloudflare

    traefik-manager-api:
      rule: Host(`manager.example.com`) && PathPrefix(`/api`)
      entryPoints: [websecure]
      service: traefik-manager
      tls:
        certResolver: cloudflare

  services:
    traefik-manager:
      loadBalancer:
        servers:
          - url: http://traefik-manager:5000
```

::: warning Keep one form of auth enabled
Generate API keys for your mobile devices. A valid key is accepted in every mode, so the `/api/*`
route stays protected whether you sign in with the built-in password or with OIDC.

The one combination that leaves it open is turning **both** off: with built-in auth disabled and no
OIDC provider configured, `/api/*` answers without a key at all.
:::

---

## Requirements

| | |
|---|---|
| Traefik Manager (server) | **v1.14.0 or higher**, v1.15.0 for server messages in the app's language |
| Android | 13+ (API 33) |
| iPhone and iPad | iOS and iPadOS 17+ |
| Push on Android (optional) | A UnifiedPush distributor, such as the ntfy app |

---

## Privacy

The app collects nothing. It talks only to the Traefik Manager server you connect it to, and to the addresses of your own routes when you open them. The server URL and API key stay on the device (the API key in the Android keystore or the iOS Keychain), and there is no analytics, crash reporting, advertising or account with the developer. Push on Android goes through the UnifiedPush distributor you pick; alerts on iOS are local notifications built on the device.

---

## Tech Stack

Version 2.x is native on both platforms.

- **Android:** Kotlin 2.4, Jetpack Compose with Material 3 Expressive, Hilt, Retrofit 3 with kotlinx.serialization, DataStore for storage, Glance with WorkManager for the widgets, and UnifiedPush for push. Release builds are minified and resource-shrunk with R8.
- **iOS:** Swift and SwiftUI with no third-party dependencies, WidgetKit with App Intents for the widgets, LocalAuthentication for the app lock, and BackgroundTasks with UserNotifications for alerts.

Version 1.x was built with Expo SDK 53 / React Native 0.79, and is still available on the `v1` branch.

::: tip Upgrading from 1.x
The rewrite ships under the same application id and is signed with the same certificate, so it installs straight over 1.x from either channel and keeps your server, API key and placed widgets.
:::
