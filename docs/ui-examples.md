# Traefik Manager – UI Examples

<style>
.ui-img-dark { display: none; }
.ui-theme-dark .ui-img-light { display: none; }
.ui-theme-dark .ui-img-dark { display: block; }
#ui-theme-toggle {
  display: inline-flex; align-items: center; gap: 8px;
  padding: 6px 14px; border-radius: 6px; border: 1px solid #888;
  background: transparent; cursor: pointer; font-size: 14px;
  margin-bottom: 20px;
}
#ui-theme-toggle:hover { background: rgba(128,128,128,0.15); }
</style>

<button id="ui-theme-toggle" onclick="uiToggleTheme()">🌙 Switch to Dark</button>

<script>
function uiToggleTheme() {
  const el = document.getElementById('ui-examples-wrap');
  const btn = document.getElementById('ui-theme-toggle');
  if (!el || !btn) return;
  const isDark = el.classList.toggle('ui-theme-dark');
  btn.textContent = isDark ? '☀️ Switch to Light' : '🌙 Switch to Dark';
  localStorage.setItem('ui-ex-theme', isDark ? 'dark' : 'light');
}

function uiInitTheme() {
  const saved = localStorage.getItem('ui-ex-theme');
  const el = document.getElementById('ui-examples-wrap');
  const btn = document.getElementById('ui-theme-toggle');
  if (!el || !btn) return;
  if (saved === 'dark') {
    el.classList.add('ui-theme-dark');
    btn.textContent = '☀️ Switch to Light';
  } else {
    el.classList.remove('ui-theme-dark');
    btn.textContent = '🌙 Switch to Dark';
  }
}

// MkDocs Material instant navigation — fires on every page load/navigation
if (typeof document$ !== 'undefined') {
  document$.subscribe(uiInitTheme);
} else {
  document.addEventListener('DOMContentLoaded', uiInitTheme);
}
</script>

<div id="ui-examples-wrap">

---

## Table of Contents

- [Initial Setup](#initial-setup)
- [Dashboard](#dashboard)
- [Routes](#routes)
- [Services](#services)
- [Middlewares](#middlewares)
- [Plugins](#plugins)
- [Certificates](#certificates)
- [Docker](#docker)
- [Logs](#logs)
- [Settings](#settings)

---

# Initial Setup

When first launching Traefik Manager you are guided through a short setup wizard.

> **Screenshots coming soon** — setup screen is currently in development.

---

# Dashboard

The dashboard shows a live overview of your Traefik instance with stat cards, entrypoints bar, and quick-navigate links.

## Expanded Stats

<img class="ui-img-light" src="images/light-routes.png" alt="Dashboard – expanded stats (light)">
<img class="ui-img-dark"  src="images/dark-routes.png"  alt="Dashboard – expanded stats (dark)">

## Compact Stats

<img class="ui-img-light" src="images/light-compact-stats.png" alt="Dashboard – expanded stats (light)">
<img class="ui-img-dark"  src="images/dark-compact-stats.png"  alt="Dashboard – expanded stats (dark)">

## Hidden Stats

<img class="ui-img-light" src="images/light-hidden-stats.png" alt="Dashboard – stats hidden (light)">
<img class="ui-img-dark"  src="images/dark-hidden-stats.png"  alt="Dashboard – stats hidden (dark)">

---

# Routes

Routes define how incoming traffic is forwarded to backend services.

## Routes Overview

<img class="ui-img-light" src="images/light-routes.png" alt="Routes overview (light)">
<img class="ui-img-dark"  src="images/dark-routes.png"  alt="Routes overview (dark)">

## Route Details

<img class="ui-img-light" src="images/light-route-details.png" alt="Route details (light)">
<img class="ui-img-dark"  src="images/dark-route-details.png"  alt="Route details (dark)">

## Editing a Route

<img class="ui-img-light" src="images/light-route-edit.png" alt="Route edit (light)">
<img class="ui-img-dark"  src="images/dark-route-edit.png"  alt="Route edit (dark)">

## Adding an HTTP Route

<img class="ui-img-light" src="images/light-route-add-http.png" alt="Add HTTP route (light)">
<img class="ui-img-dark"  src="images/dark-route-add-http.png"  alt="Add HTTP route (dark)">

## Adding a TCP Route

<img class="ui-img-light" src="images/light-route-add-tcp.png" alt="Add TCP route (light)">
<img class="ui-img-dark"  src="images/dark-route-add-tcp.png"  alt="Add TCP route (dark)">

## Adding a UDP Route

<img class="ui-img-light" src="images/light-route-add-udp.png" alt="Add UDP route (light)">
<img class="ui-img-dark"  src="images/dark-route-add-udp.png"  alt="Add UDP route (dark)">

---

# Services

Services represent the backend targets that Traefik forwards traffic to.

## Services Overview

<img class="ui-img-light" src="images/light-services.png" alt="Services overview (light)">
<img class="ui-img-dark"  src="images/dark-services.png"  alt="Services overview (dark)">

## Service Details

<img class="ui-img-light" src="images/light-services-details.png" alt="Service details (light)">
<img class="ui-img-dark"  src="images/dark-services-details.png"  alt="Service details (dark)">

---

# Middlewares

Middlewares modify requests before they reach your services — authentication, rate limiting, headers, redirects, and more.

## Middleware List

<img class="ui-img-light" src="images/light-middleware.png" alt="Middleware list (light)">
<img class="ui-img-dark"  src="images/dark-middleware.png"  alt="Middleware list (dark)">

## Editing Middleware

<img class="ui-img-light" src="images/light-middleware-edit.png" alt="Middleware edit (light)">
<img class="ui-img-dark"  src="images/dark-middleware-edit.png"  alt="Middleware edit (dark)">

## Adding Middleware

<img class="ui-img-light" src="images/light-middleware-add.png" alt="Add middleware (light)">
<img class="ui-img-dark"  src="images/dark-middleware-add.png"  alt="Add middleware (dark)">

---

# Plugins

View and monitor active Traefik plugins.

## Plugin List

<img class="ui-img-light" src="images/light-plugins.png" alt="Plugin list (light)">
<img class="ui-img-dark"  src="images/dark-plugins.png"  alt="Plugin list (dark)">

## Plugin Details

<img class="ui-img-light" src="images/light-plugins-details.png" alt="Plugin details (light)">
<img class="ui-img-dark"  src="images/dark-plugins-details.png"  alt="Plugin details (dark)">

---

# Certificates

View and monitor TLS certificates managed by Traefik.

## Certificates View

<img class="ui-img-light" src="images/light-certs.png" alt="Certificates (light)">
<img class="ui-img-dark"  src="images/dark-certs.png"  alt="Certificates (dark)">

---

# Docker

Inspect routes and services discovered via the Docker provider, including container labels and health state.

## Docker Routes

<img class="ui-img-light" src="images/light-docker.png" alt="Docker routes (light)">
<img class="ui-img-dark"  src="images/dark-docker.png"  alt="Docker routes (dark)">

## Docker Route Details

<img class="ui-img-light" src="images/light-docker-details.png" alt="Docker route details (light)">
<img class="ui-img-dark"  src="images/dark-docker-details.png"  alt="Docker route details (dark)">

---

# Logs

Live and historical Traefik access logs with line-count control and filtering.

## Logs View

<img class="ui-img-light" src="images/light-logs.png" alt="Logs (light)">
<img class="ui-img-dark"  src="images/dark-logs.png"  alt="Logs (dark)">

---

# Settings

## Authentication

<img class="ui-img-light" src="images/light-settings-auth.png" alt="Settings – authentication (light)">
<img class="ui-img-dark"  src="images/dark-settins-auth.png"  alt="Settings – authentication (dark)">

## Connections

<img class="ui-img-light" src="images/light-settings-connections.png" alt="Settings – connections (light)">
<img class="ui-img-dark"  src="images/dark-settins-connections.png"  alt="Settings – connections (dark)">

## Routes Config

<img class="ui-img-light" src="images/light-settings-routes.png" alt="Settings – routes (light)">
<img class="ui-img-dark"  src="images/dark-settins-routes.png"  alt="Settings – routes (dark)">

## Backups

<img class="ui-img-light" src="images/light-settings-backups.png" alt="Settings – backups (light)">
<img class="ui-img-dark"  src="images/dark-settins-backups.png"  alt="Settings – backups (dark)">

## System

<img class="ui-img-light" src="images/light-settings-system.png" alt="Settings – system (light)">
<img class="ui-img-dark"  src="images/dark-settins-system.png"  alt="Settings – system (dark)">

## UI Preferences

<img class="ui-img-light" src="images/light-settings-ui.png" alt="Settings – UI preferences (light)">
<img class="ui-img-dark"  src="images/dark-settins-ui.png"  alt="Settings – UI preferences (dark)">

</div>
