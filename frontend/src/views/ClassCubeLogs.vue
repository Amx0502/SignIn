<template>
  <div class="page-container">
    <el-card shadow="hover">
      <template #header>
        <div class="card-header">
          <span>魔方日志</span>
          <el-space>
            <el-select v-model="filterLevel" size="small" style="width:110px">
              <el-option label="全部级别" value="ALL" />
              <el-option label="INFO" value="INFO" />
              <el-option label="WARNING" value="WARNING" />
              <el-option label="ERROR" value="ERROR" />
            </el-select>
            <el-tag size="small" type="info">共 {{ filteredLogs.length }} 条</el-tag>
            <el-button :icon="Refresh" size="small" :loading="loading" @click="refreshLogs">刷新</el-button>
            <el-button :icon="Bottom" size="small" @click="scrollToBottom">滚动到底部</el-button>
          </el-space>
        </div>
      </template>
      <div ref="logsRef" class="logs-container">
        <div v-if="!filteredLogs.length" class="logs-empty">暂无班级魔方日志</div>
        <div
          v-for="(item, index) in filteredLogs"
          :key="index"
          class="log-line"
          :class="`log-level-${item.level.toLowerCase()}`"
        >
          <span class="log-time">{{ item.time }}</span>
          <el-tag class="log-level" :type="levelType(item.level)" size="small" effect="plain">{{ item.level }}</el-tag>
          <span class="log-message">{{ item.message }}</span>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { Bottom, Refresh } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import classCubeApi from '../api/classCube.js'

const logs = ref([])
const logsRef = ref(null)
const filterLevel = ref('ALL')
const loading = ref(false)
const logPattern = /^(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}(?:,\d{3})?)\s+\[([A-Z]+)\]\s+(.*)$/

const parsedLogs = computed(() => logs.value.map(line => {
  const match = String(line).match(logPattern)
  return match
    ? { time: match[1], level: match[2], message: match[3] }
    : { time: '', level: 'INFO', message: String(line) }
}))
const filteredLogs = computed(() => filterLevel.value === 'ALL'
  ? parsedLogs.value
  : parsedLogs.value.filter(item => item.level === filterLevel.value))

async function refreshLogs() {
  loading.value = true
  try {
    const response = await classCubeApi.listLogs(500)
    logs.value = Array.isArray(response?.data) ? response.data : []
  } catch (error) {
    ElMessage.error(error.message || '加载魔方日志失败')
  } finally {
    loading.value = false
  }
}
function levelType(level) {
  return { ERROR: 'danger', WARNING: 'warning', INFO: 'info', DEBUG: 'success' }[level] || 'info'
}
function scrollToBottom() {
  if (logsRef.value) logsRef.value.scrollTop = logsRef.value.scrollHeight
}
onMounted(refreshLogs)
</script>

<style scoped>
.card-header{display:flex;align-items:center;justify-content:space-between;gap:12px}.logs-container{max-height:70vh;overflow-y:auto;font-family:ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,monospace;font-size:13px;line-height:1.7;padding:12px;background:#0f172a;border-radius:8px;color:#e2e8f0}.logs-empty{text-align:center;color:#64748b;padding:40px 0}.log-line{display:flex;align-items:flex-start;gap:10px;padding:4px 0;border-bottom:1px solid rgb(148 163 184 / 8%);word-break:break-all}.log-time{flex-shrink:0;width:170px;color:#94a3b8;white-space:nowrap}.log-level{flex-shrink:0;width:70px;text-align:center;font-weight:600}.log-message{flex:1;color:#e2e8f0}.log-level-error .log-message{color:#fca5a5}.log-level-warning .log-message{color:#fcd34d}@media(max-width:768px){.logs-container{font-size:12px;max-height:50vh}.log-line{flex-direction:column;gap:4px}.log-time{width:auto;white-space:normal;font-size:11px}.log-level{width:auto}.card-header{align-items:flex-start;flex-direction:column}.card-header .el-space{flex-wrap:wrap}}@media(max-width:480px){.logs-container{font-size:11px}.card-header .el-select{width:100%!important}}
</style>
