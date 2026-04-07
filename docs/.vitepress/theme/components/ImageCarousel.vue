<script setup lang="ts">
import { ref, computed } from 'vue'

interface Slide {
  light: string
  dark:  string
  label: string
}

const props = defineProps<{
  slides:   Slide[]
  portrait?: boolean
}>()

const idx   = ref(0)
const slide = computed(() => props.slides[idx.value])
const total = computed(() => props.slides.length)

const prev = () => { idx.value = (idx.value - 1 + total.value) % total.value }
const next = () => { idx.value = (idx.value + 1) % total.value }
const go   = (n: number) => { idx.value = n }
</script>

<template>
  <div class="carousel" :class="{ 'carousel--portrait': portrait }">
    <div class="carousel-img-wrap">
      <img class="carousel-img light-img" :src="slide.light" :alt="slide.label" />
      <img class="carousel-img dark-img"  :src="slide.dark"  :alt="slide.label" />
    </div>

    <div class="carousel-footer">
      <div class="carousel-label">{{ slide.label }}</div>
      <div class="carousel-controls">
        <button class="carousel-btn" @click="prev" aria-label="Previous">‹</button>
        <span class="carousel-counter">{{ idx + 1 }} / {{ total }}</span>
        <button class="carousel-btn" @click="next" aria-label="Next">›</button>
      </div>
      <div v-if="total <= 12" class="carousel-dots">
        <button
          v-for="(_, n) in slides"
          :key="n"
          class="carousel-dot"
          :class="{ active: n === idx }"
          @click="go(n)"
          :aria-label="`Slide ${n + 1}`"
        />
      </div>
    </div>
  </div>
</template>

<style scoped>
.carousel {
  border: 1px solid var(--vp-c-divider);
  border-radius: 12px;
  overflow: hidden;
  background: var(--vp-c-bg-soft);
}

.carousel-img-wrap {
  width: 100%;
  line-height: 0;
}

.carousel-img {
  width: 100%;
  height: auto;
  display: block;
}

.carousel--portrait .carousel-img-wrap {
  display: flex;
  justify-content: center;
  background: var(--vp-c-bg-alt);
  padding: 16px 0;
}

.carousel--portrait .carousel-img {
  width: auto;
  max-height: 520px;
  max-width: 100%;
}

.dark-img  { display: none; }
.dark .dark-img  { display: block; }
.dark .light-img { display: none; }

.carousel-footer {
  padding: 12px 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.carousel-label {
  font-size: 13px;
  color: var(--vp-c-text-2);
  text-align: center;
}

.carousel-controls {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
}

.carousel-btn {
  width: 32px;
  height: 32px;
  border-radius: 6px;
  border: 1px solid var(--vp-c-divider);
  background: var(--vp-c-bg);
  color: var(--vp-c-text-1);
  font-size: 20px;
  line-height: 1;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.15s;
}
.carousel-btn:hover {
  background: var(--vp-c-default-soft);
}

.carousel-counter {
  font-size: 13px;
  color: var(--vp-c-text-2);
  min-width: 48px;
  text-align: center;
}

.carousel-dots {
  display: flex;
  justify-content: center;
  gap: 6px;
  flex-wrap: wrap;
}

.carousel-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  border: none;
  background: var(--vp-c-divider);
  cursor: pointer;
  padding: 0;
  transition: background 0.15s, transform 0.15s;
}
.carousel-dot.active {
  background: var(--vp-c-brand-1);
  transform: scale(1.3);
}
</style>
