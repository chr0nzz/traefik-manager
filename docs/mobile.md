# Mobile App

**traefik-manager-mobile** is a React Native companion app for managing Traefik Manager from your phone.

::: warning Requires Traefik Manager v0.6.0 or higher
The mobile app authenticates via the API key feature introduced in v0.6.0. Earlier versions are not supported.
:::

::: warning Mobile app v0.6.0+ requires Traefik Manager v0.10.0 or higher
v0.10.0 includes the `CONFIG_DIR` multi-file API changes that the mobile app v0.6.0+ depends on. Connecting a v0.6.0+ mobile app to an older server will result in missing config file data.
:::

::: info Using external auth (Authentik, Authelia, etc.)?
See [connecting without an API key](#connecting-without-an-api-key) and [external auth providers](#external-auth-providers) below.
:::

---

## Download

<MobileRelease />

<a href="https://forms.gle/csituqc92sreNooZ8" target="_blank" rel="noopener noreferrer" class="vp-btn vp-btn--brand" style="display:inline-flex;align-items:center;gap:6px;margin-top:8px;">
  🧪 Sign up to beta test on Google Play
</a>

---

## Setup

### 1. Generate an API key

In the Traefik Manager web UI go to **Settings → Authentication → App / Mobile API Keys** and click **Add Key**. Enter a device name (e.g. `My Phone`) and click **Generate**. Copy the full key - it is only shown once.

::: tip One key per device
Each device should have its own key. You can have up to 10 keys at once. Keys are identified by their device name in the settings list, so you can revoke a single device without affecting others.
:::

### 2. Configure the app

Open the mobile app and enter:

| Field | Value |
|---|---|
| Server URL | Base URL of your Traefik Manager instance, e.g. `https://traefik-manager.example.com` |
| API Key | The key generated in step 1 |

Tap **Connect** - the app connects immediately.

::: tip API key is optional when built-in auth is disabled
If you have disabled Traefik Manager's built-in authentication (e.g. you are using an external provider like Authentik), leave the API key field empty. The app will detect that auth is disabled and connect without a key.

If built-in auth is enabled, an API key is required.
:::

---

## Navigation

The app uses a bottom navigation bar with four tabs: **Home**, **Routes**, **Middleware**, and **Services**. An optional **Logs** tab appears when enabled.

### Settings drawer

Tap the **hamburger icon** (top-left of any screen) to open the navigation drawer. The drawer provides access to all settings pages:

| Section | Items |
|---|---|
| General | Appearance, App Lock, Traefik, Server |
| Tabs | Logs |
| Data | Backups |
| Info | About |

---

## Features

### Dashboard (Home)

- Summary stat cards for HTTP Routers, TCP Routers, UDP Routers, Services, and Middlewares - each shows a ring chart with success / warning / error counts
- Tap **Explore →** on any card to jump to the matching tab filtered to that protocol
- Entrypoints listed at the bottom with name, address, and protocol badges
- On tablets and larger screens, stat cards display in a 2-column grid

### Routes

- List all HTTP, TCP, and UDP routes with status, domain, target, and attached middlewares
- Filter by protocol using the segmented button bar
- Enable / disable routes with a toggle - configuration is preserved, Traefik stops routing until re-enabled
- Add new routes via a form (name, host/domain, target IP, port, protocol, middlewares, cert resolver)
- Edit existing routes
- Delete routes with confirmation
- Tap a domain to open it in the browser

### Middlewares

- List all middlewares with type, protocol, and YAML config preview
- Filter by protocol
- Add new middlewares - two-step flow: choose from 12 built-in templates then fill in the form

    | Template | Description |
    |---|---|
    | Blank | Start from scratch |
    | HTTPS Redirect | Redirect HTTP to HTTPS |
    | Basic Auth | Password protect your service |
    | Security Headers | HSTS, X-Frame, XSS filter |
    | Rate Limit | Limit requests per source IP |
    | Forward Auth | Delegate auth to an external service |
    | Strip Prefix | Remove a URL path prefix |
    | Add Prefix | Prepend a URL path prefix |
    | Compress | Enable gzip / brotli compression |
    | IP Allowlist | Restrict access by IP range |
    | Redirect Regex | Redirect using a regex pattern |
    | Chain | Combine multiple middlewares |

- Edit existing middlewares (name + YAML)
- Delete middlewares with confirmation

### Services

- Live service list with protocol badge, type badge, and status chip (Success / Warning / Error)
- Server health fraction (e.g. `2/3 active`)
- Provider and linked router chips
- Tap the info icon for a full detail sheet

### Logs

The Logs tab is hidden by default. To enable it, open the drawer and go to **Logs**, then toggle **Show Logs Tab**.

::: warning Requires server-side configuration
The Logs tab requires `ACCESS_LOG_PATH` to be set in your Traefik Manager server configuration pointing to a Traefik access log file.
:::

- Color-coded log entries by HTTP status (green 2xx/3xx, yellow 4xx, red 5xx) in a monospace font
- Adjustable line count: 100, 500, or 1000 lines
- Pull to refresh

### Backups

Access via the drawer under **Data → Backups**. Create and restore configuration backups.

### Edit Mode

Tap the **pencil icon** in the top bar to enter edit mode. In edit mode, cards reveal:

- **Toggle** (routes only) - enable or disable the route
- **Edit** - open the edit form
- **Delete** - remove with confirmation

Buttons are hidden when not in edit mode to keep the list clean.

---

## Settings

All settings are accessed from the navigation drawer (hamburger icon in the top bar).

### Appearance

Switch between Light, Dark, and System theme.

### App Lock

Require biometric or device PIN authentication when the app opens or returns from background.

### Traefik

Configure domains, cert resolvers, and the direct Traefik API URL. Includes a **Test Connection** button to verify connectivity to the Traefik API.

### Server

Change the Traefik Manager server URL and API key, or switch to Demo Mode.

---

## Connecting without an API key

If Traefik Manager's built-in auth is disabled, leave the **API Key** field empty and tap **Connect**. The app will verify the server is reachable and connect without credentials.

::: danger No auth means no protection
If you disable built-in auth and expose Traefik Manager without any other protection, **anyone who can reach your instance can use the mobile app with no credentials**. Only disable built-in auth if you have an external auth provider (Authentik, Authelia, etc.) in front - and if so, read the [external auth providers](#external-auth-providers) section to ensure the mobile app still works correctly.
:::

---

## External auth providers

If you use an external auth provider (Authentik, Authelia, Keycloak, etc.) via Traefik's `forwardAuth` middleware, the middleware intercepts **all** requests - including the mobile app's API calls - and redirects unauthenticated requests to the provider's login page. The mobile app cannot complete that OAuth/OIDC flow.

The solution is to split the Traefik route into two: one with `forwardAuth` for the web UI, and one without for `/api/*` that relies on Traefik Manager's own API key auth.

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

::: warning Keep built-in auth enabled
When using this split-route pattern, keep Traefik Manager's built-in auth **enabled** and generate API keys for your mobile devices. Without built-in auth, the `/api/*` route has no protection.
:::

---

## Requirements

| | |
|---|---|
| Traefik Manager (server) | **v0.10.0 or higher** (mobile v0.6.0+), v0.6.0+ for earlier mobile versions |
| Android | 7.0+ (API 24+) |
| iOS | 16+ (build from source required) |

---

## Tech Stack

Built with [Expo](https://expo.dev) SDK 54 / React Native 0.81, Expo Router, TanStack Query, Zustand, and React Native Paper (Material Design 3).
