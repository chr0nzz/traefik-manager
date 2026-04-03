import { h, onMounted, watch, nextTick } from 'vue'
import { useRoute } from 'vitepress'
import DefaultTheme from 'vitepress/theme'
import { enhanceAppWithTabs } from 'vitepress-plugin-tabs/client'
import mediumZoom from 'medium-zoom'
import GitHubStars from './components/GitHubStars.vue'
import MobileRelease from './components/MobileRelease.vue'
import './style.css'

export default {
  extends: DefaultTheme,
  Layout() {
    const route = useRoute()

    const initZoom = () => {
      mediumZoom('.ui-img-light, .ui-img-dark', {
        background: 'rgba(0,0,0,0.85)',
      })
    }

    onMounted(() => initZoom())
    watch(() => route.path, () => nextTick(() => initZoom()))

    return h(DefaultTheme.Layout, null, {
      'nav-bar-content-after': () => h(GitHubStars),
    })
  },
  enhanceApp({ app }: { app: any }) {
    enhanceAppWithTabs(app)
    app.component('MobileRelease', MobileRelease)
  },
}
