# Traefik Manager – UI Examples

Images follow your site theme (light / dark toggle in the top-right corner).

<style>
.ui-cards {
  display: grid;
  grid-template-columns: 1fr;
  gap: 32px;
  margin-top: 32px;
}
.ui-card {
  border: 1px solid var(--vp-c-divider);
  border-radius: 16px;
  overflow: hidden;
  background: var(--vp-c-bg-soft);
}
.ui-card-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 16px 20px;
  border-bottom: 1px solid var(--vp-c-divider);
  font-size: 17px;
  font-weight: 700;
  color: var(--vp-c-text-1);
  background: var(--vp-c-bg-alt);
}
.ui-card-body {
  padding: 0;
}
</style>

<div class="ui-cards">

  <div class="ui-card">
    <div class="ui-card-header">🖥️ Desktop</div>
    <div class="ui-card-body">
      <DesktopScreenshots />
    </div>
  </div>

  <div class="ui-card">
    <div class="ui-card-header">📱 Mobile</div>
    <div class="ui-card-body">
      <MobileScreenshots />
    </div>
  </div>

</div>
