<script setup lang="ts">
import { ref, onMounted } from 'vue'

const stars = ref<number | null>(null)

onMounted(async () => {
  try {
    const res = await fetch('https://api.github.com/repos/chr0nzz/traefik-manager')
    const data = await res.json()
    stars.value = data.stargazers_count
  } catch {}
})

function fmt(n: number): string {
  return n >= 1000 ? (n / 1000).toFixed(1) + 'k' : String(n)
}
</script>

<template>
  <a
    href="https://github.com/chr0nzz/traefik-manager"
    target="_blank"
    rel="noopener noreferrer"
    class="gh-stars"
  >
    <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
      <path d="M12 .587l3.668 7.568L24 9.306l-6 5.854 1.416 8.275L12 19.144l-7.416 4.291L6 15.16 0 9.306l8.332-1.151z"/>
    </svg>
    <span>Star</span>
    <span v-if="stars !== null" class="gh-stars-count">{{ fmt(stars) }}</span>
  </a>
</template>
