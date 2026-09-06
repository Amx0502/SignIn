<template>
  <div class="miaoying-page">
    <section class="miaoying-hero">
      <img src="../img/miaoying.png" alt="秒应" />
      <div>
        <p>秒应</p>
        <h1>秒应服务中心</h1>
        <span>秒应功能入口已接入，后续服务将在此集中展示。</span>
      </div>
    </section>

    <el-card class="miaoying-content" shadow="never">
      <el-empty description="暂无可用功能" :image-size="86">
        <p>当前已完成菜单、权限和页面入口配置。</p>
      </el-empty>
    </el-card>
  </div>
</template>

<style scoped>
.miaoying-page { display:grid;gap:18px;min-width:0 }
.miaoying-hero { display:flex;align-items:center;gap:22px;padding:25px 28px;border:1px solid #dbeafe;border-radius:24px;background:linear-gradient(125deg,#eff8ff,#f0fdf4);box-shadow:0 18px 42px #0f172a0d }
.miaoying-hero img { width:78px;height:78px;flex:none;padding:7px;border-radius:22px;background:#fff;box-shadow:0 12px 28px #2f9ed829 }
.miaoying-hero p { margin:0;color:#168ac5;font-size:12px;font-weight:800;letter-spacing:.18em }
.miaoying-hero h1 { margin:7px 0 5px;color:#0f172a;font-size:27px }
.miaoying-hero span { color:#64748b }
.miaoying-content { min-height:340px;border:1px solid #dbeafe;border-radius:22px;background:#ffffffdb }
.miaoying-content :deep(.el-card__body) { display:grid;min-height:300px;place-items:center }
.miaoying-content p { margin:7px 0 0;color:#94a3b8;font-size:12px }
@media(max-width:640px){.miaoying-hero{align-items:flex-start;padding:20px;gap:15px}.miaoying-hero img{width:60px;height:60px}.miaoying-hero h1{font-size:22px}.miaoying-hero span{font-size:13px}}
</style>
