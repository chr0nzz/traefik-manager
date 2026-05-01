import { h, onMounted, watch, nextTick } from 'vue'
import { useRoute } from 'vitepress'
import DefaultTheme from 'vitepress/theme'
import { enhanceAppWithTabs } from 'vitepress-plugin-tabs/client'
import mediumZoom from 'medium-zoom'
import GitHubStars from './components/GitHubStars.vue'
import MobileRelease from './components/MobileRelease.vue'
import UnraidCAStatus from './components/UnraidCAStatus.vue'
import ImageCarousel from './components/ImageCarousel.vue'
import DesktopScreenshots from './components/DesktopScreenshots.vue'
import MobileScreenshots from './components/MobileScreenshots.vue'
import ComposeUpgrader from './components/ComposeUpgrader.vue'
import ShowcaseMockup from './components/ShowcaseMockup.vue'
import InstallSection from './components/InstallSection.vue'
import KoFiButton from './components/KoFiButton.vue'
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
      'nav-bar-content-after': () => [h(KoFiButton), h(GitHubStars)],
      'home-features-before': () => h(ShowcaseMockup),
      'home-features-after': () => h(InstallSection),
    })
  },
  enhanceApp({ app }: { app: any }) {
    enhanceAppWithTabs(app)
    app.component('MobileRelease', MobileRelease)
    app.component('UnraidCAStatus', UnraidCAStatus)
    app.component('ImageCarousel', ImageCarousel)
    app.component('DesktopScreenshots', DesktopScreenshots)
    app.component('MobileScreenshots', MobileScreenshots)
    app.component('ComposeUpgrader', ComposeUpgrader)
    app.component('ShowcaseMockup', ShowcaseMockup)
    app.component('InstallSection', InstallSection)
  },
}
