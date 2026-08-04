<template>
  <el-card shadow="hover">
    <template #header>
      <div class="card-header">
        <span>{{ title }}</span>
        <el-space>
          <el-select v-model="filterLevel" size="small" style="width: 110px">
            <el-option label="全部级别" value="ALL" />
            <el-option label="INFO" value="INFO" />
            <el-option label="WARNING" value="WARNING" />
            <el-option label="ERROR" value="ERROR" />
          </el-select>
          <el-tag size="small" type="info">共 {{ filteredLogs.length }} 条</el-tag>
          <el-button :icon="Refresh" size="small" :loading="loading" @click="emit('refresh')">刷新</el-button>
          <el-button :icon="Bottom" size="small" @click="scrollToBottom">滚动到底部</el-button>
        </el-space>
      </div>
    </template>
    <div ref="logsRef" class="logs-container">
      <div v-if="!filteredLogs.length" class="logs-empty">{{ emptyText }}</div>
      <div
        v-for="(item, index) in filteredLogs"
        :key="index"
        class="log-line"
        :class="`log-level-${item.level.toLowerCase()}`"
      >
        <span class="log-time">{{ item.time }}</span>
        <el-tag class="log-level" :type="levelType(item.level)" size="small" effect="plain">
          {{ item.level }}
        </el-tag>
        <span class="log-message">{{ item.message }}</span>
      </div>
    </div>
  </el-card>
</template>

<script setup>
import { computed, ref } from 'vue'
import { Bottom, Refresh } from '@element-plus/icons-vue'
import { filterLogEntries } from '../utils/logConsole.js'

const props = defineProps({
  title: { type: String, required: true },
  emptyText: { type: String, default: '暂无日志' },
  logs: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
})
const emit = defineEmits(['refresh'])
const logsRef = ref(null)
const filterLevel = ref('ALL')
const filteredLogs = computed(() => filterLogEntries(props.logs, filterLevel.value))

function levelType(level) {
  return { ERROR: 'danger', WARNING: 'warning', INFO: 'info', DEBUG: 'success' }[level] || 'info'
}
function scrollToBottom() {
  if (logsRef.value) logsRef.value.scrollTop = logsRef.value.scrollHeight
}
</script>

<style scoped>
.card-header { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.logs-container { max-height: 70vh; overflow-y: auto; padding: 12px; color: #e2e8f0; border-radius: 8px; background: #0f172a; font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; font-size: 13px; line-height: 1.7; }
.logs-empty { padding: 40px 0; color: #64748b; text-align: center; }
.log-line { display: flex; align-items: flex-start; gap: 10px; padding: 4px 0; border-bottom: 1px solid rgb(148 163 184 / 8%); word-break: break-all; }
.log-time { width: 170px; flex-shrink: 0; color: #94a3b8; white-space: nowrap; }
.log-level { width: 70px; flex-shrink: 0; font-weight: 600; text-align: center; }
.log-message { flex: 1; color: #e2e8f0; }
.log-level-error .log-message { color: #fca5a5; }
.log-level-warning .log-message { color: #fcd34d; }
@media (max-width: 768px) {
  .logs-container { max-height: 50vh; font-size: 12px; }
  .log-line { flex-direction: column; gap: 4px; }
  .log-time { width: auto; font-size: 11px; white-space: normal; }
  .log-level { width: auto; }
  .card-header { align-items: flex-start; flex-direction: column; gap: 8px; }
  .card-header .el-space { flex-wrap: wrap; }
}
@media (max-width: 480px) {
  .logs-container { font-size: 11px; }
  .card-header .el-select { width: 100% !important; }
}
</style>
