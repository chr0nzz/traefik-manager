<script setup lang="ts">
import ImageCarousel from './ImageCarousel.vue'

const slides = [
  { light: '/images/light-mobile-connect.png',       dark: '/images/dark-mobile-connect.png',       label: 'Connect' },
  { light: '/images/light-mobile-dashboard.png',     dark: '/images/dark-mobile-dashboard.png',     label: 'Dashboard' },
  { light: '/images/light-mobile-routes.png',        dark: '/images/dark-mobile-routes.png',        label: 'Routes' },
  { light: '/images/light-mobile-routes-add.png',    dark: '/images/dark-mobile-routes-add.png',    label: 'Add Route' },
  { light: '/images/light-mobile-middleware.png',    dark: '/images/dark-mobile-middleware.png',    label: 'Middlewares' },
  { light: '/images/light-mobile-middleware-add.png',dark: '/images/dark-mobile-middleware-add.png',label: 'Add Middleware' },
  { light: '/images/light-mobile-services-live.png', dark: '/images/dark-mobile-services-live.png', label: 'Services' },
  { light: '/images/light-mobile-plugins.png',       dark: '/images/dark-mobile-plugins.png',       label: 'Plugins' },
  { light: '/images/light-mobile-certs.png',         dark: '/images/dark-mobile-certs.png',         label: 'Certificates' },
  { light: '/images/light-mobile-logs.png',          dark: '/images/dark-mobile-logs.png',          label: 'Logs' },
  { light: '/images/light-mobile-settings.png',      dark: '/images/dark-mobile-settings.png',      label: 'Settings' },
]
</script>

<template>
  <ImageCarousel :slides="slides" :portrait="true" />
</template>
