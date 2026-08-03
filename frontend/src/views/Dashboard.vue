<template>
  <div class="dashboard-page">
    <section class="dashboard-hero">
      <div>
        <p class="eyebrow">SIGN-IN OPERATIONS CENTER</p>
        <h1>综合总览</h1>
        <p>集中查看小小签到与班级魔方的运行情况、任务分布和执行排行。</p>
      </div>
      <el-button class="refresh-button" :loading="loading" :icon="Refresh" @click="loadDashboard">
        {{ loading ? '加载中' : '刷新数据' }}
      </el-button>
    </section>

    <el-alert
      v-for="error in platformErrors"
      :key="error"
      class="platform-alert"
      type="warning"
      :title="error"
      :closable="false"
    />

    <el-skeleton v-if="loading && !loadedOnce" :rows="5" animated />
    <template v-else>
      <section class="metric-grid">
        <article v-for="card in metrics.cards" :key="card.label" class="metric-card" :class="`metric-${card.tone}`">
          <div class="metric-icon"><el-icon><component :is="iconFor(card.tone)" /></el-icon></div>
          <div><strong>{{ card.value }}</strong><span>{{ card.label }}</span></div>
        </article>
      </section>

      <section class="content-grid">
        <el-card class="panel status-panel" shadow="never">
          <template #header><div class="panel-title"><span>运行状态</span><el-tag type="info">班级魔方记录</el-tag></div></template>
          <div class="status-list">
            <div v-for="item in statusItems" :key="item.key" class="status-row">
              <span class="status-dot" :class="`dot-${item.key}`"></span>
              <span>{{ item.label }}</span><strong>{{ item.value }}</strong>
              <div class="status-track"><i :class="`bar-${item.key}`" :style="{ width: `${statusPercent(item.value)}%` }"></i></div>
            </div>
          </div>
        </el-card>

        <el-card class="panel type-panel" shadow="never">
          <template #header><div class="panel-title"><span>签到类型分布</span><el-tag type="primary">任务</el-tag></div></template>
          <el-empty v-if="!metrics.typeDistribution.length" description="暂无任务类型数据" :image-size="70" />
          <div v-else class="type-list">
            <div v-for="item in metrics.typeDistribution" :key="item.label" class="type-row">
              <div class="type-name"><span>{{ item.label }}</span><strong>{{ item.value }}</strong></div>
              <div class="type-track"><i :style="{ width: `${typePercent(item.value)}%` }"></i></div>
            </div>
          </div>
        </el-card>
      </section>

      <section class="content-grid lower-grid">
        <el-card class="panel recent-panel" shadow="never">
          <template #header><div class="panel-title"><span>最近运行</span><el-button link type="primary" @click="router.push('/class-cube/runs')">查看全部</el-button></div></template>
          <el-empty v-if="!metrics.recentRuns.length" description="暂无运行记录" :image-size="70" />
          <div v-else class="recent-list">
            <div v-for="(run, index) in metrics.recentRuns" :key="run.id || index" class="recent-row">
              <span class="recent-index">{{ index + 1 }}</span>
              <div class="recent-main"><strong>{{ run.task_name || run.task_title || '签到任务' }}</strong><small>{{ run.account_name || '未知账号' }} · {{ formatTime(run.started_at || run.created_at) }}</small></div>
              <el-tag size="small" :type="statusTagType(run.status)">{{ statusLabel(run.status) }}</el-tag>
            </div>
          </div>
        </el-card>

        <el-card class="panel ranking-panel" shadow="never">
          <template #header><div class="panel-title"><span>账号排行</span><el-tag type="success">成功次数</el-tag></div></template>
          <el-empty v-if="!metrics.ranking.length" description="暂无排行数据" :image-size="70" />
          <div v-else class="ranking-list">
            <div v-for="(item, index) in metrics.ranking" :key="item.name" class="ranking-row">
              <span class="rank-number" :class="{ top: index < 3 }">{{ index + 1 }}</span><span class="rank-name">{{ item.name }}</span><strong>{{ item.value }} 次</strong>
            </div>
          </div>
        </el-card>
      </section>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { CircleCheck, Document, Refresh, Tickets, User } from '@element-plus/icons-vue'
import { useRouter } from 'vue-router'
import api from '../api'
import classCubeApi from '../api/classCube.js'
import { buildDashboardMetrics } from '../utils/dashboardMetrics.js'

const router = useRouter()
const loading = ref(false)
const loadedOnce = ref(false)
const platformErrors = ref([])
const metrics = ref(buildDashboardMetrics())
const statusItems = computed(() => [
  { key: 'success', label: '签到成功', value: metrics.value.statuses.success },
  { key: 'failed', label: '签到失败', value: metrics.value.statuses.failed },
  { key: 'running', label: '执行中', value: metrics.value.statuses.running },
  { key: 'pending', label: '待处理', value: metrics.value.statuses.pending },
])
const totalStatuses = computed(() => statusItems.value.reduce((sum, item) => sum + item.value, 0))
const maxTypeValue = computed(() => Math.max(...metrics.value.typeDistribution.map(item => item.value), 1))

const iconFor = tone => ({ blue: User, violet: Tickets, green: CircleCheck, cyan: User, orange: Document, slate: Tickets }[tone] || Document)
const statusPercent = value => totalStatuses.value ? Math.max(4, Math.round(value / totalStatuses.value * 100)) : 0
const typePercent = value => Math.max(4, Math.round(value / maxTypeValue.value * 100))
const statusLabel = status => ({ success: '成功', already_signed: '已签到', failed: '失败', error: '失败', running: '执行中', submitting: '提交中' }[String(status || '').toLowerCase()] || '待处理')
const statusTagType = status => ({ success: 'success', already_signed: 'success', failed: 'danger', error: 'danger', running: 'warning', submitting: 'warning' }[String(status || '').toLowerCase()] || 'info')
const formatTime = value => value ? new Date(value).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }) : '-'

function unwrap(response, fallback) {
  if (response?.ok === false) throw new Error(response.error || '请求失败')
  return response?.data ?? fallback
}

async function loadDashboard() {
  loading.value = true
  platformErrors.value = []
  const results = await Promise.allSettled([
    api.getState(),
    api.getLogs(100),
    classCubeApi.listAccounts(),
    classCubeApi.listTasks(),
    classCubeApi.listRuns({ limit: 100 }),
  ])
  const values = results.map(result => result.status === 'fulfilled' ? result.value : null)
  const messages = []
  if (results[0].status === 'rejected' || results[1].status === 'rejected') messages.push('小小签到数据暂时不可用')
  if (results.slice(2).some(result => result.status === 'rejected')) messages.push('班级魔方数据暂时不可用')
  platformErrors.value = messages
  metrics.value = buildDashboardMetrics({
    xxqd: results[0].status === 'fulfilled' ? unwrap(values[0], {}) : null,
    xxqdLogs: results[1].status === 'fulfilled' ? unwrap(values[1], []) : null,
    cubeAccounts: results[2].status === 'fulfilled' ? unwrap(values[2], []) : null,
    cubeTasks: results[3].status === 'fulfilled' ? unwrap(values[3], []) : null,
    cubeRuns: results[4].status === 'fulfilled' ? unwrap(values[4], []) : null,
  })
  loadedOnce.value = true
  loading.value = false
}

onMounted(loadDashboard)
</script>

<style scoped>
.dashboard-page{display:grid;gap:18px}.dashboard-hero{display:flex;align-items:center;justify-content:space-between;gap:20px;padding:28px;border-radius:24px;color:#fff;background:linear-gradient(125deg,#1e40af,#0891b2);box-shadow:0 20px 50px #1d4ed83b}.eyebrow{margin:0;font-size:11px;letter-spacing:.18em;opacity:.8}.dashboard-hero h1{margin:9px 0 6px;font-size:30px}.dashboard-hero p:last-child{margin:0;color:#dbeafe}.refresh-button{color:#1d4ed8;background:#fff;border:0}.platform-alert{margin-bottom:0}.metric-grid{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:14px}.metric-card{display:flex;align-items:center;gap:12px;min-height:88px;padding:16px;border:1px solid #dbeafe;border-radius:18px;background:#fff;box-shadow:0 12px 30px #0f172a0b}.metric-icon{display:grid;place-items:center;width:42px;height:42px;border-radius:14px;background:#dbeafe;color:#2563eb}.metric-card strong,.metric-card span{display:block}.metric-card strong{font-size:25px;color:#0f172a}.metric-card span{margin-top:5px;font-size:12px;color:#64748b}.metric-violet .metric-icon{background:#ede9fe;color:#7c3aed}.metric-green .metric-icon{background:#dcfce7;color:#16a34a}.metric-cyan .metric-icon{background:#cffafe;color:#0891b2}.metric-orange .metric-icon{background:#ffedd5;color:#ea580c}.metric-slate .metric-icon{background:#e2e8f0;color:#475569}.content-grid{display:grid;grid-template-columns:1fr 1fr;gap:18px}.panel{border:1px solid #dbeafe;border-radius:22px;background:#ffffffd9}.panel-title{display:flex;align-items:center;justify-content:space-between;font-weight:700}.status-list,.type-list,.recent-list,.ranking-list{display:grid;gap:15px}.status-row{display:grid;grid-template-columns:10px 70px 38px 1fr;align-items:center;gap:10px;color:#64748b;font-size:13px}.status-row strong{color:#0f172a;text-align:right}.status-dot{width:9px;height:9px;border-radius:50%}.dot-success{background:#22c55e}.dot-failed{background:#ef4444}.dot-running{background:#f59e0b}.dot-pending{background:#94a3b8}.status-track,.type-track{height:8px;overflow:hidden;border-radius:99px;background:#eef2f7}.status-track i,.type-track i{display:block;height:100%;border-radius:inherit;background:#22c55e}.bar-failed{background:#ef4444!important}.bar-running{background:#f59e0b!important}.bar-pending{background:#94a3b8!important}.type-name{display:flex;justify-content:space-between;color:#475569;font-size:13px}.type-name strong{color:#1d4ed8}.type-track i{background:linear-gradient(90deg,#2563eb,#06b6d4)}.recent-row,.ranking-row{display:flex;align-items:center;gap:12px;padding:10px 0;border-bottom:1px solid #eef2f7}.recent-row:last-child,.ranking-row:last-child{border-bottom:0}.recent-index,.rank-number{display:grid;place-items:center;width:26px;height:26px;border-radius:9px;background:#eff6ff;color:#2563eb;font-size:12px}.recent-main{flex:1;min-width:0}.recent-main strong,.recent-main small{display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.recent-main strong{color:#334155}.recent-main small{margin-top:4px;color:#94a3b8}.rank-name{flex:1;color:#334155}.rank-number.top{color:#fff;background:#2563eb}.ranking-row strong{color:#16a34a}@media(max-width:1200px){.metric-grid{grid-template-columns:repeat(3,1fr)}}@media(max-width:760px){.dashboard-hero{align-items:flex-start;flex-direction:column}.metric-grid,.content-grid{grid-template-columns:1fr}.metric-grid{grid-template-columns:repeat(2,1fr)}}
</style>
