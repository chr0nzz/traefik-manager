<script setup lang="ts">
import ImageCarousel from './ImageCarousel.vue'

const slides = [
  { light: '/images/light-mobile-connect-1.png',    dark: '/images/dark-mobile-connect-1.png',    label: 'Connect' },
  { light: '/images/light-mobile-dashboard-2.png',  dark: '/images/dark-mobile-dashboard-2.png',  label: 'Dashboard' },
  { light: '/images/light-mobile-routes-3.png',     dark: '/images/dark-mobile-routes-3.png',     label: 'Routes' },
  { light: '/images/light-mobile-middleware-4.png', dark: '/images/dark-mobile-middleware-4.png', label: 'Middlewares' },
  { light: '/images/light-mobile-services-5.png',   dark: '/images/dark-mobile-services-5.png',   label: 'Services' },
  { light: '/images/light-mobile-settings-6.png',   dark: '/images/dark-mobile-settings-6.png',   label: 'Settings' },
]
</script>

<template>
  <ImageCarousel :slides="slides" :portrait="true" />
</template>
