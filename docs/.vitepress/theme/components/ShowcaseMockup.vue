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
          <img :src="withBase('/images/light-routes-cards.png')" alt="Traefik Manager routes tab" class="browser-img shot-light" />
          <img :src="withBase('/images/dark-routes-cards.png')" alt="Traefik Manager routes tab" class="browser-img shot-dark" />
        </div>

        <div class="phone">
          <div class="phone-screen">
            <img :src="withBase('/images/light-mobile-dashboard.png')" alt="Traefik Manager mobile app" class="phone-img shot-light" />
            <img :src="withBase('/images/dark-mobile-dashboard.png')" alt="Traefik Manager mobile app" class="phone-img shot-dark" />
            <div class="phone-camera" />
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
  border-radius: 36px;
  background: #e8eaed;
  border: 1px solid #d0d7de;
  box-shadow: 0 16px 48px rgba(0, 0, 0, 0.22);
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 5px 5px 10px;
  gap: 0;
  z-index: 10;
}

.phone-screen {
  flex: 1;
  width: 100%;
  border-radius: 32px;
  overflow: hidden;
  position: relative;
}

.phone-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  object-position: top;
  display: block;
}

.phone-camera {
  position: absolute;
  top: 10px;
  left: 50%;
  transform: translateX(-50%);
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: rgba(0, 0, 0, 0.75);
  z-index: 2;
}

.phone-home {
  width: 44px;
  height: 4px;
  background: #b0b8c1;
  border-radius: 2px;
  margin-top: 6px;
  flex-shrink: 0;
}


@media (max-width: 640px) {
  .browser-img {
    object-position: top center;
  }
  .phone {
    width: 80px;
    height: 160px;
    right: -8px;
    bottom: -40px;
    border-radius: 20px;
    padding: 3px 3px 7px;
  }
  .phone-screen {
    border-radius: 18px;
  }
  .phone-camera {
    width: 6px;
    height: 6px;
    top: 7px;
  }
  .phone-home {
    width: 28px;
    height: 3px;
    margin-top: 4px;
  }
}
</style>
