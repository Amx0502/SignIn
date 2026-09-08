<template>
  <section class="task-panel">
    <header class="task-panel-head">
      <div><h2>自动签到任务</h2><p>集中创建、编辑和执行秒应自动签到任务</p></div>
      <div class="task-panel-actions">
        <el-input v-model="keyword" clearable placeholder="搜索任务、账号或项目" :prefix-icon="Search" />
        <el-button type="primary" :icon="Plus" @click="emit('create')">新增任务</el-button>
      </div>
    </header>

    <div v-if="selectedIds.length" class="batch-toolbar">
      <strong>已选择 {{ selectedIds.length }} 项</strong>
      <el-button type="success" plain :loading="batchLoading" @click="emit('batch-state', selectedIds, true)">批量启用</el-button>
      <el-button type="warning" plain :loading="batchLoading" @click="emit('batch-state', selectedIds, false)">批量停用</el-button>
      <el-button type="danger" plain :loading="batchLoading" @click="emit('batch-delete', selectedIds)">批量删除</el-button>
      <el-button text @click="selectedIds = []">取消选择</el-button>
    </div>

    <el-table class="task-table" :data="filteredTasks" row-key="id" stripe @selection-change="rows => selectedIds = rows.map(row => row.id)">
      <el-table-column type="selection" width="46" reserve-selection />
      <el-table-column label="任务" min-width="180"><template #default="{row}"><div class="task-cell"><strong>{{ row.name }}</strong><small>{{ (row.schedule_times || []).join('、') || '未设置时间' }}</small><small>{{ schedulePlanSummary(row) }}</small></div></template></el-table-column>
      <el-table-column label="账号 / 签到项目" min-width="190"><template #default="{row}"><div class="task-cell"><span>{{ accountName(row.account_id) }}</span><small>{{ formName(row.form_id) }}</small></div></template></el-table-column>
      <el-table-column label="预设参数" min-width="170"><template #default="{row}"><el-space wrap><el-tag v-if="row.latitude != null && row.longitude != null" size="small" type="primary">位置</el-tag><el-tag v-if="row.answers?.__identity" size="small" type="success">名单身份</el-tag><el-tag v-if="(row.answer_schema || []).length" size="small" type="info">填写项 {{ row.answer_schema.length }}</el-tag><span v-if="!hasParameters(row)" class="muted">无</span></el-space></template></el-table-column>
      <el-table-column label="状态" width="92"><template #default="{row}"><el-switch :model-value="row.enabled" inline-prompt active-text="启" inactive-text="停" @change="value => emit('toggle', row, value)" /></template></el-table-column>
      <el-table-column label="最近更新" min-width="150"><template #default="{row}"><span class="muted">{{ format(row.updated_at) }}</span></template></el-table-column>
      <el-table-column label="操作" width="190" fixed="right"><template #default="{row}"><el-button link type="primary" @click="emit('edit', row)">编辑</el-button><el-button link type="success" :loading="runningTaskId === row.id" :disabled="runningTaskId !== null && runningTaskId !== row.id" @click="emit('run', row)">立即执行</el-button><el-button link type="danger" @click="emit('remove', row)">删除</el-button></template></el-table-column>
      <template #empty><TaskEmpty @create="emit('create')" /></template>
    </el-table>

    <div class="task-card-list">
      <article v-for="row in filteredTasks" :key="row.id" class="task-card">
        <el-checkbox :model-value="selectedIds.includes(row.id)" @change="value => selectCard(row.id, value)" />
        <div class="task-card-main">
          <div class="task-card-title"><strong>{{ row.name }}</strong><el-tag :type="row.enabled ? 'success' : 'info'" size="small">{{ row.enabled ? '已启用' : '已停用' }}</el-tag></div>
          <p>{{ accountName(row.account_id) }} · {{ formName(row.form_id) }}</p>
          <small>{{ (row.schedule_times || []).join('、') || '未设置时间' }} · {{ schedulePlanSummary(row) }}</small>
          <div class="task-tags"><el-tag v-if="row.latitude != null" size="small" type="primary">位置</el-tag><el-tag v-if="row.answers?.__identity" size="small" type="success">名单身份</el-tag><el-tag v-if="(row.answer_schema || []).length" size="small" type="info">填写项 {{ row.answer_schema.length }}</el-tag></div>
          <div class="task-card-actions"><el-button type="primary" plain @click="emit('edit', row)">编辑</el-button><el-button type="success" plain :loading="runningTaskId === row.id" :disabled="runningTaskId !== null && runningTaskId !== row.id" @click="emit('run', row)">立即执行</el-button><el-dropdown trigger="click" @command="command => handleCommand(command, row)"><el-button>更多</el-button><template #dropdown><el-dropdown-menu><el-dropdown-item :command="row.enabled ? 'disable' : 'enable'">{{ row.enabled ? '停用任务' : '启用任务' }}</el-dropdown-item><el-dropdown-item command="delete" divided>删除任务</el-dropdown-item></el-dropdown-menu></template></el-dropdown></div>
        </div>
      </article>
      <TaskEmpty v-if="!filteredTasks.length" @create="emit('create')" />
    </div>
  </section>
</template>

<script setup>
import { computed, defineComponent, h, ref, watch } from 'vue'
import { ElButton, ElEmpty } from 'element-plus'
import { Plus, Search } from '@element-plus/icons-vue'

const props = defineProps({
  tasks: { type: Array, default: () => [] },
  accounts: { type: Array, default: () => [] },
  forms: { type: Array, default: () => [] },
  runningTaskId: { type: Number, default: null },
  batchLoading: { type: Boolean, default: false },
})
const emit = defineEmits(['create', 'edit', 'run', 'toggle', 'remove', 'batch-state', 'batch-delete'])
const keyword = ref('')
const selectedIds = ref([])
const TaskEmpty = defineComponent({
  emits: ['create'],
  setup(_, { emit: childEmit }) {
    return () => h('div', { class: 'task-empty' }, [
      h(ElEmpty, { description: '还没有自动任务', imageSize: 84 }),
      h('p', '创建后，系统会在设定时间自动获取项目并执行签到。'),
      h(ElButton, { type: 'primary', onClick: () => childEmit('create') }, () => '新增第一个任务'),
    ])
  },
})

const accountName = id => props.accounts.find(item => item.id === id)?.remark || props.accounts.find(item => item.id === id)?.nickname || `账号 ${id}`
const formName = id => props.forms.find(item => item.id === id)?.title || `签到项目 ${id}`
const filteredTasks = computed(() => {
  const value = keyword.value.trim().toLowerCase()
  if (!value) return props.tasks
  return props.tasks.filter(row => `${row.name}${accountName(row.account_id)}${formName(row.form_id)}`.toLowerCase().includes(value))
})
const format = value => value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '—'
const hasParameters = row => row.latitude != null || row.answers?.__identity || (row.answer_schema || []).length
function schedulePlanSummary(plan) {
  const excluded = (plan.skip_dates || []).length
  if ((plan.date_mode || 'daily') === 'daily') return ['每天执行', plan.skip_weekends ? '周末跳过' : '', excluded ? `排除 ${excluded} 天` : ''].filter(Boolean).join(' · ')
  return [`指定 ${(plan.run_dates || []).length} 天`, plan.auto_disable_after_finish ? '结束后关闭' : ''].filter(Boolean).join(' · ')
}
function selectCard(id, selected) {
  selectedIds.value = selected ? [...new Set([...selectedIds.value, id])] : selectedIds.value.filter(value => value !== id)
}
function handleCommand(command, row) {
  if (command === 'delete') emit('remove', row)
  else if (command === 'enable') emit('toggle', row, true)
  else if (command === 'disable') emit('toggle', row, false)
}
watch(() => props.tasks, rows => {
  const valid = new Set(rows.map(row => row.id))
  selectedIds.value = selectedIds.value.filter(id => valid.has(id))
})
</script>

<style scoped>
.task-panel{min-width:0;overflow:hidden;border:1px solid #dbeafe;border-radius:20px;background:#ffffffde;box-shadow:0 14px 34px #0f172a0a}.task-panel-head{display:flex;align-items:flex-start;justify-content:space-between;gap:14px;padding:20px 20px 0}.task-panel h2{margin:0;color:#172033;font-size:18px}.task-panel p{margin:4px 0 0;color:#64748b;font-size:13px}.task-panel-actions{display:flex;align-items:center;justify-content:flex-end;gap:10px}.task-panel-actions .el-input{width:280px}.task-panel-actions .el-button{margin:0}.batch-toolbar{display:flex;align-items:center;gap:8px;margin:16px 20px 0;padding:10px 12px;border:1px solid #bfdbfe;border-radius:13px;background:#eff6ff}.batch-toolbar strong{margin-right:auto;color:#1e3a8a;font-size:13px}.batch-toolbar .el-button+.el-button{margin-left:0}.task-table{margin:0 20px 20px;width:calc(100% - 40px)}.task-cell{display:grid;gap:4px}.task-cell strong{color:#172033}.task-cell small{color:#64748b;font-size:11px}.muted{color:#94a3b8;font-size:12px}.task-card-list{display:none;padding:16px 20px 20px}.task-card{display:flex;align-items:flex-start;gap:12px;padding:15px;border:1px solid #dbeafe;border-radius:16px;background:linear-gradient(145deg,#fff,#f8fbff)}.task-card-main{display:grid;min-width:0;flex:1;gap:7px}.task-card-title{display:flex;align-items:center;justify-content:space-between;gap:10px}.task-card-title strong{overflow:hidden;color:#172033;text-overflow:ellipsis;white-space:nowrap}.task-card p{margin:0;color:#475569}.task-card small{color:#64748b}.task-tags,.task-card-actions{display:flex;align-items:center;gap:8px;flex-wrap:wrap}.task-card-actions{margin-top:4px}.task-card-actions .el-button+.el-button{margin-left:0}.task-empty{display:grid;place-items:center;padding:28px;text-align:center}.task-empty :deep(.el-empty){padding:0}.task-empty p{margin:-8px 0 14px;color:#64748b}@media(max-width:1450px){.task-table{display:none}.task-card-list{display:grid;gap:12px}}@media(max-width:850px){.task-panel-head{align-items:stretch;flex-direction:column}.task-panel-actions{align-items:stretch;flex-direction:column}.task-panel-actions .el-input,.task-panel-actions .el-button{width:100%}.batch-toolbar{align-items:stretch;flex-wrap:wrap}.batch-toolbar strong{width:100%}.batch-toolbar .el-button{flex:1}.task-card-actions>.el-button{flex:1}}@media(max-width:560px){.task-panel-head{padding:14px 14px 0}.task-card-list{padding:14px}.batch-toolbar{margin:14px 14px 0}.task-card-actions{display:grid;grid-template-columns:1fr 1fr}.task-card-actions>.el-dropdown{grid-column:1/-1}.task-card-actions :deep(.el-dropdown .el-button){width:100%}}
</style>
