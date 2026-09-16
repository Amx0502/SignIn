<template>
  <div class="xxqd-runs-page">
    <el-card class="run-panel" shadow="never">
      <template #header>
        <div class="panel-head">
          <div>
            <strong>运行记录</strong>
            <small>查看小小签到自动任务和手动执行的严格结果记录</small>
          </div>
          <el-button :icon="Refresh" :loading="loading" @click="loadRuns">刷新记录</el-button>
        </div>
      </template>

      <div class="filters">
        <el-select v-model="filters.account_id" clearable placeholder="全部账号" @change="loadRuns">
          <el-option
            v-for="account in accounts"
            :key="account.id"
            :value="account.id"
            :label="account.name || account.mobile || `账号 ${account.id}`"
          />
        </el-select>
        <el-select v-model="filters.task_id" clearable placeholder="全部任务" @change="loadRuns">
          <el-option
            v-for="task in taskOptions"
            :key="task.id"
            :value="task.id"
            :label="task.title"
          />
        </el-select>
        <el-select v-model="filters.source" clearable placeholder="全部来源" @change="loadRuns">
          <el-option v-for="(label, value) in sourceNames" :key="value" :value="value" :label="label" />
        </el-select>
        <el-select v-model="filters.status" clearable placeholder="全部状态" @change="loadRuns">
          <el-option v-for="(meta, value) in statuses" :key="value" :value="value" :label="meta.label" />
        </el-select>
        <el-button type="primary" @click="loadRuns">筛选</el-button>
        <el-button @click="resetFilters">重置</el-button>
      </div>

      <div class="run-summary">
        <span>共 {{ total }} 条记录</span>
        <span v-if="ownerUserId">仅显示用户 {{ route.query.username || ownerUserId }} 的记录</span>
        <span v-if="lastLoadedAt">更新时间：{{ lastLoadedAt }}</span>
      </div>

      <div v-loading="loading" class="run-list">
        <article v-for="run in runs" :key="run.id" class="run-row" @click="openDetail(run)">
          <span class="run-mark" :class="run.status">
            <el-icon><component :is="statusMeta(run.status).icon" /></el-icon>
          </span>
          <div class="run-main">
            <div>
              <strong>{{ run.task_title || `任务 ${run.task_id || '-'}` }}</strong>
              <span class="run-account">{{ run.account_name || `账号 ${run.account_id || '-'}` }}</span>
              <el-tag :type="statusMeta(run.status).type" size="small">
                {{ statusMeta(run.status).label }}
              </el-tag>
            </div>
            <p>{{ run.message || statusMeta(run.status).tip }}</p>
            <small>
              {{ formatTime(run.started_at) }}
              · {{ sourceName(run.source) }}
              · {{ modeName(run.mode) }}
            </small>
          </div>
          <el-icon class="run-arrow"><ArrowRight /></el-icon>
        </article>
        <el-empty v-if="!loading && !runs.length" description="暂无可显示的运行记录" :image-size="90" />
      </div>
    </el-card>

    <el-drawer v-model="detailVisible" title="运行记录详情" size="min(560px, 92vw)">
      <div v-if="currentRun" class="run-detail">
        <div class="detail-row"><span>任务</span><strong>{{ currentRun.task_title || '-' }}</strong></div>
        <div class="detail-row"><span>账号</span><strong>{{ currentRun.account_name || '-' }}</strong></div>
        <div class="detail-row"><span>状态</span><el-tag :type="statusMeta(currentRun.status).type">{{ statusMeta(currentRun.status).label }}</el-tag></div>
        <div class="detail-row"><span>来源</span><strong>{{ sourceName(currentRun.source) }}</strong></div>
        <div class="detail-row"><span>开始时间</span><strong>{{ formatTime(currentRun.started_at) }}</strong></div>
        <div class="detail-row"><span>结束时间</span><strong>{{ formatTime(currentRun.finished_at) }}</strong></div>
        <div class="detail-row detail-row--wide"><span>结果说明</span><p>{{ currentRun.message || statusMeta(currentRun.status).tip }}</p></div>
        <div v-if="summary.real_title" class="detail-row detail-row--wide"><span>实际项目</span><p>{{ summary.real_title }}</p></div>
        <div v-if="summary.text" class="detail-row detail-row--wide"><span>文本内容</span><p>{{ summary.text }}</p></div>
        <div v-if="locationText" class="detail-row detail-row--wide"><span>签到位置</span><p>{{ locationText }}</p></div>
        <div v-if="imageUrls.length" class="detail-row detail-row--wide">
          <span>签到图片</span>
          <div class="detail-images">
            <el-image
              v-for="(url, index) in imageUrls"
              :key="`${url}-${index}`"
              :src="url"
              :preview-src-list="imageUrls"
              :initial-index="index"
              fit="cover"
              preview-teleported
            />
          </div>
        </div>
      </div>
    </el-drawer>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import {
  ArrowRight,
  CircleCheckFilled,
  CircleCloseFilled,
  Clock,
  Refresh,
  WarningFilled,
} from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { useRoute } from 'vue-router'
import { listXxqdRunsApi } from '../api'
import { useAppState } from '../composables/useAppState.js'

const { state: appState, refreshState } = useAppState()
const route = useRoute()
const loading = ref(false)
const runs = ref([])
const total = ref(0)
const lastLoadedAt = ref('')
const detailVisible = ref(false)
const currentRun = ref(null)
const filters = reactive({ account_id: null, task_id: null, source: '', status: '' })
const ownerUserId = computed(() => Number(route.query.owner_user_id) || null)

const accounts = computed(() => appState.value.accounts || [])
const taskOptions = computed(() => accounts.value.flatMap(account =>
  (account.tasks || []).map(task => ({ id: task.id, title: `${account.name} · ${task.title}` }))
))
const statuses = {
  success: { label: '成功', type: 'success', icon: CircleCheckFilled, tip: '签到成功' },
  already_signed: { label: '已签到', type: 'success', icon: CircleCheckFilled, tip: '任务已经完成' },
  waiting_parameter: { label: '等待参数', type: 'warning', icon: Clock, tip: '任务缺少执行参数' },
  unknown_result: { label: '结果未知', type: 'warning', icon: WarningFilled, tip: '签到结果需要人工确认' },
  failed: { label: '失败', type: 'danger', icon: CircleCloseFilled, tip: '任务执行失败' },
  skipped: { label: '跳过', type: 'info', icon: Clock, tip: '本轮无需执行' },
  blocked: { label: '已阻止', type: 'warning', icon: WarningFilled, tip: '会员卡状态已阻止任务执行' },
}
const sourceNames = {
  manual: '手动执行',
  manual_all: '批量执行',
  schedule: '定时执行',
  scheduled: '定时执行',
}
const summary = computed(() => currentRun.value?.response_summary || {})
const imageUrls = computed(() => Array.isArray(summary.value.image_urls) ? summary.value.image_urls : [])
const locationText = computed(() => {
  const location = summary.value.location
  return typeof location === 'string' ? location : location?.address || ''
})

function statusMeta(status) {
  return statuses[status] || statuses.failed
}
function sourceName(source) {
  return sourceNames[source] || source || '未知来源'
}
function modeName(mode) {
  return { normal: '普通签到', image: '图片签到' }[mode] || mode || '普通签到'
}
function formatTime(value) {
  return value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '-'
}
function filterPayload() {
  return Object.fromEntries(Object.entries(filters).filter(([, value]) => value !== null && value !== ''))
}
async function loadRuns() {
  loading.value = true
  try {
    const payload = { ...filterPayload(), limit: 200 }
    if (ownerUserId.value) payload.owner_user_id = ownerUserId.value
    const response = await listXxqdRunsApi(payload)
    runs.value = response.data?.items || []
    total.value = response.data?.total || 0
    lastLoadedAt.value = new Date().toLocaleString('zh-CN', { hour12: false })
  } catch (error) {
    ElMessage.error(error.message || '加载运行记录失败')
  } finally {
    loading.value = false
  }
}
function resetFilters() {
  Object.assign(filters, { account_id: null, task_id: null, source: '', status: '' })
  loadRuns()
}
function openDetail(run) {
  currentRun.value = run
  detailVisible.value = true
}

onMounted(async () => {
  await refreshState()
  await loadRuns()
})
watch(ownerUserId, loadRuns)
</script>

<style scoped>
.xxqd-runs-page{display:grid;gap:18px}.run-panel{border:1px solid rgb(191 219 254 / 58%);border-radius:22px;background:rgb(255 255 255 / 88%);box-shadow:0 18px 42px rgb(15 23 42 / 7%)}.panel-head{display:flex;align-items:center;justify-content:space-between;gap:12px}.panel-head strong,.panel-head small{display:block}.panel-head small{margin-top:4px;color:#64748b;font-size:11px}.filters{display:grid;grid-template-columns:repeat(4,minmax(120px,1fr)) auto auto;gap:10px}.filters .el-button+.el-button{margin-left:0}.run-summary{display:flex;justify-content:space-between;margin:14px 2px 10px;color:#64748b;font-size:12px}.run-list{display:grid;gap:10px;min-height:220px}.run-row{display:flex;align-items:center;gap:13px;padding:15px;border:1px solid #e2e8f0;border-radius:17px;background:linear-gradient(145deg,#fff,#f8fafc);cursor:pointer;transition:.18s ease}.run-row:hover{border-color:#93c5fd;background:#f8fbff;transform:translateY(-1px)}.run-mark{display:grid;width:44px;height:44px;flex:none;place-items:center;color:#64748b;border-radius:14px;background:#e2e8f0;font-size:21px}.run-mark.success,.run-mark.already_signed{color:#059669;background:#d1fae5}.run-mark.waiting_parameter,.run-mark.unknown_result,.run-mark.blocked{color:#d97706;background:#fef3c7}.run-mark.failed{color:#dc2626;background:#fee2e2}.run-main{min-width:0;flex:1}.run-main>div{display:flex;align-items:center;gap:8px}.run-main>div strong{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.run-account{color:#2563eb;font-size:12px;font-weight:600}.run-main p{margin:6px 0;color:#475569;font-size:13px;line-height:1.5}.run-main small{color:#64748b;font-size:11px}.run-arrow{flex:none;color:#94a3b8}.run-detail{display:grid;gap:12px}.detail-row{display:grid;grid-template-columns:90px minmax(0,1fr);align-items:start;gap:10px;padding:12px 14px;border:1px solid #e2e8f0;border-radius:13px;background:#f8fafc}.detail-row>span{color:#64748b;font-size:12px}.detail-row strong,.detail-row p{margin:0;overflow-wrap:anywhere;color:#172033;line-height:1.6}.detail-images{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px}.detail-images :deep(.el-image){width:100%;aspect-ratio:1;border-radius:10px}@media(max-width:1100px){.filters{grid-template-columns:repeat(3,1fr)}}@media(max-width:650px){.panel-head{align-items:stretch;flex-direction:column}.filters{grid-template-columns:1fr 1fr}.filters .el-button{width:100%;margin:0}.run-row{align-items:flex-start;padding:12px}.run-mark{width:38px;height:38px}.run-main>div{flex-wrap:wrap}.run-arrow{display:none}.detail-images{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:420px){.filters{grid-template-columns:1fr}.run-summary{flex-direction:column;gap:4px}}
</style>
