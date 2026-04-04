<script setup lang="ts">
import { ref, onMounted } from 'vue'

const merged = ref<boolean | null>(null)

onMounted(async () => {
  try {
    const res  = await fetch('https://api.github.com/repos/selfhosters/unRAID-CA-templates/pulls/661')
    const data = await res.json()
    merged.value = data.merged === true || data.state === 'closed'
  } catch {
    merged.value = null
  }
})
</script>

<template>
  <div v-if="merged === null" class="ca-status ca-status--loading">
    Checking Community Applications status...
  </div>
  <div v-else-if="merged" class="ca-status ca-status--available">
    ✅ Available in Community Applications - search for <strong>Traefik Manager</strong> in the Apps tab.
  </div>
  <div v-else class="ca-status ca-status--pending">
    ⏳ Pending approval in the Community Applications repository -
    <a href="https://github.com/selfhosters/unRAID-CA-templates/pull/661" target="_blank" rel="noopener noreferrer">
      track the PR here
    </a>.
    Install manually in the meantime by downloading the
    <a href="https://raw.githubusercontent.com/chr0nzz/traefik-manager/main/unraid/traefik-manager.xml" target="_blank" rel="noopener noreferrer">
      template XML
    </a>
    and importing it via Apps → Settings → Import.
  </div>
</template>

<style scoped>
.ca-status {
  padding: 12px 16px;
  border-radius: 8px;
  font-size: 14px;
  margin: 16px 0;
  border: 1px solid;
}
.ca-status--loading {
  border-color: var(--vp-c-border);
  color: var(--vp-c-text-2);
}
.ca-status--available {
  border-color: var(--vp-c-green-2);
  background: var(--vp-c-green-soft);
  color: var(--vp-c-green-1);
}
.ca-status--pending {
  border-color: var(--vp-c-yellow-2);
  background: var(--vp-c-yellow-soft);
  color: var(--vp-c-text-1);
}
</style>
