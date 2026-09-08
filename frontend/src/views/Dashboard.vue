<template>
  <div class="dashboard-page">
    <section class="dashboard-hero">
      <div class="hero-copy">
        <p class="eyebrow">SIGN-IN OPERATIONS CENTER</p>
        <h1>综合总览</h1>
        <p>用统一口径查看小小签到、班级魔方与秒应的执行质量、任务规模和资源用量。</p>
      </div>
      <div class="hero-actions">
        <el-segmented v-model="range" :options="rangeOptions" @change="loadDashboard" />
        <el-button class="refresh-button" :loading="loading" :icon="Refresh" @click="loadDashboard">
          {{ loading ? '加载中' : '刷新数据' }}
        </el-button>
        <small v-if="summary.generated_at">更新于 {{ formatDateTime(summary.generated_at) }}</small>
      </div>
    </section>

    <el-alert v-if="errorMessage" type="warning" :title="errorMessage" :closable="false" show-icon />

    <el-skeleton v-if="loading && !loadedOnce" :rows="8" animated />
    <template v-else>
      <section class="metric-grid">
        <article v-for="card in coreCards" :key="card.label" class="metric-card" :class="`metric-${card.tone}`">
          <div class="metric-top"><span>{{ card.label }}</span><el-icon><component :is="card.icon" /></el-icon></div>
          <strong>{{ card.value }}</strong>
          <small>{{ card.note }}</small>
        </article>
      </section>

      <section class="platform-grid">
        <article v-for="platform in platformCards" :key="platform.key" class="platform-card" :class="`platform-${platform.key}`">
          <header>
            <div class="platform-title">
              <span class="platform-logo"><img :src="platform.logo" :alt="`${platform.name}图标`" /></span>
              <div><strong>{{ platform.name }}</strong><small>{{ platform.description }}</small></div>
            </div>
            <el-tag effect="plain">{{ rangeLabel }}</el-tag>
          </header>
          <div class="platform-kpis">
            <div><span>执行</span><strong>{{ platform.data.executions }}</strong></div>
            <div><span>成功</span><strong class="success-text">{{ platform.data.success }}</strong></div>
            <div><span>失败</span><strong class="danger-text">{{ platform.data.failed }}</strong></div>
            <div><span>其他</span><strong>{{ platform.data.other }}</strong></div>
          </div>
          <div class="rate-line"><span>成功率</span><strong>{{ formatPercent(platform.data.success_rate) }}</strong></div>
          <el-progress :percentage="platform.data.success_rate || 0" :stroke-width="9" :show-text="false" />
          <footer>
            <span><b>{{ platform.data.accounts }}</b> 个账号</span>
            <span><b>{{ platform.data.tasks }}</b> 个任务</span>
            <span><b>{{ platform.data.enabled_tasks }}</b> 个启用</span>
          </footer>
        </article>
      </section>

      <section class="main-grid">
        <el-card class="panel recent-panel" shadow="never">
          <template #header>
            <div class="panel-title"><div><strong>最近执行</strong><small>三个平台按时间统一排列</small></div><el-tag type="info">最近 {{ summary.recent_runs.length }} 条</el-tag></div>
          </template>
          <el-empty v-if="!summary.recent_runs.length" description="当前统计范围暂无执行记录" :image-size="72" />
          <div v-else class="recent-list">
            <article v-for="run in summary.recent_runs" :key="`${run.platform}-${run.id}`" class="recent-row">
              <span class="platform-pill" :class="run.platform">{{ platformShortName(run.platform) }}</span>
              <div class="recent-main">
                <strong>{{ run.task_title || run.task_name || '签到任务' }}</strong>
                <small>{{ run.account_name || '未知账号' }} · {{ modeLabel(run.mode) }}</small>
              </div>
              <div class="recent-result">
                <el-tag size="small" :type="statusTagType(run.status)">{{ statusLabel(run.status) }}</el-tag>
                <time>{{ formatDateTime(run.started_at) }}</time>
              </div>
            </article>
          </div>
        </el-card>

        <div class="side-stack">
          <el-card class="panel resource-panel" shadow="never">
            <template #header><div class="panel-title"><div><strong>系统资源</strong><small>配额和后台用户状态</small></div><el-icon><Location /></el-icon></div></template>
            <div class="location-quota-list">
              <div v-for="quota in locationQuotas" :key="quota.key" class="location-quota">
                <div class="resource-heading"><span>{{ quota.label }}</span><strong>{{ quota.used }}/{{ quota.limit || '不限' }}</strong></div>
                <el-progress :percentage="quota.percent" :stroke-width="10" :show-text="false" :status="quota.percent >= 90 ? 'exception' : undefined" />
                <div class="resource-meta"><span>今日剩余 <b>{{ quota.remaining }}</b></span><span>{{ quota.date || '-' }}</span></div>
              </div>
            </div>
            <div class="resource-users">
              <span><el-icon><User /></el-icon>后台用户</span>
              <strong>{{ summary.resources.users }} 人</strong>
              <small>启用 {{ summary.resources.active_users }} 人</small>
            </div>
            <p class="resource-tip">关键词输入提示与逆地址解析分别计算每日额度；仅统计本系统实际请求，缓存命中不重复计数。</p>
          </el-card>

          <el-card class="panel distribution-panel" shadow="never">
            <template #header><div class="panel-title"><div><strong>结果分布</strong><small>成功、失败与非提交结果</small></div></div></template>
            <div class="distribution-list">
              <div v-for="item in summary.status_distribution" :key="item.key" class="distribution-row">
                <span class="status-dot" :class="item.key"></span><span>{{ item.label }}</span><strong>{{ item.value }}</strong>
                <div class="track"><i :class="item.key" :style="{ width: statusWidth(item.value) }"></i></div>
              </div>
            </div>
          </el-card>
        </div>
      </section>

      <section class="bottom-grid">
        <el-card class="panel" shadow="never">
          <template #header><div class="panel-title"><div><strong>签到类型</strong><small>按实际执行记录统计</small></div></div></template>
          <el-empty v-if="!summary.type_distribution.length" description="暂无签到类型数据" :image-size="64" />
          <div v-else class="type-list">
            <div v-for="item in summary.type_distribution" :key="item.mode" class="type-row">
              <span>{{ modeLabel(item.mode) }}</span><strong>{{ item.value }} 次</strong>
              <div class="track"><i :style="{ width: typeWidth(item.value) }"></i></div>
            </div>
          </div>
        </el-card>
        <el-card class="panel" shadow="never">
          <template #header><div class="panel-title"><div><strong>账号排行</strong><small>按成功签到次数排序</small></div></div></template>
          <el-empty v-if="!summary.ranking.length" description="暂无成功记录" :image-size="64" />
          <div v-else class="ranking-list">
            <div v-for="(item, index) in summary.ranking" :key="`${item.platform}-${item.name}`" class="ranking-row">
              <span class="rank" :class="{ top: index < 3 }">{{ index + 1 }}</span>
              <span class="platform-pill" :class="item.platform">{{ platformShortName(item.platform) }}</span>
              <strong>{{ item.name }}</strong><b>{{ item.value }} 次</b>
            </div>
          </div>
        </el-card>
      </section>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { CircleCheck, Clock, DataAnalysis, Location, Refresh, Timer, User } from '@element-plus/icons-vue'
import { getDashboardSummaryApi } from '../api'
import xxqdImage from '../img/xxqd.png'
import classCubeImage from '../img/bjmf.png'
import miaoyingImage from '../img/miaoying.png'

const emptyPlatform = () => ({ accounts: 0, tasks: 0, enabled_tasks: 0, executions: 0, success: 0, failed: 0, other: 0, success_rate: 0 })
const emptySummary = () => ({
  generated_at: '', totals: { executions: 0, success: 0, failed: 0, other: 0, success_rate: 0, enabled_tasks: 0 },
  platforms: { xxqd: emptyPlatform(), class_cube: emptyPlatform(), miaoying: emptyPlatform() }, status_distribution: [], type_distribution: [], recent_runs: [], ranking: [],
  resources: { tencent_location: { used: 0, limit: 0, date: '', items: [] }, users: 0, active_users: 0 },
})

const loading = ref(false)
const loadedOnce = ref(false)
const errorMessage = ref('')
const range = ref('today')
const summary = ref(emptySummary())
const rangeOptions = [{ label: '今天', value: 'today' }, { label: '近 7 天', value: '7d' }, { label: '近 30 天', value: '30d' }]
const rangeLabel = computed(() => rangeOptions.find(item => item.value === range.value)?.label || '今天')
const locationUsage = computed(() => summary.value.resources?.tencent_location || {})
const locationQuotas = computed(() => {
  const items = Array.isArray(locationUsage.value.items) ? locationUsage.value.items : []
  if (items.length) return items.map(item => ({
    ...item,
    used: Number(item.used || 0),
    limit: Number(item.limit || 0),
    remaining: Number(item.limit || 0) > 0 ? Math.max(0, Number(item.limit) - Number(item.used || 0)) : '不限',
    percent: Number(item.limit || 0) > 0 ? Math.min(100, Math.round(Number(item.used || 0) * 100 / Number(item.limit))) : 0,
  }))
  const limit = Number(locationUsage.value.limit || 0)
  const used = Number(locationUsage.value.used || 0)
  const perApiLimit = limit > 6000 ? Math.floor(limit / 2) : (limit || 6000)
  const quota = (key, label, currentUsed) => ({
    key,
    label,
    used: currentUsed,
    limit: perApiLimit,
    remaining: Math.max(0, perApiLimit - currentUsed),
    percent: Math.min(100, Math.round(currentUsed * 100 / perApiLimit)),
    date: locationUsage.value.date,
  })
  return [
    quota('suggestion', '关键词输入提示', used),
    quota('reverse', '逆地址解析', 0),
  ]
})
const maxStatus = computed(() => Math.max(...summary.value.status_distribution.map(item => item.value), 1))
const maxType = computed(() => Math.max(...summary.value.type_distribution.map(item => item.value), 1))
const coreCards = computed(() => [
  { label: '执行次数', value: summary.value.totals.executions, note: `${rangeLabel.value}三个平台合计`, tone: 'blue', icon: Timer },
  { label: '签到成功', value: summary.value.totals.success, note: `失败 ${summary.value.totals.failed} 次`, tone: 'green', icon: CircleCheck },
  { label: '成功率', value: formatPercent(summary.value.totals.success_rate), note: '成功次数 ÷ 全部执行', tone: 'violet', icon: DataAnalysis },
  { label: '启用任务', value: summary.value.totals.enabled_tasks, note: '当前正在参与调度', tone: 'orange', icon: Clock },
])
const platformCards = computed(() => [
  { key: 'xxqd', name: '小小签到', description: '自动签到任务执行情况', logo: xxqdImage, data: summary.value.platforms.xxqd || emptyPlatform() },
  { key: 'class_cube', name: '班级魔方', description: '课程签到项提交情况', logo: classCubeImage, data: summary.value.platforms.class_cube || emptyPlatform() },
  { key: 'miaoying', name: '秒应', description: '报名签到与日期计划执行情况', logo: miaoyingImage, data: summary.value.platforms.miaoying || emptyPlatform() },
])

const modeLabel = mode => ({ normal: '普通签到', image: '图片签到', gps: 'GPS 签到', gps_photo: 'GPS 拍照签到', password: '密码签到', qr: '二维码签到', task: '任务扫描', miaoying: '秒应签到', unknown: '其他签到' }[String(mode || '').toLowerCase()] || '其他签到')
const statusLabel = status => ({ success: '成功', already_signed: '已签到', failed: '失败', error: '失败', unknown_result: '待确认', no_sign_in: '无签到项', skipped: '已跳过', waiting_parameter: '待补参数', running: '执行中' }[String(status || '').toLowerCase()] || '其他')
const statusTagType = status => ({ success: 'success', already_signed: 'success', failed: 'danger', error: 'danger', unknown_result: 'warning', waiting_parameter: 'warning', running: 'warning' }[String(status || '').toLowerCase()] || 'info')
const platformShortName = platform => ({ xxqd: '小小', class_cube: '魔方', miaoying: '秒应' }[platform] || '其他')
const formatPercent = value => `${Number(value || 0).toFixed(1)}%`
const formatDateTime = value => value ? new Date(value).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false }) : '-'
const statusWidth = value => `${value ? Math.max(5, Math.round(value * 100 / maxStatus.value)) : 0}%`
const typeWidth = value => `${value ? Math.max(5, Math.round(value * 100 / maxType.value)) : 0}%`

async function loadDashboard() {
  loading.value = true
  errorMessage.value = ''
  try {
    const response = await getDashboardSummaryApi(range.value)
    summary.value = response?.data || emptySummary()
  } catch (error) {
    errorMessage.value = error.message || '综合总览数据加载失败'
  } finally {
    loadedOnce.value = true
    loading.value = false
  }
}

onMounted(loadDashboard)
</script>

<style scoped>
.dashboard-page{display:grid;gap:18px;min-width:0}.dashboard-hero{display:flex;align-items:center;justify-content:space-between;gap:24px;padding:26px 28px;border-radius:24px;color:#fff;background:linear-gradient(125deg,#1e40af 0%,#2563eb 48%,#0891b2 100%);box-shadow:0 20px 50px #1d4ed833}.hero-copy{min-width:0}.eyebrow{margin:0;font-size:11px;letter-spacing:.18em;opacity:.8}.dashboard-hero h1{margin:8px 0 5px;font-size:28px}.dashboard-hero p:last-child{margin:0;color:#dbeafe}.hero-actions{display:flex;align-items:center;justify-content:flex-end;gap:10px;flex-wrap:wrap}.hero-actions small{flex-basis:100%;text-align:right;color:#dbeafe}.refresh-button{color:#1d4ed8;background:#fff;border:0}.metric-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px}.metric-card{min-width:0;padding:18px 19px;border:1px solid #dbeafe;border-radius:18px;background:#fff;box-shadow:0 12px 30px #0f172a0a}.metric-top{display:flex;align-items:center;justify-content:space-between;color:#64748b}.metric-top .el-icon{display:grid;place-items:center;width:34px;height:34px;border-radius:11px;color:#2563eb;background:#eff6ff}.metric-card>strong{display:block;margin:10px 0 3px;font-size:28px;color:#0f172a}.metric-card>small{color:#94a3b8}.metric-green .metric-top .el-icon{color:#16a34a;background:#dcfce7}.metric-violet .metric-top .el-icon{color:#7c3aed;background:#ede9fe}.metric-orange .metric-top .el-icon{color:#ea580c;background:#ffedd5}.platform-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:18px}.platform-card{padding:20px;border:1px solid #bfdbfe;border-radius:22px;background:linear-gradient(145deg,#fff,#f8fbff);box-shadow:0 12px 35px #2563eb0d}.platform-card header,.platform-title,.platform-card footer,.rate-line{display:flex;align-items:center}.platform-card header{justify-content:space-between;gap:12px}.platform-title{gap:12px;min-width:0}.platform-logo{display:grid;place-items:center;width:42px;height:42px;border-radius:14px;color:#2563eb;background:#dbeafe}.platform-title strong,.platform-title small{display:block}.platform-title strong{color:#0f172a;font-size:17px}.platform-title small{margin-top:3px;color:#94a3b8}.platform-class_cube .platform-logo{color:#0891b2;background:#cffafe}.platform-miaoying .platform-logo{color:#16a34a;background:#dcfce7}.platform-kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin:20px 0 16px}.platform-kpis div{padding:10px;border-radius:12px;text-align:center;background:#f1f5f9}.platform-kpis span,.platform-kpis strong{display:block}.platform-kpis span{font-size:12px;color:#64748b}.platform-kpis strong{margin-top:4px;color:#0f172a;font-size:19px}.success-text{color:#16a34a!important}.danger-text{color:#dc2626!important}.rate-line{justify-content:space-between;margin-bottom:8px;color:#64748b;font-size:13px}.platform-card footer{gap:18px;margin-top:16px;padding-top:14px;border-top:1px solid #e2e8f0;color:#64748b;font-size:12px}.platform-card footer b{color:#334155}.main-grid{display:grid;grid-template-columns:minmax(0,1.65fr) minmax(300px,.75fr);gap:18px}.side-stack{display:grid;align-content:start;gap:18px}.panel{min-width:0;border:1px solid #dbeafe;border-radius:22px;background:#ffffffdb}.panel-title{display:flex;align-items:center;justify-content:space-between;gap:12px}.panel-title>div>strong,.panel-title>div>small{display:block}.panel-title>div>small{margin-top:3px;color:#94a3b8;font-weight:400}.recent-list{display:grid}.recent-row{display:flex;align-items:center;gap:12px;padding:13px 0;border-bottom:1px solid #eef2f7}.recent-row:last-child{border-bottom:0}.platform-pill{flex:0 0 auto;padding:4px 7px;border-radius:7px;color:#1d4ed8;background:#dbeafe;font-size:11px}.platform-pill.class_cube{color:#0e7490;background:#cffafe}.platform-pill.miaoying{color:#15803d;background:#dcfce7}.recent-main{flex:1;min-width:0}.recent-main strong,.recent-main small{display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.recent-main strong{color:#334155}.recent-main small{margin-top:4px;color:#94a3b8}.recent-result{display:grid;justify-items:end;gap:5px}.recent-result time{color:#94a3b8;font-size:11px}.location-quota-list{display:grid;gap:16px}.location-quota+.location-quota{padding-top:16px;border-top:1px solid #e2e8f0}.resource-heading,.resource-meta,.resource-users{display:flex;align-items:center;justify-content:space-between}.resource-heading{margin-bottom:9px;color:#475569}.resource-heading strong{color:#0f172a;font-size:18px}.resource-meta{margin-top:8px;color:#94a3b8;font-size:12px}.resource-meta b{color:#2563eb}.resource-users{display:grid;grid-template-columns:1fr auto;gap:4px 12px;margin-top:18px;padding:14px;border-radius:14px;background:#f0f9ff}.resource-users span{display:flex;align-items:center;gap:7px;color:#475569}.resource-users strong{color:#0f172a}.resource-users small{grid-column:1/-1;color:#94a3b8}.resource-tip{margin:12px 0 0;color:#94a3b8;font-size:11px;line-height:1.65}.distribution-list,.type-list,.ranking-list{display:grid;gap:14px}.distribution-row{display:grid;grid-template-columns:9px 90px 38px 1fr;align-items:center;gap:9px;color:#64748b;font-size:12px}.distribution-row strong{text-align:right;color:#0f172a}.status-dot{width:9px;height:9px;border-radius:50%;background:#94a3b8}.status-dot.success,.track i.success{background:#22c55e}.status-dot.failed,.track i.failed{background:#ef4444}.status-dot.other,.track i.other{background:#f59e0b}.track{height:8px;overflow:hidden;border-radius:99px;background:#eef2f7}.track i{display:block;height:100%;border-radius:inherit;background:linear-gradient(90deg,#2563eb,#06b6d4)}.bottom-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px}.type-row{display:grid;grid-template-columns:1fr auto;gap:7px;color:#475569;font-size:13px}.type-row .track{grid-column:1/-1}.type-row strong{color:#1d4ed8}.ranking-row{display:grid;grid-template-columns:28px auto 1fr auto;align-items:center;gap:10px;padding-bottom:11px;border-bottom:1px solid #eef2f7}.ranking-row:last-child{padding-bottom:0;border-bottom:0}.rank{display:grid;place-items:center;width:26px;height:26px;border-radius:9px;color:#2563eb;background:#eff6ff;font-size:12px}.rank.top{color:#fff;background:#2563eb}.ranking-row>strong{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:#334155}.ranking-row>b{color:#16a34a}@media(max-width:1300px){.platform-grid{grid-template-columns:1fr}.metric-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.main-grid{grid-template-columns:1fr}.side-stack{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:760px){.dashboard-hero{align-items:flex-start;flex-direction:column}.hero-actions{justify-content:flex-start;width:100%}.platform-grid,.bottom-grid,.side-stack{grid-template-columns:1fr}.platform-kpis{grid-template-columns:repeat(2,1fr)}}@media(max-width:520px){.metric-grid{grid-template-columns:1fr}.dashboard-hero{padding:22px 18px}.recent-row{align-items:flex-start;flex-wrap:wrap}.recent-main{min-width:calc(100% - 58px)}.recent-result{grid-template-columns:auto auto;align-items:center;width:100%;justify-content:end}.platform-card footer{align-items:flex-start;flex-direction:column;gap:7px}.distribution-row{grid-template-columns:9px 72px 30px 1fr}}
.platform-logo img{display:block;width:100%;height:100%;border-radius:inherit;object-fit:cover}
.location-quota{padding:13px;border:1px solid #dbeafe;border-radius:14px;background:#f8fbff}.location-quota+.location-quota{padding-top:13px;border-top:1px solid #dbeafe}
@media(max-width:760px){.hero-actions small{text-align:left}}
</style>
