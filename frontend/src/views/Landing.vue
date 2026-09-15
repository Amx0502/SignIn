<template>
  <div class="landing-page">
    <nav class="nav-bar">
      <div class="nav-inner">
        <div class="nav-logo">
          <span class="logo-icon">班</span>
          <span class="logo-text">班级魔方</span>
        </div>
        <div class="nav-links">
          <a href="#features">功能</a>
          <a href="#guide">使用说明</a>
          <a href="#pricing">购买</a>
          <button class="btn-outline" @click="goLogin">登录</button>
          <button class="btn-primary" @click="goBuy">立即购买</button>
        </div>
      </div>
    </nav>

    <section class="hero">
      <div class="hero-inner">
        <h1>班级魔方</h1>
        <p class="hero-tagline">全自动签到 · 精准定位 · 多账号管理</p>
        <p class="hero-desc">一键配置，自动完成班级魔方签到。支持微信内置浏览器定位，无需手动操作。</p>
        <div class="hero-actions">
          <button class="btn-primary btn-lg" @click="goBuy">立即购买 →</button>
          <button class="btn-outline btn-lg" @click="goLogin">登录使用</button>
        </div>
      </div>
    </section>

    <section id="features" class="features">
      <div class="section-inner">
        <h2 class="section-title">核心功能</h2>
        <div class="feature-grid">
          <div class="feature-card">
            <div class="feature-icon auto">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 11l3 3L22 4M21 12v7a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2h11"/></svg>
            </div>
            <h3>自动签到</h3>
            <p>配置好时间后，系统每天自动执行签到，无需手动操作。</p>
          </div>
          <div class="feature-card">
            <div class="feature-icon location">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0118 0z"/><circle cx="12" cy="10" r="3"/></svg>
            </div>
            <h3>精准定位</h3>
            <p>支持浏览器原生定位和微信内置浏览器定位，自动坐标纠偏，签到位置准确。</p>
          </div>
          <div class="feature-card">
            <div class="feature-icon multi">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 00-3-3.87M16 3.13a4 4 0 010 7.75"/></svg>
            </div>
            <h3>多账号管理</h3>
            <p>支持同时管理多个班级魔方账号，批量签到，效率翻倍。</p>
          </div>
        </div>
      </div>
    </section>

    <section id="guide" class="guide">
      <div class="section-inner">
        <h2 class="section-title">使用说明</h2>
        <div class="steps">
          <div class="step">
            <div class="step-num">1</div>
            <div class="step-content">
              <h3>购买会员卡</h3>
              <p>选择次卡或月卡，完成购买后获取登录账号。</p>
            </div>
          </div>
          <div class="step">
            <div class="step-num">2</div>
            <div class="step-content">
              <h3>登录系统</h3>
              <p>使用分配的账号密码登录，进入班级魔方管理面板。</p>
            </div>
          </div>
          <div class="step">
            <div class="step-num">3</div>
            <div class="step-content">
              <h3>添加账号</h3>
              <p>扫码登录班级魔方账号，同步签到课程和项目。</p>
            </div>
          </div>
          <div class="step">
            <div class="step-num">4</div>
            <div class="step-content">
              <h3>配置任务</h3>
              <p>设置签到时间、位置信息，保存后系统将自动执行签到。</p>
            </div>
          </div>
        </div>
      </div>
    </section>

    <section id="pricing" class="pricing">
      <div class="section-inner">
        <h2 class="section-title">会员卡购买</h2>
        <div class="pricing-grid">
          <div class="pricing-card">
            <div class="pricing-header">
              <h3>次卡</h3>
              <p class="pricing-desc">签到一次后自动过期</p>
            </div>
            <div class="pricing-features">
              <div class="feature-item"><span class="check">✓</span> 单次签到有效</div>
              <div class="feature-item"><span class="check">✓</span> 自动过期失效</div>
              <div class="feature-item"><span class="check">✓</span> 随机用户名密码</div>
            </div>
            <button class="btn-primary btn-block" @click="goBuy">购买次卡</button>
          </div>
          <div class="pricing-card pricing-highlight">
            <div class="pricing-badge">推荐</div>
            <div class="pricing-header">
              <h3>月卡</h3>
              <p class="pricing-desc">激活后 30 天有效</p>
            </div>
            <div class="pricing-features">
              <div class="feature-item"><span class="check">✓</span> 首次登录激活</div>
              <div class="feature-item"><span class="check">✓</span> 30 天自动签到</div>
              <div class="feature-item"><span class="check">✓</span> 到期自动过期</div>
              <div class="feature-item"><span class="check">✓</span> 多课程批量签到</div>
            </div>
            <button class="btn-primary btn-block" @click="goBuy">购买月卡</button>
          </div>
        </div>
      </div>
    </section>

    <footer class="footer">
      <div class="footer-inner">
        <button class="btn-outline" @click="goLogin">前往登录 →</button>
        <p class="footer-text">班级魔方自动签到系统</p>
      </div>
    </footer>
  </div>
</template>

<script setup>
const BUY_URL = "https://m.tb.cn/h.8sGQxfh?tk=Dz6vT8OEx7h";
const LOGIN_PATH = "/login";

function goBuy() {
  window.open(BUY_URL, "_blank");
}
function goLogin() {
  window.location.href = LOGIN_PATH;
}
</script>

<style scoped>
.landing-page {
  --c-primary: #4f6bff;
  --c-primary-light: #eef1ff;
  --c-accent: #ff7a45;
  --c-bg: #f8faff;
  --c-text: #1e2a44;
  --c-muted: #64748b;
  --c-border: #dce3f0;
  --c-surface: #ffffff;
  --radius-card: 12px;
  --radius-full: 999px;
  font-family: -apple-system, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
  color: var(--c-text);
  background: var(--c-bg);
  line-height: 1.6;
}

.nav-bar {
  position: sticky;
  top: 0;
  z-index: 100;
  background: rgba(255, 255, 255, 0.92);
  backdrop-filter: blur(12px);
  border-bottom: 1px solid var(--c-border);
}
.nav-inner {
  max-width: 1080px;
  margin: 0 auto;
  padding: 0 24px;
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.nav-logo {
  display: flex;
  align-items: center;
  gap: 10px;
}
.logo-icon {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  background: var(--c-primary);
  color: #fff;
  font-size: 16px;
  font-weight: 700;
  display: grid;
  place-items: center;
}
.logo-text {
  font-size: 18px;
  font-weight: 700;
}
.nav-links {
  display: flex;
  align-items: center;
  gap: 20px;
}
.nav-links a {
  font-size: 14px;
  color: var(--c-text);
  text-decoration: none;
  font-weight: 500;
  transition: color 0.15s;
}
.nav-links a:hover {
  color: var(--c-primary);
}

.btn-primary, .btn-outline {
  font-size: 14px;
  font-weight: 600;
  border-radius: var(--radius-full);
  cursor: pointer;
  border: none;
  transition: all 0.15s;
  font-family: inherit;
}
.btn-primary {
  background: var(--c-primary);
  color: #fff;
  padding: 8px 20px;
}
.btn-primary:hover {
  background: #3d56e0;
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(79, 107, 255, 0.3);
}
.btn-outline {
  background: transparent;
  color: var(--c-primary);
  border: 1.5px solid var(--c-primary);
  padding: 6px 18px;
}
.btn-outline:hover {
  background: var(--c-primary-light);
}
.btn-lg {
  padding: 12px 32px;
  font-size: 15px;
}
.btn-block {
  width: 100%;
  padding: 12px;
  font-size: 15px;
}

.hero {
  background: linear-gradient(135deg, var(--c-primary-light), var(--c-bg));
  padding: 80px 24px 60px;
  text-align: center;
}
.hero-inner {
  max-width: 720px;
  margin: 0 auto;
}
.hero h1 {
  font-size: 42px;
  font-weight: 800;
  margin: 0 0 12px;
  letter-spacing: -0.02em;
}
.hero-tagline {
  font-size: 20px;
  color: var(--c-primary);
  font-weight: 600;
  margin: 0 0 8px;
}
.hero-desc {
  font-size: 15px;
  color: var(--c-muted);
  margin: 0 0 32px;
}
.hero-actions {
  display: flex;
  gap: 14px;
  justify-content: center;
  flex-wrap: wrap;
}
.hero-actions .btn-primary {
  background: var(--c-accent);
}
.hero-actions .btn-primary:hover {
  background: #e8693a;
  box-shadow: 0 4px 12px rgba(255, 122, 69, 0.3);
}

.section-inner {
  max-width: 1080px;
  margin: 0 auto;
  padding: 64px 24px;
}
.section-title {
  font-size: 28px;
  font-weight: 700;
  text-align: center;
  margin: 0 0 40px;
}

.feature-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 20px;
}
.feature-card {
  background: var(--c-surface);
  border: 1px solid var(--c-border);
  border-radius: var(--radius-card);
  padding: 28px 20px;
  text-align: center;
  transition: box-shadow 0.2s, transform 0.2s;
}
.feature-card:hover {
  box-shadow: 0 8px 24px rgba(79, 107, 255, 0.08);
  transform: translateY(-2px);
}
.feature-icon {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  display: grid;
  place-items: center;
  margin: 0 auto 16px;
  color: var(--c-primary);
  background: var(--c-primary-light);
}
.feature-icon.location { color: #ef4444; background: #fef2f2; }
.feature-icon.multi { color: #8b5cf6; background: #f5f3ff; }
.feature-icon.notify { color: #f59e0b; background: #fffbeb; }
.feature-card h3 {
  font-size: 16px;
  font-weight: 600;
  margin: 0 0 8px;
}
.feature-card p {
  font-size: 13px;
  color: var(--c-muted);
  margin: 0;
}

.steps {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 20px;
}
.step {
  display: grid;
  gap: 16px;
  text-align: center;
}
.step-num {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: var(--c-primary);
  color: #fff;
  font-size: 18px;
  font-weight: 700;
  display: grid;
  place-items: center;
  margin: 0 auto;
}
.step-content h3 {
  font-size: 15px;
  font-weight: 600;
  margin: 0 0 6px;
}
.step-content p {
  font-size: 13px;
  color: var(--c-muted);
  margin: 0;
}

.pricing {
  background: linear-gradient(180deg, var(--c-bg), var(--c-primary-light));
}
.pricing-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 24px;
  max-width: 640px;
  margin: 0 auto;
}
.pricing-card {
  background: var(--c-surface);
  border: 1px solid var(--c-border);
  border-radius: 16px;
  padding: 32px 28px;
  display: grid;
  gap: 24px;
  position: relative;
}
.pricing-highlight {
  border: 2px solid var(--c-primary);
  box-shadow: 0 12px 32px rgba(79, 107, 255, 0.12);
}
.pricing-badge {
  position: absolute;
  top: -12px;
  left: 50%;
  transform: translateX(-50%);
  background: var(--c-accent);
  color: #fff;
  font-size: 12px;
  font-weight: 600;
  padding: 4px 16px;
  border-radius: var(--radius-full);
}
.pricing-header h3 {
  font-size: 22px;
  font-weight: 700;
  margin: 0 0 4px;
}
.pricing-desc {
  font-size: 13px;
  color: var(--c-muted);
  margin: 0;
}
.pricing-features {
  display: grid;
  gap: 12px;
}
.feature-item {
  font-size: 14px;
  display: flex;
  align-items: center;
  gap: 8px;
}
.check {
  color: var(--c-primary);
  font-weight: 700;
}
.pricing-highlight .btn-primary {
  background: var(--c-accent);
}
.pricing-highlight .btn-primary:hover {
  background: #e8693a;
  box-shadow: 0 4px 12px rgba(255, 122, 69, 0.3);
}

.footer {
  background: var(--c-text);
  padding: 40px 24px;
}
.footer-inner {
  max-width: 1080px;
  margin: 0 auto;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.footer .btn-outline {
  color: #fff;
  border-color: rgba(255, 255, 255, 0.3);
}
.footer .btn-outline:hover {
  background: rgba(255, 255, 255, 0.1);
}
.footer-text {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.5);
  margin: 0;
}

/* 平板端 768px - 1024px */
@media (max-width: 1024px) {
  .nav-inner, .section-inner { max-width: 100%; }
  .hero { padding: 56px 20px 44px; }
  .hero h1 { font-size: 34px; }
  .hero-tagline { font-size: 17px; }
  .hero-desc { font-size: 14px; margin-bottom: 28px; }
  .section-inner { padding: 48px 20px; }
  .section-title { font-size: 24px; margin-bottom: 32px; }
  .feature-grid { grid-template-columns: repeat(3, 1fr); gap: 16px; }
  .feature-card { padding: 22px 16px; }
  .feature-card h3 { font-size: 15px; }
  .feature-card p { font-size: 12px; }
  .steps { grid-template-columns: repeat(2, 1fr); gap: 24px 16px; }
  .pricing-grid { max-width: 560px; gap: 20px; }
  .pricing-card { padding: 24px 20px; }
}

/* 手机端 < 768px */
@media (max-width: 767px) {
  .nav-inner { padding: 0 16px; height: 54px; }
  .nav-links { gap: 8px; }
  .nav-links a { display: none !important; }
  .nav-links .btn-outline { display: inline-flex !important; }
  .logo-text { font-size: 16px; }
  .logo-icon { width: 28px; height: 28px; font-size: 14px; }

  .hero { padding: 40px 16px 36px; }
  .hero h1 { font-size: 26px; }
  .hero-tagline { font-size: 15px; }
  .hero-desc { font-size: 13px; margin-bottom: 24px; }
  .hero-actions { gap: 10px; }
  .btn-lg { padding: 10px 24px; font-size: 14px; }

  .section-inner { padding: 40px 16px; }
  .section-title { font-size: 20px; margin-bottom: 28px; }

  .feature-grid { grid-template-columns: 1fr; gap: 12px; }
  .feature-card { padding: 20px 16px; display: flex; align-items: flex-start; gap: 14px; text-align: left; }
  .feature-icon { width: 40px; height: 40px; margin: 0; flex-shrink: 0; }
  .feature-card h3 { font-size: 14px; margin-bottom: 4px; }
  .feature-card p { font-size: 12px; }

  .steps { grid-template-columns: 1fr; gap: 20px; }
  .step { display: flex; align-items: flex-start; gap: 14px; text-align: left; }
  .step-num { width: 32px; height: 32px; font-size: 15px; margin: 0; flex-shrink: 0; }
  .step-content h3 { font-size: 14px; }
  .step-content p { font-size: 12px; }

  .pricing-grid { grid-template-columns: 1fr; max-width: 100%; gap: 16px; }
  .pricing-card { padding: 24px 20px; }
  .pricing-header h3 { font-size: 18px; }

  .footer { padding: 32px 16px; }
  .footer-inner { flex-direction: column; gap: 14px; }
  .footer-text { font-size: 12px; }
}

/* 小屏手机 < 400px */
@media (max-width: 399px) {
  .hero h1 { font-size: 22px; }
  .hero-tagline { font-size: 13px; }
  .btn-lg { padding: 10px 18px; font-size: 13px; }
  .section-title { font-size: 18px; }
}
</style>
