<script setup lang="ts">
import ImageCarousel from './ImageCarousel.vue'

const slides = [
  { light: '/images/light-setup-temp-pass-1.png',     dark: '/images/dark-setup-temp-pass-1.png',     label: 'Setup – Step 1: Temporary Password' },
  { light: '/images/light-setup-welcome-2.png',       dark: '/images/dark-setup-welcome-2.png',       label: 'Setup – Step 2: Welcome' },
  { light: '/images/light-setup-conn-dom-3.png',      dark: '/images/dark-setup-conn-dom-3.png',      label: 'Setup – Step 3: Connection & Domains' },
  { light: '/images/light-setup-opt-tabs-4.png',      dark: '/images/dark-setup-opt-tabs-4.png',      label: 'Setup – Step 4: Optional Tabs' },
  { light: '/images/light-setup-set-pass-5.png',      dark: '/images/dark-setup-set-pass-5.png',      label: 'Setup – Step 5: Set Password' },
  { light: '/images/light-dashboard.png',             dark: '/images/dark-dashboard.png',             label: 'Dashboard – Main View' },
  { light: '/images/light-dashboard-compact.png',     dark: '/images/dark-dashboard-compact.png',     label: 'Dashboard – Compact Stats' },
  { light: '/images/light-dashboard-no-widgets.png',  dark: '/images/dark-dashboard-no-widgets.png',  label: 'Dashboard – No Widgets' },
  { light: '/images/light-dashboard-edit-gorup.png',  dark: '/images/dark-dashboard-edit-group.png',  label: 'Dashboard – Edit Group' },
  { light: '/images/light-dashboard-edit route.png',  dark: '/images/dark-dashboard-edit-route.png',  label: 'Dashboard – Edit Route Card' },
  { light: '/images/light-route-map.png',             dark: '/images/dark-route-map.png',             label: 'Route Map – Topology View' },
  { light: '/images/light-route-map-hover.png',       dark: '/images/dark-route-map-hover.png',       label: 'Route Map – Hover Highlight' },
  { light: '/images/light-routes.png',                dark: '/images/dark-routes.png',                label: 'Routes – Overview' },
  { light: '/images/light-route-details.png',         dark: '/images/dark-route-details.png',         label: 'Routes – Details' },
  { light: '/images/light-route-edit.png',            dark: '/images/dark-route-edit.png',            label: 'Routes – Editing' },
  { light: '/images/light-route-add-http.png',        dark: '/images/dark-route-add-http.png',        label: 'Routes – Add HTTP Route' },
  { light: '/images/light-route-add-tcp.png',         dark: '/images/dark-route-add-tcp.png',         label: 'Routes – Add TCP Route' },
  { light: '/images/light-route-add-udp.png',         dark: '/images/dark-route-add-udp.png',         label: 'Routes – Add UDP Route' },
  { light: '/images/light-services.png',              dark: '/images/dark-services.png',              label: 'Services – Overview' },
  { light: '/images/light-services-details.png',      dark: '/images/dark-services-details.png',      label: 'Services – Details' },
  { light: '/images/light-middleware.png',            dark: '/images/dark-middleware.png',            label: 'Middlewares – List' },
  { light: '/images/light-middleware-edit.png',       dark: '/images/dark-middleware-edit.png',       label: 'Middlewares – Edit' },
  { light: '/images/light-middleware-add.png',        dark: '/images/dark-middleware-add.png',        label: 'Middlewares – Add' },
  { light: '/images/light-plugins.png',               dark: '/images/dark-plugins.png',               label: 'Plugins – List' },
  { light: '/images/light-plugins-details.png',       dark: '/images/dark-plugins-details.png',       label: 'Plugins – Details' },
  { light: '/images/light-certs.png',                 dark: '/images/dark-certs.png',                 label: 'Certificates' },
  { light: '/images/light-docker.png',               dark: '/images/dark-docker.png',               label: 'Docker – Routes' },
  { light: '/images/light-docker-details.png',       dark: '/images/dark-docker-details.png',       label: 'Docker – Route Details' },
  { light: '/images/light-logs.png',                  dark: '/images/dark-logs.png',                  label: 'Logs' },
  { light: '/images/light-settings-auth.png',         dark: '/images/dark-settins-auth.png',          label: 'Settings – Authentication' },
  { light: '/images/light-settings-connections.png',  dark: '/images/dark-settins-connections.png',   label: 'Settings – Connections' },
  { light: '/images/light-settings-routes.png',       dark: '/images/dark-settins-routes.png',        label: 'Settings – Routes Config' },
  { light: '/images/light-settings-backups.png',      dark: '/images/dark-settins-backups.png',       label: 'Settings – Backups' },
  { light: '/images/light-settings-system.png',       dark: '/images/dark-settins-system.png',        label: 'Settings – System' },
  { light: '/images/light-settings-ui.png',           dark: '/images/dark-settins-ui.png',            label: 'Settings – UI Preferences' },
]
</script>

<template>
  <ImageCarousel :slides="slides" />
</template>
