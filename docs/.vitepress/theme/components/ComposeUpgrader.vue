<script setup lang="ts">
import { ref, computed } from 'vue'
import yaml from 'js-yaml'

const input = ref('')
const output = ref('')
const restartMethod = ref('proxy')
const enableStatic = ref(false)
const staticHostPath = ref('')
const error = ref('')
const copied = ref(false)

const needsStaticPath = computed(() => {
  if (!enableStatic.value || !input.value.trim()) return false
  try {
    const doc = yaml.load(input.value) as any
    const services = doc?.services || {}
    const tmService = Object.values(services).find((s: any) =>
      s?.image?.includes('traefik-manager')
    ) as any
    if (!tmService?.volumes) return true
    return !tmService.volumes.some((v: any) =>
      typeof v === 'string' && v.includes('/app/traefik.yml')
    )
  } catch {
    return false
  }
})

function upgrade() {
  error.value = ''
  output.value = ''

  if (!input.value.trim()) {
    error.value = 'Paste your docker-compose content first.'
    return
  }

  try {
    const doc = yaml.load(input.value) as any

    if (!doc?.services) {
      error.value = 'No services found in compose file.'
      return
    }

    const tmKey = Object.keys(doc.services).find((k) =>
      doc.services[k]?.image?.includes('traefik-manager')
    )

    if (!tmKey) {
      error.value = 'No traefik-manager service found in compose file.'
      return
    }

    const svc = doc.services[tmKey]

    svc.image = svc.image.replace(/:(latest|\d+\.\d+\.\d+[\w.-]*)$/, ':beta')
    if (!svc.image.endsWith(':beta')) svc.image += ':beta'

    if (!svc.environment) {
      svc.environment = {}
    } else if (Array.isArray(svc.environment)) {
      const obj: Record<string, string> = {}
      svc.environment.forEach((e: string) => {
        const idx = e.indexOf('=')
        if (idx > -1) obj[e.slice(0, idx)] = e.slice(idx + 1)
        else obj[e] = ''
      })
      svc.environment = obj
    }

    if (restartMethod.value === 'proxy') {
      svc.environment['RESTART_METHOD'] = 'proxy'
      svc.environment['DOCKER_HOST'] = 'tcp://socket-proxy:2375'
      svc.environment['TRAEFIK_CONTAINER'] = 'traefik'
    } else if (restartMethod.value === 'poison-pill') {
      svc.environment['RESTART_METHOD'] = 'poison-pill'
      svc.environment['SIGNAL_FILE_PATH'] = '/signals/restart.sig'
    } else if (restartMethod.value === 'socket') {
      svc.environment['RESTART_METHOD'] = 'socket'
      svc.environment['TRAEFIK_CONTAINER'] = 'traefik'
    }

    if (enableStatic.value) {
      svc.environment['STATIC_CONFIG_PATH'] = '/app/traefik.yml'

      if (!svc.volumes) svc.volumes = []

      const existingIdx = svc.volumes.findIndex((v: any) =>
        typeof v === 'string' && v.includes('/app/traefik.yml')
      )

      if (existingIdx > -1) {
        svc.volumes[existingIdx] = (svc.volumes[existingIdx] as string).replace(/:ro$/, '')
      } else {
        const hostPath = staticHostPath.value.trim() || './traefik.yml'
        svc.volumes.push(`${hostPath}:/app/traefik.yml`)
      }
    }

    if (restartMethod.value === 'poison-pill') {
      if (!svc.volumes) svc.volumes = []
      if (!svc.volumes.includes('traefik-signals:/signals')) {
        svc.volumes.push('traefik-signals:/signals')
      }
      if (!doc.volumes) doc.volumes = {}
      if (!('traefik-signals' in doc.volumes)) {
        doc.volumes['traefik-signals'] = null
      }
    }

    if (restartMethod.value === 'socket') {
      if (!svc.volumes) svc.volumes = []
      const socketMount = '/var/run/docker.sock:/var/run/docker.sock:ro'
      if (!svc.volumes.includes(socketMount)) {
        svc.volumes.push(socketMount)
      }
    }

    output.value = yaml.dump(doc, { indent: 2, lineWidth: -1, noRefs: true })
  } catch (e: any) {
    error.value = `Failed to parse YAML: ${e.message}`
  }
}

async function copy() {
  if (!output.value) return
  await navigator.clipboard.writeText(output.value)
  copied.value = true
  setTimeout(() => (copied.value = false), 2000)
}
</script>

<template>
  <div class="upgrader">
    <div class="field">
      <label>Your current compose</label>
      <textarea v-model="input" placeholder="Paste your docker-compose.yml here..." rows="12" />
    </div>

    <div class="options">
      <div class="field">
        <label>Restart method</label>
        <select v-model="restartMethod">
          <option value="proxy">Socket proxy (recommended)</option>
          <option value="poison-pill">Poison pill</option>
          <option value="socket">Direct socket</option>
        </select>
      </div>

      <div class="field checkbox">
        <label>
          <input type="checkbox" v-model="enableStatic" />
          Enable Static Config editor
        </label>
      </div>

      <div class="field" v-if="enableStatic && needsStaticPath">
        <label>Host path to traefik.yml</label>
        <input type="text" v-model="staticHostPath" placeholder="e.g. /home/user/traefik/traefik.yml" />
      </div>
    </div>

    <button class="upgrade-btn" @click="upgrade">Upgrade</button>

    <div class="error" v-if="error">{{ error }}</div>

    <div class="output-block" v-if="output">
      <div class="output-header">
        <label>Upgraded compose</label>
        <button class="copy-btn" @click="copy">{{ copied ? 'Copied!' : 'Copy' }}</button>
      </div>
      <textarea :value="output" readonly rows="16" />
    </div>
  </div>
</template>

<style scoped>
.upgrader {
  display: flex;
  flex-direction: column;
  gap: 16px;
  margin: 24px 0;
}
.field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.field label {
  font-size: 14px;
  font-weight: 500;
  color: var(--vp-c-text-1);
}
.field textarea,
.field input[type='text'],
.field select {
  padding: 8px 10px;
  border: 1px solid var(--vp-c-divider);
  border-radius: 6px;
  background: var(--vp-c-bg-soft);
  color: var(--vp-c-text-1);
  font-size: 13px;
  font-family: var(--vp-font-family-mono);
  resize: vertical;
  width: 100%;
  box-sizing: border-box;
}
.field select {
  font-family: inherit;
  resize: none;
}
.field.checkbox label {
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 8px;
}
.options {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.upgrade-btn {
  align-self: flex-start;
  padding: 8px 20px;
  background: var(--vp-c-brand-1);
  color: #fff;
  border: none;
  border-radius: 6px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
}
.upgrade-btn:hover {
  background: var(--vp-c-brand-2);
}
.error {
  color: var(--vp-c-danger-1);
  font-size: 13px;
}
.output-block {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.output-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.output-header label {
  font-size: 14px;
  font-weight: 500;
  color: var(--vp-c-text-1);
}
.copy-btn {
  padding: 4px 12px;
  background: var(--vp-c-bg-soft);
  border: 1px solid var(--vp-c-divider);
  border-radius: 4px;
  font-size: 12px;
  cursor: pointer;
  color: var(--vp-c-text-1);
}
.copy-btn:hover {
  background: var(--vp-c-bg-mute);
}
</style>
