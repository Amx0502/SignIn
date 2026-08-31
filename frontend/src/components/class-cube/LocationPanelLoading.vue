<template>
  <div class="location-panel-loading" role="status" aria-live="polite">
    <div class="loading-fields"><span /><span /></div>
    <div class="loading-map"><i /><strong>正在加载地图组件…</strong></div>
  </div>
</template>

<style scoped>
.location-panel-loading{display:grid;gap:12px;width:100%;min-height:430px;padding:12px;border:1px solid #dbeafe;border-radius:15px;background:linear-gradient(145deg,#f8fbff,#fff);box-sizing:border-box}.loading-fields{display:grid;gap:9px}.loading-fields span{height:34px;border-radius:10px;background:linear-gradient(90deg,#eef4fb 20%,#dbeafe 45%,#eef4fb 70%);background-size:220% 100%;animation:loading-shimmer 1.2s linear infinite}.loading-map{display:grid;min-height:330px;place-content:center;justify-items:center;gap:12px;border:1px solid #bfdbfe;border-radius:14px;background:#eaf3ff;color:#1e40af}.loading-map i{width:28px;height:28px;border:3px solid #bfdbfe;border-top-color:#2563eb;border-radius:50%;animation:loading-spin .8s linear infinite}.loading-map strong{font-size:13px}@keyframes loading-spin{to{transform:rotate(360deg)}}@keyframes loading-shimmer{to{background-position:-220% 0}}@media(prefers-reduced-motion:reduce){.loading-fields span,.loading-map i{animation:none}}
</style>
