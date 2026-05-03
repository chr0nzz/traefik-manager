<script setup lang="ts">
import ImageCarousel from './ImageCarousel.vue'

const slides = [
  { light: '/images/light-login.png',                  dark: '/images/dark-login.png',                  label: 'Login' },
  { light: '/images/light-setup-welcome.png',          dark: '/images/dark-setup-welcome.png',          label: 'Setup – Welcome' },
  { light: '/images/light-setup-connection.png',       dark: '/images/dark-setup-connection.png',       label: 'Setup – Connection & Domains' },
  { light: '/images/light-setup-self-route.png',       dark: '/images/dark-setup-self-route.png',       label: 'Setup – Self Route' },
  { light: '/images/light-setup-monitoring.png',       dark: '/images/dark-setup-monitoring.png',       label: 'Setup – Optional Tabs' },
  { light: '/images/light-setup-password.png',         dark: '/images/dark-setup-password.png',         label: 'Setup – Set Password' },
  { light: '/images/light-dashboard.png',              dark: '/images/dark-dashboard.png',              label: 'Dashboard' },
  { light: '/images/light-route-map.png',              dark: '/images/dark-route-map.png',              label: 'Route Map' },
  { light: '/images/light-routes-cards.png',           dark: '/images/dark-routes-cards.png',           label: 'Routes – Card View' },
  { light: '/images/light-routes-list.png',            dark: '/images/dark-routes-list.png',            label: 'Routes – List View' },
  { light: '/images/light-routes-add-http.png',        dark: '/images/dark-routes-add-http.png',        label: 'Routes – Add HTTP Route' },
  { light: '/images/light-routes-add-tcp.png',         dark: '/images/dark-routes-add-tcp.png',         label: 'Routes – Add TCP Route' },
  { light: '/images/light-routes-add-udp.png',         dark: '/images/dark-routes-add-udp.png',         label: 'Routes – Add UDP Route' },
  { light: '/images/light-middlewares-cards.png',      dark: '/images/dark-middlewares-cards.png',      label: 'Middlewares – Card View' },
  { light: '/images/light-middlewares-list.png',       dark: '/images/dark-middlewares-list.png',       label: 'Middlewares – List View' },
  { light: '/images/light-middlewares-add.png',        dark: '/images/dark-middlewares-add.png',        label: 'Middlewares – Add' },
  { light: '/images/light-services-cards.png',         dark: '/images/dark-services-cards.png',         label: 'Services – Card View' },
  { light: '/images/light-services-list.png',          dark: '/images/dark-services-list.png',          label: 'Services – List View' },
  { light: '/images/light-plugins.png',                dark: '/images/dark-plugins.png',                label: 'Plugins' },
  { light: '/images/light-plugins-add.png',            dark: '/images/dark-plugins-add.png',            label: 'Plugins – Add' },
  { light: '/images/light-settings-interface.png',     dark: '/images/dark-settings-interface.png',     label: 'Settings – Interface' },
  { light: '/images/light-settings-auth-password.png', dark: '/images/dark-settings-auth-password.png', label: 'Settings – Authentication' },
  { light: '/images/light-settings-auth-apikeys.png',  dark: '/images/dark-settings-auth-apikeys.png',  label: 'Settings – API Keys' },
  { light: '/images/light-settings-auth-oidc.png',     dark: '/images/dark-settings-auth-oidc.png',     label: 'Settings – OIDC / SSO' },
  { light: '/images/light-settings-static-config.png', dark: '/images/dark-settings-static-config.png', label: 'Settings – Static Config' },
  { light: '/images/light-settings-backups.png',       dark: '/images/dark-settings-backups.png',       label: 'Settings – Backups' },
  { light: '/images/light-settings-system.png',        dark: '/images/dark-settings-system.png',        label: 'Settings – System Monitoring' },
  { light: '/images/light-settings-routes.png',        dark: '/images/dark-settings-routes.png',        label: 'Settings – Route Monitoring' },
  { light: '/images/light-settings-connection.png',    dark: '/images/dark-settings-connection.png',    label: 'Settings – Connection' },
  { light: '/images/light-settings-about.png',         dark: '/images/dark-settings-about.png',         label: 'Settings – About' },
]
</script>

<template>
  <ImageCarousel :slides="slides" />
</template>
