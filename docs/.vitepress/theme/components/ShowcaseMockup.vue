<script setup>
import { useData, withBase } from 'vitepress'
const { isDark } = useData()
</script>

<template>
  <div class="showcase-wrap">
    <div class="showcase-inner">
      <div class="browser" :class="{ dark: isDark }">
        <div class="browser-bar">
          <div class="browser-dots">
            <span /><span /><span />
          </div>
          <div class="browser-url">manager.example.com</div>
        </div>
        <div class="browser-content">
          <img
            :src="withBase(isDark ? '/images/dark-routes.png' : '/images/light-routes.png')"
            alt="Traefik Manager routes tab"
            class="browser-img"
          />
        </div>

        <div class="phone" :class="{ dark: isDark }">
          <div class="phone-notch" />
          <div class="phone-screen">
            <img
              :src="withBase(isDark ? '/images/dark-mobile-dashboard-2.png' : '/images/light-mobile-dashboard-2.png')"
              alt="Traefik Manager mobile app"
              class="phone-img"
            />
          </div>
          <div class="phone-home" />
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.showcase-wrap {
  padding: 32px 24px 80px;
  width: 100%;
}

.showcase-inner {
  max-width: 880px;
  margin: 0 auto;
}

.browser {
  position: relative;
  border-radius: 10px;
  overflow: visible;
  box-shadow: 0 24px 64px rgba(0, 0, 0, 0.18);
  background: #e8eaed;
  border: 1px solid #d0d7de;
}

.browser.dark {
  background: #1c2128;
  border-color: #30363d;
}

.browser-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 0 14px;
  height: 36px;
  border-bottom: 1px solid #d0d7de;
}

.browser.dark .browser-bar {
  border-bottom-color: #30363d;
}

.browser-dots {
  display: flex;
  gap: 6px;
  flex-shrink: 0;
}

.browser-dots span {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: #d0d7de;
}

.browser.dark .browser-dots span {
  background: #30363d;
}

.browser-dots span:nth-child(1) { background: #ff5f57; }
.browser-dots span:nth-child(2) { background: #febc2e; }
.browser-dots span:nth-child(3) { background: #28c840; }

.browser-url {
  flex: 1;
  background: #ffffff;
  border: 1px solid #d0d7de;
  border-radius: 6px;
  height: 22px;
  line-height: 22px;
  text-align: center;
  font-size: 11px;
  color: #636c76;
  font-family: system-ui, sans-serif;
  max-width: 280px;
  margin: 0 auto;
  padding: 0 8px;
}

.browser.dark .browser-url {
  background: #0d1117;
  border-color: #30363d;
  color: #8b949e;
}

.browser-content {
  height: 400px;
  overflow: hidden;
  border-radius: 0 0 10px 10px;
}

.browser-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  object-position: top left;
  display: block;
}

.phone {
  position: absolute;
  bottom: -60px;
  right: -16px;
  width: 110px;
  height: 220px;
  border-radius: 18px;
  background: #e8eaed;
  border: 1px solid #d0d7de;
  box-shadow: 0 16px 48px rgba(0, 0, 0, 0.22);
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 10px 6px 12px;
  gap: 6px;
  z-index: 10;
}

.phone.dark {
  background: #1c2128;
  border-color: #30363d;
}

.phone-notch {
  width: 40px;
  height: 8px;
  background: #d0d7de;
  border-radius: 4px;
  flex-shrink: 0;
}

.phone.dark .phone-notch {
  background: #30363d;
}

.phone-screen {
  flex: 1;
  width: 100%;
  border-radius: 8px;
  overflow: hidden;
}

.phone-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  object-position: top;
  display: block;
}

.phone-home {
  width: 36px;
  height: 5px;
  background: #d0d7de;
  border-radius: 3px;
  flex-shrink: 0;
}

.phone.dark .phone-home {
  background: #30363d;
}

@media (max-width: 640px) {
  .phone {
    width: 80px;
    height: 160px;
    right: -8px;
    bottom: -40px;
    border-radius: 14px;
  }
}
</style>
