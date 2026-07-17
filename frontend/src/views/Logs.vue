<template>
  <div class="page-container">
    <el-card shadow="hover">
      <template #header>
        <div class="card-header">
          <span>运行日志</span>
          <el-space>
            <el-select v-model="filterLevel" size="small" style="width: 110px">
              <el-option label="全部级别" value="ALL" />
              <el-option label="INFO" value="INFO" />
              <el-option label="WARNING" value="WARNING" />
              <el-option label="ERROR" value="ERROR" />
            </el-select>
            <el-tag size="small" type="info">共 {{ filteredLogs.length }} 条</el-tag>
            <el-button :icon="Refresh" size="small" @click="refreshLogs">刷新</el-button>
            <el-button :icon="Bottom" size="small" @click="scrollToBottom">滚动到底部</el-button>
          </el-space>
        </div>
      </template>
      <div class="logs-container" ref="logsRef">
        <div v-if="!filteredLogs.length" class="logs-empty">暂无日志</div>
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
  </div>
</template>

<script setup>
import { ref, computed, watch, nextTick } from 'vue'
import { Refresh, Bottom } from '@element-plus/icons-vue'
import { useAppState } from '../composables/useAppState'

const { logs, refreshLogs } = useAppState()
const logsRef = ref(null)
const filterLevel = ref('ALL')

const logPattern = /^(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}(?:,\d{3})?)\s+\[([A-Z]+)\]\s+(.*)$/

const parsedLogs = computed(() => {
  return (logs.value || []).map(line => {
    const match = String(line).match(logPattern)
    if (match) {
      return { time: match[1], level: match[2], message: match[3] }
    }
    return { time: '', level: 'INFO', message: line }
  })
})

const filteredLogs = computed(() => {
  if (filterLevel.value === 'ALL') return parsedLogs.value
  return parsedLogs.value.filter(item => item.level === filterLevel.value)
})

function levelType(level) {
  switch (level) {
    case 'ERROR': return 'danger'
    case 'WARNING': return 'warning'
    case 'INFO': return 'info'
    case 'DEBUG': return 'success'
    default: return 'info'
  }
}

function scrollToBottom() {
  if (logsRef.value) {
    logsRef.value.scrollTop = logsRef.value.scrollHeight
  }
}

watch(logs, () => {
  nextTick(scrollToBottom)
}, { deep: true })
</script>

<style scoped>
.logs-container {
  max-height: 70vh;
  overflow-y: auto;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 13px;
  line-height: 1.7;
  padding: 12px;
  background: #0f172a;
  border-radius: 8px;
  color: #e2e8f0;
}
.logs-empty {
  text-align: center;
  color: #64748b;
  padding: 40px 0;
}
.log-line {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 4px 0;
  border-bottom: 1px solid rgba(148, 163, 184, 0.08);
  word-break: break-all;
}
.log-time {
  flex-shrink: 0;
  width: 170px;
  color: #94a3b8;
  white-space: nowrap;
}
.log-level {
  flex-shrink: 0;
  width: 70px;
  text-align: center;
  font-weight: 600;
}
.log-message {
  flex: 1;
  color: #e2e8f0;
}
.log-level-error .log-message {
  color: #fca5a5;
}
.log-level-warning .log-message {
  color: #fcd34d;
}
</style>
