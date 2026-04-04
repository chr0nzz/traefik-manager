# Mobile App

**traefik-manager-mobile** is a React Native companion app for managing Traefik Manager from your phone.

::: warning Requires Traefik Manager v0.6.0 or higher
The mobile app authenticates via the API key feature introduced in v0.6.0. Earlier versions are not supported.
:::

---

## Download

<MobileRelease />

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

---

## Features

### Routes

- List all HTTP, TCP, and UDP routes with status, domain, target, and attached middlewares
- Enable / disable routes with a toggle - configuration is preserved, Traefik stops routing until re-enabled
- Add new routes via a form (name, host/domain, target IP, port, protocol, middlewares)
- Edit existing routes
- Delete routes with confirmation
- Tap a domain to open it in the browser

### Middlewares

- List all middlewares with type, protocol, and YAML config preview
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

### Edit Mode

Tap the **pencil icon** in the top bar to enter edit mode. In edit mode, cards reveal:

- **Toggle** (routes only) - enable or disable the route
- **Edit** - open the edit form
- **Delete** - remove with confirmation

Buttons are hidden when not in edit mode to keep the list clean.

---

## Requirements

| | |
|---|---|
| Traefik Manager (server) | **v0.6.0 or higher** |
| Android | 7.0+ (API 24+) |
| iOS | 16+ (build from source required) |

---

## Tech Stack

Built with [Expo](https://expo.dev) SDK 54 / React Native 0.81, Expo Router, TanStack Query, and Zustand.
