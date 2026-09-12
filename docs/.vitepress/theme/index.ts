import { h, onMounted, watch, nextTick } from 'vue'
import { useRoute } from 'vitepress'
import DefaultTheme from 'vitepress/theme'
import { enhanceAppWithTabs } from 'vitepress-plugin-tabs/client'
import mediumZoom from 'medium-zoom'
import GitHubStars from './components/GitHubStars.vue'
import MobileRelease from './components/MobileRelease.vue'
import ComposeUpgrader from './components/ComposeUpgrader.vue'
import ShowcaseMockup from './components/ShowcaseMockup.vue'
import HomeHero from './components/HomeHero.vue'
import HomeShowcase from './components/HomeShowcase.vue'
import HomeCta from './components/HomeCta.vue'
import KoFiButton from './components/KoFiButton.vue'
import './style.css'

export default {
  extends: DefaultTheme,
  setup() {
    const route = useRoute()
    let zoom: ReturnType<typeof mediumZoom> | null = null

    const initZoom = () => {
      if (zoom) zoom.detach()
      zoom = mediumZoom('.screenshot', {
        margin: 32,
        background: 'rgba(0,0,0,0.85)',
      })
    }

    onMounted(() => nextTick(() => initZoom()))
    watch(() => route.path, () => nextTick(() => initZoom()))
  },
  Layout() {
    return h(DefaultTheme.Layout, null, {
      'nav-bar-content-after': () => [h(KoFiButton), h(GitHubStars)],
      'home-hero-before': () => h(HomeHero),
      'home-features-before': () => [h(ShowcaseMockup), h(HomeCta)],
      'home-features-after': () => h(HomeShowcase),
    })
  },
  enhanceApp({ app }: { app: any }) {
    enhanceAppWithTabs(app)
    app.component('MobileRelease', MobileRelease)
    app.component('ComposeUpgrader', ComposeUpgrader)
    app.component('ShowcaseMockup', ShowcaseMockup)
  },
}
