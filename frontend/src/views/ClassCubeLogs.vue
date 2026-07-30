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
          <div class="log-meta">
            <span class="log-time">{{ item.time }}</span>
            <el-tag class="log-level" :type="levelType(item.level)" size="small" effect="plain">{{ levelName(item.level) }}</el-tag>
            <el-tag class="log-event" :type="eventType(item.message)" size="small" effect="dark">{{ eventName(item.message) }}</el-tag>
          </div>
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
function levelName(level) {
  return { ERROR: '错误', WARNING: '警告', INFO: '信息', DEBUG: '调试' }[level] || level
}
function eventName(message) {
  if (message.startsWith('开始')) return '任务开始'
  if (message.startsWith('签到项扫描')) return '签到扫描'
  if (message.startsWith('签到项「')) return '签到结果'
  if (message.includes('执行完成')) return '执行汇总'
  if (message.includes('企业微信')) return '企业微信'
  return '系统事件'
}
function eventType(message) {
  const event = eventName(message)
  return {
    任务开始: 'primary',
    签到扫描: 'info',
    签到结果: 'success',
    执行汇总: 'warning',
    企业微信: 'primary',
  }[event] || 'info'
}
function scrollToBottom() {
  if (logsRef.value) logsRef.value.scrollTop = logsRef.value.scrollHeight
}
onMounted(refreshLogs)
</script>

<style scoped>
.card-header{display:flex;align-items:center;justify-content:space-between;gap:12px}.logs-container{display:grid;gap:9px;max-height:70vh;overflow-y:auto;padding:14px;background:linear-gradient(145deg,#0b1220,#101b31);border:1px solid rgb(96 165 250 / 18%);border-radius:16px;color:#e2e8f0}.logs-empty{text-align:center;color:#64748b;padding:40px 0}.log-line{display:grid;grid-template-columns:285px minmax(0,1fr);align-items:start;gap:14px;padding:11px 13px;border:1px solid rgb(148 163 184 / 11%);border-radius:11px;background:rgb(15 23 42 / 78%);box-shadow:0 6px 18px rgb(0 0 0 / 8%);word-break:break-word}.log-meta{display:flex;align-items:center;gap:7px;min-width:0}.log-time{color:#93c5fd;white-space:nowrap;font:11px/1.5 ui-monospace,SFMono-Regular,Menlo,monospace}.log-level,.log-event{flex-shrink:0}.log-message{color:#e5edf9;font-size:13px;line-height:1.65}.log-level-error{border-color:rgb(248 113 113 / 24%)}.log-level-error .log-message{color:#fecaca}.log-level-warning .log-message{color:#fde68a}@media(max-width:900px){.log-line{grid-template-columns:1fr;gap:7px}}@media(max-width:768px){.logs-container{max-height:55vh;padding:10px}.log-line{padding:10px}.log-meta{flex-wrap:wrap}.card-header{align-items:flex-start;flex-direction:column}.card-header .el-space{flex-wrap:wrap}}@media(max-width:480px){.log-message{font-size:12px}.card-header .el-select{width:100%!important}}
</style>
