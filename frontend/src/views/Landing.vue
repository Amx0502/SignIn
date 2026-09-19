<template>
  <div class="landing-page">
    <nav class="nav-bar">
      <div class="nav-inner">
        <a class="nav-logo" href="#top">
          <img :src="logoImage" alt="轻签系统图标" class="system-logo" />
          <span>轻签</span>
        </a>
        <div class="nav-links">
          <a class="btn-guide" :href="GUIDE_URL" target="_blank" rel="noopener noreferrer">使用说明指南</a>
          <button class="btn-outline" @click="goLogin">登录</button>
          <button class="btn-primary" @click="goBuy">立即购买</button>
        </div>
      </div>
    </nav>

    <main>
      <section id="top" class="hero">
        <div class="hero-inner">
          <div class="hero-mark"><img :src="logoImage" alt="轻签" /></div>
          <p class="eyebrow">多平台自动化签到管理中台</p>
          <h1>轻签</h1>
          <h2>一个后台，管理多种常用签到工具</h2>
          <p class="hero-desc">统一管理账号、自动任务、定位搜索和运行记录。目前已支持小小签到、班级魔方、秒应，更多常用工具持续接入中。</p>
          <div class="hero-actions">
            <button class="btn-primary btn-lg" @click="goBuy">购买次卡或月卡</button>
            <button class="btn-outline btn-lg" @click="goLogin">登录使用</button>
            <a class="btn-outline btn-lg hero-guide" :href="GUIDE_URL" target="_blank" rel="noopener noreferrer">使用说明指南</a>
          </div>
          <div class="hero-points"><span>多平台统一管理</span><span>自动任务稳定运行</span><span>运行记录长期保留</span></div>
        </div>
      </section>

      <section id="platforms" class="section platforms-section">
        <div class="section-inner">
          <div class="section-heading">
            <p class="eyebrow">平台能力</p>
            <h2>已有工具与持续接入</h2>
            <p>根据账号所属平台统一分配功能范围，普通用户只看到被授权的工具入口。</p>
          </div>
          <div class="platform-grid">
            <article v-for="platform in platforms" :key="platform.name" class="platform-card">
              <div class="platform-icon"><img :src="platform.image" :alt="`${platform.name}图标`" /></div>
              <div>
                <div class="platform-title"><h3>{{ platform.name }}</h3><span>{{ platform.status }}</span></div>
                <p>{{ platform.description }}</p>
                <ul><li v-for="item in platform.features" :key="item">{{ item }}</li></ul>
              </div>
            </article>
            <article class="platform-card platform-card--more">
              <div class="platform-icon more-icon"><el-icon><Plus /></el-icon></div>
              <div>
                <div class="platform-title"><h3>更多常用工具</h3><span>持续接入中</span></div>
                <p>后续会继续接入新的签到、打卡和任务工具，并沿用统一账号、任务与记录体系。</p>
              </div>
            </article>
          </div>
        </div>
      </section>

      <section id="features" class="section features-section">
        <div class="section-inner">
          <div class="section-heading"><p class="eyebrow">核心能力</p><h2>减少重复操作，让签到更轻松</h2></div>
          <div class="feature-grid">
            <article v-for="feature in features" :key="feature.title" class="feature-card">
              <div class="feature-icon"><el-icon><component :is="feature.icon" /></el-icon></div>
              <h3>{{ feature.title }}</h3><p>{{ feature.description }}</p>
            </article>
          </div>
        </div>
      </section>

      <section id="guide" class="section guide-section">
        <div class="section-inner">
          <div class="section-heading"><p class="eyebrow">使用流程</p><h2>三步开始使用</h2></div>
          <div class="steps">
            <article v-for="step in steps" :key="step.number" class="step-card">
              <span>{{ step.number }}</span><div><h3>{{ step.title }}</h3><p>{{ step.description }}</p></div>
            </article>
          </div>
        </div>
      </section>

      <section id="pricing" class="section pricing-section">
        <div class="section-inner">
          <div class="section-heading">
            <p class="eyebrow">会员卡</p><h2>按需要选择次卡或月卡</h2>
            <p>购买后获得系统登录账号，可在已授权的平台中使用完整任务能力。</p>
          </div>
          <div class="pricing-grid">
            <article class="pricing-card">
              <div><p class="plan-label">灵活使用</p><h3>次卡</h3><p>按成功签到次数核销，适合短期或低频使用。</p></div>
              <ul><li>可设置签到总次数</li><li>核销后按配置时间失效</li><li>运行记录保留</li></ul>
              <button class="btn-primary btn-block" @click="goBuy">购买次卡</button>
            </article>
            <article class="pricing-card pricing-card--featured">
              <span class="recommended">推荐</span>
              <div><p class="plan-label">长期使用</p><h3>月卡</h3><p>首次登录激活，30 天内持续使用。</p></div>
              <ul><li>激活后 30 天有效</li><li>支持自动任务和多账号管理</li><li>到期后归档保留记录</li></ul>
              <button class="btn-primary btn-block" @click="goBuy">购买月卡</button>
            </article>
          </div>
        </div>
      </section>
    </main>

    <footer class="footer">
      <div class="footer-inner">
        <div class="footer-brand"><img :src="logoImage" alt="轻签" /><strong>轻签</strong></div>
        <p>多平台自动化签到管理，更多常用工具持续接入中。</p>
        <button class="btn-outline" @click="goLogin">前往登录</button>
      </div>
    </footer>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Document, Location, Plus, Timer, UserFilled } from '@element-plus/icons-vue'
import { getSiteConfigApi } from '../api'
import logoImage from '../img/logo.png'
import xxqdImage from '../img/xxqd.png'
import classCubeImage from '../img/bjmf.png'
import miaoyingImage from '../img/miaoying.png'

const router = useRouter()
const DEFAULT_BUY_URL = 'https://m.tb.cn/h.8sGQxfh?tk=Dz6vT8OEx7h'
const GUIDE_URL = 'https://my.feishu.cn/wiki/space/7686887090772003768?ccm_open_type=lark_wiki_spaceLink&open_tab_from=wiki_home'
const purchaseUrl = ref(DEFAULT_BUY_URL)
const platforms = [
  { name: '小小签到', status: '已支持', image: xxqdImage, description: '适合日常任务签到，支持账号、自动任务及运行记录。', features: ['自动任务', '多账号管理', '运行记录'] },
  { name: '班级魔方', status: '已支持', image: classCubeImage, description: '支持课程任务、定位搜索和图片签到等常见场景。', features: ['课程签到', '定位搜索', '图片任务'] },
  { name: '秒应', status: '已支持', image: miaoyingImage, description: '支持秒应账号、任务配置和运行结果集中管理。', features: ['自动任务', '表单处理', '结果追踪'] },
]
const features = [
  { title: '统一账号管理', icon: UserFilled, description: '在同一后台管理不同平台的账号，权限和状态清晰可见。' },
  { title: '自动任务执行', icon: Timer, description: '按计划自动执行任务，减少重复的人工操作。' },
  { title: '定位与参数辅助', icon: Location, description: '集中维护定位、文本和图片等任务参数。' },
  { title: '运行记录留档', icon: Document, description: '记录每次执行结果，账号归档后历史记录仍然保留。' },
]
const steps = [
  { number: '01', title: '购买会员卡', description: '选择次卡或月卡，完成购买后获取系统账号。' },
  { number: '02', title: '登录并绑定账号', description: '登录轻签，按已授权平台添加或扫码绑定账号。' },
  { number: '03', title: '配置自动任务', description: '设置任务时间和参数，后续由系统自动执行并记录结果。' },
]

async function loadSiteConfig() {
  try {
    const response = await getSiteConfigApi()
    purchaseUrl.value = response.data.purchase_url || DEFAULT_BUY_URL
  } catch {
    purchaseUrl.value = DEFAULT_BUY_URL
  }
}
function goBuy() { window.open(purchaseUrl.value, '_blank', 'noopener,noreferrer') }
function goLogin() { router.push('/login') }
onMounted(loadSiteConfig)
</script>

<style scoped>
.landing-page { --primary:#3157d5; --primary-soft:#eef3ff; --accent:#ff7a45; --text:#172033; --muted:#64748b; --border:#dce5f2; --bg:#f7f9fc; min-height:100vh; color:var(--text); background:var(--bg); font-family:-apple-system,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif; }
.nav-bar { position:sticky; top:0; z-index:100; border-bottom:1px solid rgb(220 229 242 / 86%); background:rgb(255 255 255 / 94%); backdrop-filter:blur(14px); }
.nav-inner { display:flex; width:min(1180px,100%); height:68px; margin:0 auto; padding:0 24px; align-items:center; justify-content:space-between; gap:20px; }
.nav-logo { display:flex; align-items:center; gap:10px; color:var(--text); font-size:19px; font-weight:800; text-decoration:none; }
.system-logo { width:38px; height:38px; object-fit:contain; }
.nav-links { display:flex; align-items:center; gap:22px; }
.nav-links a { color:#475569; font-size:14px; font-weight:600; text-decoration:none; }
.nav-links a:hover { color:var(--primary); }
.nav-links a.btn-guide { display:inline-flex; min-height:36px; align-items:center; padding:0 14px; border:1px solid #d6e2fb; border-radius:999px; background:#f4f8ff; color:var(--primary); font-size:13px; }
.nav-links a.btn-guide:hover { border-color:var(--primary); background:#eaf1ff; color:var(--primary); }
button { font:inherit; }
.btn-primary,.btn-outline { display:inline-flex; min-height:40px; padding:0 20px; align-items:center; justify-content:center; border-radius:10px; font-weight:700; cursor:pointer; transition:.2s ease; }
.btn-primary { border:1px solid var(--primary); color:#fff; background:var(--primary); }
.btn-primary:hover { border-color:#2648bc; background:#2648bc; transform:translateY(-1px); }
.btn-outline { border:1px solid #b9c7dc; color:#334155; background:#fff; }
.btn-outline:hover { border-color:var(--primary); color:var(--primary); }
.btn-lg { min-height:48px; padding-inline:26px; font-size:15px; }
.btn-block { width:100%; }
.hero { position:relative; overflow:hidden; padding:84px 24px 72px; background:radial-gradient(circle at 50% 0%,#dfe8ff 0,transparent 42%),linear-gradient(180deg,#fff 0%,#f7f9fc 100%); }
.hero::after { position:absolute; inset:auto 0 0; height:1px; background:linear-gradient(90deg,transparent,#d9e3f2,transparent); content:""; }
.hero-inner { position:relative; z-index:1; width:min(900px,100%); margin:0 auto; text-align:center; }
.hero-mark { display:grid; width:76px; height:76px; margin:0 auto 20px; place-items:center; border:1px solid #dfe7f6; border-radius:22px; background:#fff; box-shadow:0 18px 45px rgb(49 87 213 / 14%); }
.hero-mark img { width:58px; height:58px; object-fit:contain; }
.eyebrow { margin:0 0 10px; color:var(--primary); font-size:13px; font-weight:800; letter-spacing:.08em; }
.hero h1 { margin:0; font-size:56px; line-height:1.05; }
.hero h2 { margin:14px 0 0; color:#24334f; font-size:27px; line-height:1.35; }
.hero-desc { max-width:780px; margin:22px auto 0; color:var(--muted); font-size:16px; line-height:1.85; }
.hero-actions { display:flex; margin-top:30px; justify-content:center; gap:12px; }
.hero-actions .hero-guide { display:none; align-items:center; justify-content:center; text-decoration:none; }
.hero-points { display:flex; margin-top:28px; justify-content:center; flex-wrap:wrap; gap:10px 22px; color:#52647e; font-size:13px; font-weight:600; }
.hero-points span::before { margin-right:6px; color:#22a06b; content:"✓"; }
.section { padding:78px 24px; }
.section-inner { width:min(1180px,100%); margin:0 auto; }
.section-heading { max-width:760px; margin:0 auto 38px; text-align:center; }
.section-heading h2 { margin:0; color:#14213a; font-size:34px; line-height:1.3; }
.section-heading > p:last-child { margin:14px 0 0; color:var(--muted); font-size:15px; line-height:1.8; }
.platforms-section { background:#fff; }
.platform-grid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:18px; }
.platform-card { display:grid; grid-template-columns:64px minmax(0,1fr); gap:18px; align-items:center; padding:24px; border:1px solid var(--border); border-radius:16px; background:linear-gradient(145deg,#fff,#f8fbff); }
.platform-card--more { border-style:dashed; background:#fbfcff; }
.platform-icon { display:grid; width:64px; height:64px; place-items:center; border:1px solid #e0e8f5; border-radius:16px; background:#fff; }
.platform-icon img { width:46px; height:46px; object-fit:contain; }
.more-icon { color:var(--primary); background:var(--primary-soft); font-size:28px; }
.platform-title { display:flex; align-items:center; justify-content:space-between; gap:12px; }
.platform-title h3 { margin:0; font-size:19px; }
.platform-title span { padding:3px 9px; border-radius:99px; color:#246a4e; background:#e8f8f0; font-size:11px; font-weight:700; }
.platform-card p { margin:10px 0 14px; color:var(--muted); font-size:14px; line-height:1.75; }
.platform-card ul,.pricing-card ul { display:flex; margin:0; padding:0; flex-wrap:wrap; gap:8px; list-style:none; }
.platform-card li,.pricing-card li { padding:4px 9px; border-radius:7px; color:#4b5d76; background:#eef3fa; font-size:12px; }
.features-section { background:linear-gradient(180deg,#f7f9fc,#fff); }
.feature-grid { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:16px; }
.feature-card { padding:24px; border:1px solid var(--border); border-radius:15px; background:#fff; }
.feature-icon { display:grid; width:44px; height:44px; margin-bottom:18px; place-items:center; border-radius:12px; color:var(--primary); background:var(--primary-soft); font-size:21px; }
.feature-card h3 { margin:0 0 10px; font-size:17px; }
.feature-card p { margin:0; color:var(--muted); font-size:13px; line-height:1.75; }
.guide-section { background:#fff; }
.steps { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:18px; }
.step-card { display:flex; align-items:center; padding:24px; gap:16px; border:1px solid var(--border); border-radius:15px; background:#f9fbff; }
.step-card > span { flex:none; color:var(--primary); font-size:28px; font-weight:800; }
.step-card h3 { margin:1px 0 9px; font-size:17px; }
.step-card p { margin:0; color:var(--muted); font-size:13px; line-height:1.75; }
.pricing-section { background:linear-gradient(180deg,#f7f9fc,#eef3ff); }
.pricing-grid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); max-width:820px; margin:0 auto; gap:22px; }
.pricing-card { position:relative; display:grid; padding:30px; gap:22px; border:1px solid var(--border); border-radius:17px; background:#fff; box-shadow:0 16px 40px rgb(26 46 94 / 7%); }
.pricing-card--featured { border:2px solid var(--primary); }
.recommended { position:absolute; top:-12px; left:28px; padding:4px 12px; border-radius:99px; color:#fff; background:var(--accent); font-size:11px; font-weight:800; }
.plan-label { margin:0 0 6px; color:var(--primary); font-size:12px; font-weight:800; }
.pricing-card h3 { margin:0; font-size:28px; }
.pricing-card > div > p:last-child { margin:10px 0 0; color:var(--muted); font-size:13px; line-height:1.7; }
.footer { padding:34px 24px; color:#dbe5f7; background:#111827; }
.footer-inner { display:flex; width:min(1180px,100%); margin:0 auto; align-items:center; justify-content:space-between; gap:18px; }
.footer-brand { display:flex; align-items:center; gap:9px; color:#fff; }
.footer-brand img { width:34px; height:34px; object-fit:contain; }
.footer-brand strong { font-size:18px; }
.footer p { margin:0; color:#9ca9bd; font-size:13px; }
.footer .btn-outline { border-color:#465268; color:#fff; background:transparent; }
@media (max-width:900px) {
  .nav-links a:not(.btn-guide) { display:none; }
  .feature-grid { grid-template-columns:repeat(2,minmax(0,1fr)); }
  .platform-grid { grid-template-columns:1fr; }
}
@media (max-width:640px) {
  .nav-inner { height:60px; padding:0 14px; }
  .system-logo { width:32px; height:32px; }
  .nav-links { gap:8px; }
  .nav-links .btn-primary { display:inline-flex; min-height:36px; padding-inline:14px; font-size:13px; }
  .nav-links .btn-outline { min-height:36px; padding-inline:14px; }
  .hero { padding:52px 16px 46px; }
  .hero-mark { width:62px; height:62px; border-radius:18px; }
  .hero-mark img { width:48px; height:48px; }
  .hero h1 { font-size:40px; }
  .hero h2 { font-size:20px; }
  .hero-desc { font-size:14px; }
  .hero-actions { display:grid; grid-template-columns:1fr; }
  .hero-actions .hero-guide { display:inline-flex; }
  .hero-points { align-items:center; flex-direction:row; flex-wrap:wrap; justify-content:center; gap:6px 14px; font-size:12px; }
  .section { padding:54px 16px; }
  .section-heading { margin-bottom:28px; }
  .section-heading h2 { font-size:25px; }
  .platform-card { grid-template-columns:52px minmax(0,1fr); min-height:0; padding:18px; }
  .platform-card > div { display:flex; flex-direction:column; justify-content:center; }
  .platform-icon { width:52px; height:52px; }
  .platform-icon img { width:38px; height:38px; }
  .feature-grid,.steps,.pricing-grid { grid-template-columns:1fr; }
  .feature-card,.step-card,.pricing-card { min-height:0; padding:20px; }
  .step-card { align-items:center; }
  .step-card > div { flex:1; }
  .footer-inner { align-items:flex-start; flex-direction:column; }
}
</style>
