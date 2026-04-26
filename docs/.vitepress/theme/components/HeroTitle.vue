<template>
  <div class="hero-title">
    <img src="/images/icon.png" width="44" height="44" alt="Traefik Manager" />
    <span class="name clip">Traefik Manager</span>
  </div>
</template>

<style scoped>
.hero-title {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 14px;
  margin-bottom: 12px;
}

.name {
  font-size: clamp(2rem, 5vw, 3.5rem);
  font-weight: 700;
  letter-spacing: -0.02em;
  line-height: 1;
  background: linear-gradient(120deg, var(--vp-c-brand-1), var(--vp-c-brand-2));
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}
</style>
