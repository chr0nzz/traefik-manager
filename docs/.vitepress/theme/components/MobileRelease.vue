<script setup lang="ts">
import { ref, onMounted } from 'vue'

const version = ref<string | null>(null)
const apkUrl  = ref<string | null>(null)
const pageUrl = ref('https://github.com/chr0nzz/traefik-manager-mobile/releases')

onMounted(async () => {
  try {
    const res  = await fetch('https://api.github.com/repos/chr0nzz/traefik-manager-mobile/releases/latest')
    const data = await res.json()
    version.value = data.tag_name
    pageUrl.value  = data.html_url
    const apk = data.assets?.find((a: any) => a.name.endsWith('.apk'))
    if (apk) apkUrl.value = apk.browser_download_url
  } catch {}
})
</script>

<template>
  <div class="mobile-release">
    <a
      v-if="apkUrl"
      :href="apkUrl"
      class="vp-btn vp-btn--primary"
    ><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/png/android.png" style="height:18px;width:18px;vertical-align:middle;display:inline-block;margin-right:6px">Download APK {{ version }}</a>
    <a
      v-else
      href="https://github.com/chr0nzz/traefik-manager-mobile/releases"
      class="vp-btn vp-btn--primary"
    ><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/png/android.png" style="height:18px;width:18px;vertical-align:middle;display:inline-block;margin-right:6px">Download APK</a>
    <a
      :href="pageUrl"
      target="_blank"
      rel="noopener noreferrer"
      class="vp-btn"
    >Release page</a>
  </div>
</template>
