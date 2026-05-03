<script setup>
import { ref } from 'vue'

const copied = ref(false)
const cmd = 'curl -fsSL https://get-traefik.xyzlab.dev | bash'

function copy() {
  navigator.clipboard.writeText(cmd)
  copied.value = true
  setTimeout(() => { copied.value = false }, 2000)
}
</script>

<template>
  <div class="install-wrap">
    <p class="install-label">Install Traefik + Traefik Manager</p>
    <div class="install-box">
      <code class="install-cmd">{{ cmd }}</code>
      <button class="install-copy" @click="copy" :aria-label="copied ? 'Copied' : 'Copy'">
        <svg v-if="!copied" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" width="16" height="16"><path stroke-linecap="round" stroke-linejoin="round" d="M15.75 17.25v3.375c0 .621-.504 1.125-1.125 1.125h-9.75a1.125 1.125 0 0 1-1.125-1.125V7.875c0-.621.504-1.125 1.125-1.125H6.75a9.06 9.06 0 0 1 1.5.124m7.5 10.376h3.375c.621 0 1.125-.504 1.125-1.125V11.25c0-4.46-3.243-8.161-7.5-8.876a9.06 9.06 0 0 0-1.5-.124H9.375c-.621 0-1.125.504-1.125 1.125v3.5m7.5 10.375H9.375a1.125 1.125 0 0 1-1.125-1.125v-9.25m12 6.625v-1.875a3.375 3.375 0 0 0-3.375-3.375h-1.5a1.125 1.125 0 0 1-1.125-1.125v-1.5a3.375 3.375 0 0 0-3.375-3.375H9.75"/></svg>
        <svg v-else xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" width="16" height="16"><path stroke-linecap="round" stroke-linejoin="round" d="M4.5 12.75l6 6 9-13.5"/></svg>
      </button>
    </div>
  </div>
</template>

<style scoped>
.install-wrap {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 48px 24px 0;
}

.install-label {
  font-size: 14px;
  color: var(--vp-c-text-2);
  margin: 0;
}

.install-box {
  display: flex;
  align-items: center;
  gap: 12px;
  background: var(--vp-c-bg-soft);
  border: 1px solid var(--vp-c-divider);
  border-radius: 8px;
  padding: 12px 16px;
}

.install-cmd {
  font-family: var(--vp-font-family-mono, monospace);
  font-size: 13px;
  color: var(--vp-c-text-1);
  white-space: nowrap;
}

.install-copy {
  background: none;
  border: none;
  cursor: pointer;
  color: var(--vp-c-text-2);
  padding: 0;
  display: flex;
  align-items: center;
  transition: color 0.15s;
  flex-shrink: 0;
}

.install-copy:hover {
  color: var(--vp-c-brand-1);
}
</style>
