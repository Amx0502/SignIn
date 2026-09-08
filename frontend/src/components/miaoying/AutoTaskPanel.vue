<template>
  <section class="task-panel">
    <header class="task-panel-head">
      <div class="title-row">
        <div class="panel-title">
          <h2>自动签到任务</h2>
          <p>到达设定时间后，系统会自动提交秒应签到项目</p>
        </div>
        <div class="primary-actions">
          <el-button
            type="danger"
            plain
            :icon="Delete"
            :disabled="!selectedIds.length"
            :loading="batchLoading"
            @click="emit('batch-delete', selectedIds)"
          >批量删除({{ selectedIds.length }})</el-button>
          <el-button type="primary" :icon="Plus" @click="emit('create')">新增任务</el-button>
        </div>
      </div>

      <div class="filter-row">
        <el-input
          v-model="keyword"
          clearable
          placeholder="搜索任务、账号或签到项目"
          :prefix-icon="Search"
        />
        <el-select v-model="statusFilter" aria-label="筛选任务状态">
          <el-option label="全部状态" value="all" />
          <el-option label="仅看已启用" value="enabled" />
          <el-option label="仅看已停用" value="disabled" />
        </el-select>
      </div>
    </header>

    <div v-if="filteredTasks.length" class="task-list">
      <article
        v-for="row in filteredTasks"
        :key="row.id"
        class="task-card"
        :class="{
          'task-card--selected': selectedIds.includes(row.id),
          'task-card--disabled': !row.enabled,
        }"
      >
        <header class="task-card-head">
          <el-checkbox
            :model-value="selectedIds.includes(row.id)"
            :aria-label="`选择任务 ${row.name}`"
            @change="value => selectTask(row.id, value)"
          />
          <div class="task-identity">
            <strong :title="row.name">{{ row.name }}</strong>
            <p>
              <span :title="accountName(row.account_id)">{{ accountName(row.account_id) }}</span>
              <i aria-hidden="true">·</i>
              <span :title="formName(row.form_id)">{{ formName(row.form_id) }}</span>
            </p>
          </div>
          <div class="task-state">
            <span>{{ row.enabled ? '已启用' : '已停用' }}</span>
            <el-switch
              :model-value="row.enabled"
              :aria-label="`${row.name}启用状态`"
              @change="value => emit('toggle', row, value)"
            />
          </div>
        </header>

        <div class="task-details">
          <section class="task-detail task-detail--schedule">
            <span class="detail-label">执行计划</span>
            <div class="time-list">
              <el-tag
                v-for="time in row.schedule_times || []"
                :key="time"
                size="small"
                effect="plain"
              >{{ time }}</el-tag>
              <span v-if="!(row.schedule_times || []).length" class="muted">未设置时间</span>
            </div>
            <small>{{ schedulePlanSummary(row) }}</small>
          </section>

          <section class="task-detail">
            <span class="detail-label">签到预设</span>
            <div class="task-tags">
              <el-tag v-if="row.latitude != null && row.longitude != null" size="small" type="primary">位置</el-tag>
              <el-tag v-if="row.answers?.__identity" size="small" type="success">名单身份</el-tag>
              <el-tag v-if="(row.answer_schema || []).length" size="small" type="info">填写项 {{ row.answer_schema.length }}</el-tag>
              <span v-if="!hasParameters(row)" class="muted">无需预设参数</span>
            </div>
          </section>

          <section class="task-detail task-detail--updated">
            <span class="detail-label">最近更新</span>
            <strong>{{ format(row.updated_at) }}</strong>
          </section>
        </div>

        <footer class="task-actions">
          <el-button type="primary" plain @click="emit('edit', row)">编辑</el-button>
          <el-button
            type="success"
            plain
            :loading="runningTaskId === row.id"
            :disabled="runningTaskId !== null && runningTaskId !== row.id"
            @click="emit('run', row)"
          >立即执行</el-button>
          <el-dropdown trigger="click" @command="command => handleCommand(command, row)">
            <el-button :icon="MoreFilled">更多</el-button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="delete">删除任务</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </footer>
      </article>
    </div>

    <div v-else class="task-empty">
      <el-empty :description="tasks.length ? '没有符合筛选条件的任务' : '还没有自动任务'" :image-size="82" />
      <p>{{ tasks.length ? '尝试清除搜索词或切换状态筛选。' : '新增任务后，系统会按照设定的时间自动执行签到。' }}</p>
      <el-button v-if="!tasks.length" type="primary" :icon="Plus" @click="emit('create')">新增第一个任务</el-button>
      <el-button v-else @click="resetFilters">清除筛选</el-button>
    </div>
  </section>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { Delete, MoreFilled, Plus, Search } from '@element-plus/icons-vue'

const props = defineProps({
  tasks: { type: Array, default: () => [] },
  accounts: { type: Array, default: () => [] },
  forms: { type: Array, default: () => [] },
  runningTaskId: { type: Number, default: null },
  batchLoading: { type: Boolean, default: false },
})

const emit = defineEmits(['create', 'edit', 'run', 'toggle', 'remove', 'batch-delete'])
const keyword = ref('')
const statusFilter = ref('all')
const selectedIds = ref([])

const accountName = id => {
  const account = props.accounts.find(item => item.id === id)
  return account?.remark || account?.nickname || `账号 ${id}`
}
const formName = id => props.forms.find(item => item.id === id)?.title || `签到项目 ${id}`
const format = value => value
  ? new Date(value).toLocaleString('zh-CN', { hour12: false })
  : '尚未更新'
const hasParameters = row => (
  (row.latitude != null && row.longitude != null)
  || row.answers?.__identity
  || (row.answer_schema || []).length
)

const filteredTasks = computed(() => {
  const search = keyword.value.trim().toLowerCase()
  return props.tasks.filter(row => {
    if (statusFilter.value === 'enabled' && !row.enabled) return false
    if (statusFilter.value === 'disabled' && row.enabled) return false
    if (!search) return true
    return `${row.name} ${accountName(row.account_id)} ${formName(row.form_id)}`
      .toLowerCase()
      .includes(search)
  })
})

function schedulePlanSummary(plan) {
  const excluded = (plan.skip_dates || []).length
  if ((plan.date_mode || 'daily') === 'daily') {
    return [
      '每天执行',
      plan.skip_weekends ? '周末跳过' : '',
      excluded ? `排除 ${excluded} 天` : '',
    ].filter(Boolean).join(' · ')
  }
  return [
    `指定 ${(plan.run_dates || []).length} 天`,
    plan.auto_disable_after_finish ? '结束后关闭' : '',
  ].filter(Boolean).join(' · ')
}

function selectTask(id, selected) {
  selectedIds.value = selected
    ? [...new Set([...selectedIds.value, id])]
    : selectedIds.value.filter(value => value !== id)
}

function handleCommand(command, row) {
  if (command === 'delete') emit('remove', row)
}

function resetFilters() {
  keyword.value = ''
  statusFilter.value = 'all'
}

watch(() => props.tasks, rows => {
  const validIds = new Set(rows.map(row => row.id))
  selectedIds.value = selectedIds.value.filter(id => validIds.has(id))
})
</script>

<style scoped>
.task-panel{min-width:0;overflow:hidden;border:1px solid #dbeafe;border-radius:20px;background:#ffffffeb;box-shadow:0 14px 34px #0f172a0a}
.task-panel-head{display:grid;gap:14px;padding:19px 20px 16px;border-bottom:1px solid #e7eef8}
.title-row{display:flex;align-items:flex-start;justify-content:space-between;gap:18px}
.panel-title h2{margin:0;color:#172033;font-size:18px;line-height:1.35}
.panel-title p{margin:4px 0 0;color:#64748b;font-size:12px;line-height:1.5}
.primary-actions,.filter-row{display:flex;align-items:center;gap:10px}
.primary-actions{flex:none}
.primary-actions .el-button{margin:0}
.filter-row .el-input{min-width:0;flex:1}
.filter-row .el-select{width:150px;flex:none}
.task-list{display:grid;grid-template-columns:minmax(0,1fr);gap:12px;padding:16px 20px 20px}
.task-card{overflow:hidden;border:1px solid #dbe6f2;border-radius:16px;background:#fff;box-shadow:0 7px 20px rgb(15 23 42 / 4%);transition:border-color .18s ease,box-shadow .18s ease}
.task-card:hover{border-color:#bfdbfe;box-shadow:0 10px 24px rgb(37 99 235 / 8%)}
.task-card--selected{border-color:#60a5fa;box-shadow:0 0 0 2px rgb(59 130 246 / 12%),0 10px 24px rgb(37 99 235 / 8%)}
.task-card--disabled{background:linear-gradient(145deg,#fff,#f8fafc)}
.task-card-head{display:grid;grid-template-columns:auto minmax(0,1fr) auto;align-items:center;gap:11px;padding:12px 14px;border-bottom:1px solid #edf2f7}
.task-card-head :deep(.el-checkbox){height:auto}
.task-identity{display:grid;min-width:0;gap:4px}
.task-identity strong{overflow:hidden;color:#172033;font-size:15px;line-height:1.35;text-overflow:ellipsis;white-space:nowrap}
.task-identity p{display:flex;min-width:0;align-items:center;gap:6px;margin:0;color:#64748b;font-size:11px}
.task-identity p span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.task-identity p span:last-child{flex:1}
.task-identity i{color:#cbd5e1;font-style:normal}
.task-state{display:flex;align-items:center;gap:9px;color:#64748b;font-size:11px}
.task-details{display:grid;grid-template-columns:1.2fr 1fr .9fr;padding:13px 2px}
.task-detail{display:grid;align-content:start;min-width:0;gap:5px;padding:0 13px;border-left:1px solid #edf2f7}
.task-detail:first-child{border-left:0}
.detail-label{color:#94a3b8;font-size:10px;font-weight:600}
.task-detail>strong{overflow:hidden;color:#334155;font-size:12px;font-variant-numeric:tabular-nums;text-overflow:ellipsis;white-space:nowrap}
.task-detail>small{color:#2563eb;font-size:11px}
.time-list,.task-tags{display:flex;align-items:center;flex-wrap:wrap;gap:5px;min-height:24px}
.muted{color:#94a3b8;font-size:11px}
.task-actions{display:flex;align-items:center;justify-content:flex-end;gap:8px;padding:8px 12px;background:#f8fafc;border-top:1px solid #edf2f7}
.task-actions .el-button+.el-button{margin-left:0}
.task-empty{display:grid;place-items:center;padding:30px 20px 38px;text-align:center}
.task-empty :deep(.el-empty){padding-bottom:0}
.task-empty p{margin:-6px 0 15px;color:#64748b;font-size:12px}
@media(min-width:1500px){.task-list{grid-template-columns:repeat(2,minmax(0,1fr))}.task-details{grid-template-columns:repeat(2,minmax(0,1fr));row-gap:13px}.task-detail--updated{grid-column:1/-1;padding-top:11px;border-top:1px solid #edf2f7;border-left:0}}
@media(max-width:720px){.title-row{display:grid}.primary-actions{display:grid;grid-template-columns:1fr 1fr;width:100%}.primary-actions .el-button{width:100%}.filter-row{display:grid;grid-template-columns:minmax(0,1fr) 132px}.task-details{grid-template-columns:repeat(2,minmax(0,1fr));row-gap:13px}.task-detail--updated{grid-column:1/-1;padding-top:11px;border-top:1px solid #edf2f7;border-left:0}}
@media(max-width:520px){.task-panel-head{padding:15px 14px}.filter-row{grid-template-columns:1fr}.filter-row .el-select{width:100%}.task-list{padding:14px}.task-card-head{grid-template-columns:auto minmax(0,1fr)}.task-state{grid-column:2;justify-content:space-between}.task-details{grid-template-columns:1fr;padding:2px 14px}.task-detail,.task-detail--updated{grid-column:auto;padding:12px 0;border-top:1px solid #edf2f7;border-left:0}.task-detail:first-child{border-top:0}.task-actions{display:grid;grid-template-columns:1fr 1fr auto}.task-actions .el-button{width:100%}}
</style>
