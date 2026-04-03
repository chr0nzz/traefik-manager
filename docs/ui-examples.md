# Traefik Manager – UI Examples

<style>
.ui-img-dark { display: none; }
.ui-theme-dark .ui-img-light { display: none; }
.ui-theme-dark .ui-img-dark { display: block; }
#ui-theme-toggle-wrap {
  display: flex; justify-content: center; margin-top: 24px; margin-bottom: 24px;
}
#ui-theme-toggle {
  display: inline-flex; align-items: center; gap: 8px;
  padding: 8px 20px; border-radius: 6px; border: 1px solid #888;
  background: transparent; cursor: pointer; font-size: 14px;
}
#ui-theme-toggle:hover { background: rgba(128,128,128,0.15); }
</style>

<div id="ui-theme-toggle-wrap">
  <button id="ui-theme-toggle" onclick="uiToggleTheme()">🌙 View Dark Theme</button>
</div>

<script>
if (typeof window !== 'undefined') {
  window.uiToggleTheme = function() {
    const el = document.getElementById('ui-examples-wrap');
    const btn = document.getElementById('ui-theme-toggle');
    if (!el || !btn) return;
    const isDark = el.classList.toggle('ui-theme-dark');
    btn.textContent = isDark ? '☀️ View Light Theme' : '🌙 View Dark Theme';
    localStorage.setItem('ui-ex-theme', isDark ? 'dark' : 'light');
  };

  function uiInitTheme() {
    const saved = localStorage.getItem('ui-ex-theme');
    const el = document.getElementById('ui-examples-wrap');
    const btn = document.getElementById('ui-theme-toggle');
    if (!el || !btn) return;
    if (saved === 'dark') {
      el.classList.add('ui-theme-dark');
      btn.textContent = '☀️ View Light Theme';
    } else {
      el.classList.remove('ui-theme-dark');
      btn.textContent = '🌙 View Dark Theme';
    }
  }

  setTimeout(uiInitTheme, 0);
}
</script>

<div id="ui-examples-wrap">

---


## Initial Setup

When first launching Traefik Manager you are guided through a short setup wizard.

### Step 1 - Temporary password

<img class="ui-img-light" src="/images/light-setup-temp-pass-1.png" alt="Step 1 – Temporary password (light)">
<img class="ui-img-dark"  src="/images/dark-setup-temp-pass-1.png"  alt="Step 1 – Temporary password (dark)">

### Step 2 - Welcome

<img class="ui-img-light" src="/images/light-setup-welcome-2.png" alt="Step 2 – Welcome (light)">
<img class="ui-img-dark"  src="/images/dark-setup-welcome-2.png"  alt="Step 2 – Welcome (dark)">

### Step 3 - Connection &amp; domains

<img class="ui-img-light" src="/images/light-setup-conn-dom-3.png" alt="Step 3 – Connection and domains (light)">
<img class="ui-img-dark"  src="/images/dark-setup-conn-dom-3.png"  alt="Step 3 – Connection and domains (dark)">

### Step 4 - Optional tabs

<img class="ui-img-light" src="/images/light-setup-opt-tabs-4.png" alt="Step 4 – Optional tabs (light)">
<img class="ui-img-dark"  src="/images/dark-setup-opt-tabs-4.png"  alt="Step 4 – Optional tabs (dark)">

### Step 5 - Set password

<img class="ui-img-light" src="/images/light-setup-set-pass-5.png" alt="Step 5 – Set password (light)">
<img class="ui-img-dark"  src="/images/dark-setup-set-pass-5.png"  alt="Step 5 – Set password (dark)">

---

## Dashboard

The dashboard shows app cards grouped by category with app icons, stat widgets, and quick-access controls. Cards can be customised per-route with a display name, icon override, and group override.

### Main View

<img class="ui-img-light" src="/images/light-dashboard.png" alt="Dashboard (light)">
<img class="ui-img-dark"  src="/images/dark-dashboard.png"  alt="Dashboard (dark)">

### Compact Stats

<img class="ui-img-light" src="/images/light-dashboard-compact.png" alt="Dashboard – compact stats (light)">
<img class="ui-img-dark"  src="/images/dark-dashboard-compact.png"  alt="Dashboard – compact stats (dark)">

### No Widgets

<img class="ui-img-light" src="/images/light-dashboard-no-widgets.png" alt="Dashboard – no widgets (light)">
<img class="ui-img-dark"  src="/images/dark-dashboard-no-widgets.png"  alt="Dashboard – no widgets (dark)">

### Edit Group

<img class="ui-img-light" src="/images/light-dashboard-edit-gorup.png" alt="Dashboard – edit group (light)">
<img class="ui-img-dark"  src="/images/dark-dashboard-edit-group.png"  alt="Dashboard – edit group (dark)">

### Edit Route Card

<img class="ui-img-light" src="/images/light-dashboard-edit route.png" alt="Dashboard – edit route card (light)">
<img class="ui-img-dark"  src="/images/dark-dashboard-edit-route.png"  alt="Dashboard – edit route card (dark)">

---

## Route Map

The Route Map tab shows a 4-column topology view of your Traefik setup - Entry Points, Routes, Middlewares, and Services - connected by Bezier curves.

### Topology View

<img class="ui-img-light" src="/images/light-route-map.png" alt="Route Map (light)">
<img class="ui-img-dark"  src="/images/dark-route-map.png"  alt="Route Map (dark)">

### Hover Highlight

Hovering a route dims all unrelated nodes and animates the connected entry point, middlewares, and service into alignment.

<img class="ui-img-light" src="/images/light-route-map-hover.png" alt="Route Map – hover highlight (light)">
<img class="ui-img-dark"  src="/images/dark-route-map-hover.png"  alt="Route Map – hover highlight (dark)">

---

## Routes

Routes define how incoming traffic is forwarded to backend services.

### Routes Overview

<img class="ui-img-light" src="/images/light-routes.png" alt="Routes overview (light)">
<img class="ui-img-dark"  src="/images/dark-routes.png"  alt="Routes overview (dark)">

### Route Details

<img class="ui-img-light" src="/images/light-route-details.png" alt="Route details (light)">
<img class="ui-img-dark"  src="/images/dark-route-details.png"  alt="Route details (dark)">

### Editing a Route

<img class="ui-img-light" src="/images/light-route-edit.png" alt="Route edit (light)">
<img class="ui-img-dark"  src="/images/dark-route-edit.png"  alt="Route edit (dark)">

### Adding an HTTP Route

<img class="ui-img-light" src="/images/light-route-add-http.png" alt="Add HTTP route (light)">
<img class="ui-img-dark"  src="/images/dark-route-add-http.png"  alt="Add HTTP route (dark)">

### Adding a TCP Route

<img class="ui-img-light" src="/images/light-route-add-tcp.png" alt="Add TCP route (light)">
<img class="ui-img-dark"  src="/images/dark-route-add-tcp.png"  alt="Add TCP route (dark)">

### Adding a UDP Route

<img class="ui-img-light" src="/images/light-route-add-udp.png" alt="Add UDP route (light)">
<img class="ui-img-dark"  src="/images/dark-route-add-udp.png"  alt="Add UDP route (dark)">

---

## Services

Services represent the backend targets that Traefik forwards traffic to.

### Services Overview

<img class="ui-img-light" src="/images/light-services.png" alt="Services overview (light)">
<img class="ui-img-dark"  src="/images/dark-services.png"  alt="Services overview (dark)">

### Service Details

<img class="ui-img-light" src="/images/light-services-details.png" alt="Service details (light)">
<img class="ui-img-dark"  src="/images/dark-services-details.png"  alt="Service details (dark)">

---

## Middlewares

Middlewares modify requests before they reach your services - authentication, rate limiting, headers, redirects, and more.

### Middleware List

<img class="ui-img-light" src="/images/light-middleware.png" alt="Middleware list (light)">
<img class="ui-img-dark"  src="/images/dark-middleware.png"  alt="Middleware list (dark)">

### Editing Middleware

<img class="ui-img-light" src="/images/light-middleware-edit.png" alt="Middleware edit (light)">
<img class="ui-img-dark"  src="/images/dark-middleware-edit.png"  alt="Middleware edit (dark)">

### Adding Middleware

<img class="ui-img-light" src="/images/light-middleware-add.png" alt="Add middleware (light)">
<img class="ui-img-dark"  src="/images/dark-middleware-add.png"  alt="Add middleware (dark)">

---

## Plugins

View and monitor active Traefik plugins.

### Plugin List

<img class="ui-img-light" src="/images/light-plugins.png" alt="Plugin list (light)">
<img class="ui-img-dark"  src="/images/dark-plugins.png"  alt="Plugin list (dark)">

### Plugin Details

<img class="ui-img-light" src="/images/light-plugins-details.png" alt="Plugin details (light)">
<img class="ui-img-dark"  src="/images/dark-plugins-details.png"  alt="Plugin details (dark)">

---

## Certificates

View and monitor TLS certificates managed by Traefik.

### Certificates View

<img class="ui-img-light" src="/images/light-certs.png" alt="Certificates (light)">
<img class="ui-img-dark"  src="/images/dark-certs.png"  alt="Certificates (dark)">

---

## Docker

Inspect routes and services discovered via the Docker provider, including container labels and health state.

### Docker Routes

<img class="ui-img-light" src="/images/light-docker.png" alt="Docker routes (light)">
<img class="ui-img-dark"  src="/images/dark-docker.png"  alt="Docker routes (dark)">

### Docker Route Details

<img class="ui-img-light" src="/images/light-docker-details.png" alt="Docker route details (light)">
<img class="ui-img-dark"  src="/images/dark-docker-details.png"  alt="Docker route details (dark)">

---

## Logs

Live and historical Traefik access logs with line-count control and filtering.

### Logs View

<img class="ui-img-light" src="/images/light-logs.png" alt="Logs (light)">
<img class="ui-img-dark"  src="/images/dark-logs.png"  alt="Logs (dark)">

---

## Settings

### Authentication

<img class="ui-img-light" src="/images/light-settings-auth.png" alt="Settings – authentication (light)">
<img class="ui-img-dark"  src="/images/dark-settins-auth.png"  alt="Settings – authentication (dark)">

### Connections

<img class="ui-img-light" src="/images/light-settings-connections.png" alt="Settings – connections (light)">
<img class="ui-img-dark"  src="/images/dark-settins-connections.png"  alt="Settings – connections (dark)">

### Routes Config

<img class="ui-img-light" src="/images/light-settings-routes.png" alt="Settings – routes (light)">
<img class="ui-img-dark"  src="/images/dark-settins-routes.png"  alt="Settings – routes (dark)">

### Backups

<img class="ui-img-light" src="/images/light-settings-backups.png" alt="Settings – backups (light)">
<img class="ui-img-dark"  src="/images/dark-settins-backups.png"  alt="Settings – backups (dark)">

### System

<img class="ui-img-light" src="/images/light-settings-system.png" alt="Settings – system (light)">
<img class="ui-img-dark"  src="/images/dark-settins-system.png"  alt="Settings – system (dark)">

### UI Preferences

<img class="ui-img-light" src="/images/light-settings-ui.png" alt="Settings – UI preferences (light)">
<img class="ui-img-dark"  src="/images/dark-settins-ui.png"  alt="Settings – UI preferences (dark)">

</div>
