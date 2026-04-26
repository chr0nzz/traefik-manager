<script setup>
import { withBase } from 'vitepress'
</script>

<template>
  <div class="showcase-wrap">
    <div class="showcase-inner">
      <div class="browser">
        <div class="browser-bar">
          <div class="browser-dots">
            <span /><span /><span />
          </div>
          <div class="browser-url">manager.example.com</div>
        </div>
        <div class="browser-content">
          <img :src="withBase('/images/light-routes.png')" alt="Traefik Manager routes tab" class="browser-img shot-light" />
          <img :src="withBase('/images/dark-routes.png')" alt="Traefik Manager routes tab" class="browser-img shot-dark" />
        </div>

        <div class="phone">
          <div class="phone-notch" />
          <div class="phone-screen">
            <img :src="withBase('/images/light-mobile-dashboard-2.png')" alt="Traefik Manager mobile app" class="phone-img shot-light" />
            <img :src="withBase('/images/dark-mobile-dashboard-2.png')" alt="Traefik Manager mobile app" class="phone-img shot-dark" />
          </div>
          <div class="phone-home" />
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.showcase-wrap {
  padding: 32px 24px 120px;
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


.browser-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 0 14px;
  height: 36px;
  border-bottom: 1px solid #d0d7de;
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
  bottom: -80px;
  right: -28px;
  width: 160px;
  height: 320px;
  border-radius: 26px;
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


.phone-notch {
  width: 56px;
  height: 10px;
  background: #d0d7de;
  border-radius: 4px;
  flex-shrink: 0;
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
  width: 52px;
  height: 5px;
  background: #d0d7de;
  border-radius: 3px;
  flex-shrink: 0;
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
