<template>
  <el-card shadow="hover">
    <template #header>
      <div class="card-header">
        <span class="log-title">{{ title }}</span>
        <div class="log-toolbar">
          <el-select
            v-model="filterLevel"
            class="desktop-level-filter"
            size="small"
          >
            <el-option
              v-for="option in levelOptions"
              :key="option.value"
              :label="option.label"
              :value="option.value"
            />
          </el-select>
          <el-radio-group
            v-model="filterLevel"
            class="mobile-level-filter"
            size="small"
          >
            <el-radio-button
              v-for="option in levelOptions"
              :key="option.value"
              :value="option.value"
            >
              {{ option.mobileLabel }}
            </el-radio-button>
          </el-radio-group>
          <el-tag size="small" type="info"
            >共 {{ filteredLogs.length }} 条</el-tag
          >
          <div class="log-toolbar-actions">
            <el-button
              :icon="Refresh"
              size="small"
              :loading="loading"
              @click="emit('refresh')"
              >刷新</el-button
            >
            <el-button :icon="Bottom" size="small" @click="scrollToBottom"
              >到底部</el-button
            >
          </div>
        </div>
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
        <div class="log-line-meta">
          <span class="log-time">{{ item.time }}</span>
          <el-tag
            class="log-level"
            :type="levelType(item.level)"
            size="small"
            effect="plain"
          >
            {{ item.level }}
          </el-tag>
        </div>
        <pre class="log-message">{{ item.message }}</pre>
      </div>
    </div>
  </el-card>
</template>

<script setup>
import { computed, ref } from "vue";
import { Bottom, Refresh } from "@element-plus/icons-vue";
import { filterLogEntries } from "../utils/logConsole.js";

const props = defineProps({
  title: { type: String, required: true },
  emptyText: { type: String, default: "暂无日志" },
  logs: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
});
const emit = defineEmits(["refresh"]);
const logsRef = ref(null);
const filterLevel = ref("ALL");
const levelOptions = [
  { label: "全部级别", mobileLabel: "全部", value: "ALL" },
  { label: "INFO", mobileLabel: "信息", value: "INFO" },
  { label: "WARNING", mobileLabel: "警告", value: "WARNING" },
  { label: "ERROR", mobileLabel: "错误", value: "ERROR" },
];
const filteredLogs = computed(() =>
  filterLogEntries(props.logs, filterLevel.value),
);

function levelType(level) {
  return (
    { ERROR: "danger", WARNING: "warning", INFO: "info", DEBUG: "success" }[
      level
    ] || "info"
  );
}
function scrollToBottom() {
  if (logsRef.value) logsRef.value.scrollTop = logsRef.value.scrollHeight;
}
</script>

<style scoped>
.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.log-toolbar {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
  flex-wrap: wrap;
}
.desktop-level-filter {
  width: 110px;
}
.mobile-level-filter {
  display: none;
}
.log-toolbar-actions {
  display: flex;
  gap: 8px;
}
.log-toolbar-actions .el-button {
  margin: 0;
}
.logs-container {
  max-height: 70vh;
  overflow-y: auto;
  padding: 12px;
  color: #e2e8f0;
  border-radius: 8px;
  background: #0f172a;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 13px;
  line-height: 1.7;
}
.logs-empty {
  padding: 40px 0;
  color: #64748b;
  text-align: center;
}
.log-line {
  display: grid;
  gap: 7px;
  padding: 10px 0;
  border-bottom: 1px solid rgb(148 163 184 / 14%);
}
.log-line-meta {
  display: flex;
  align-items: center;
  gap: 10px;
}
.log-time {
  color: #94a3b8;
  white-space: nowrap;
}
.log-level {
  flex-shrink: 0;
  font-weight: 600;
  text-align: center;
}
.log-message {
  min-width: 0;
  margin: 0;
  color: #e2e8f0;
  font: inherit;
  line-height: 1.65;
  overflow-wrap: anywhere;
  white-space: pre-wrap;
  word-break: break-word;
}
.log-level-error .log-message {
  color: #fca5a5;
}
.log-level-warning .log-message {
  color: #fcd34d;
}
@media (max-width: 768px) {
  :deep(.el-card__body) {
    padding: 0 !important;
  }
  .logs-container {
    max-height: calc(100dvh - 252px);
    padding: 8px 16px 20px;
    border-radius: 0;
    font-size: 12px;
  }
  .log-line {
    gap: 6px;
    padding: 11px 0;
  }
  .log-time {
    width: auto;
    font-size: 11px;
    white-space: normal;
  }
  .log-level {
    width: auto;
  }
  .card-header {
    align-items: stretch;
    flex-direction: column;
    gap: 10px;
  }
  .log-title {
    display: flex;
    align-items: center;
    min-height: 22px;
    font-size: 15px;
    font-weight: 700;
    line-height: 22px;
  }
  .log-toolbar {
    display: grid;
    grid-template-columns: auto minmax(0, 1fr);
    justify-content: stretch;
    width: 100%;
  }
  .desktop-level-filter {
    display: none;
  }
  .mobile-level-filter {
    display: flex;
    grid-column: 1 / -1;
    width: 100%;
  }
  .mobile-level-filter :deep(.el-radio-button) {
    flex: 1;
  }
  .mobile-level-filter :deep(.el-radio-button__inner) {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 100%;
    height: 40px;
    min-height: 40px;
    padding: 0 8px;
    box-sizing: border-box;
    line-height: 1;
  }
  .log-toolbar > .el-tag {
    width: auto;
    min-width: 58px;
    height: 22px;
    align-self: center;
    justify-self: start;
    padding-inline: 9px;
  }
  .log-toolbar-actions {
    justify-content: flex-end;
    justify-self: end;
  }
  .log-toolbar-actions .el-button {
    min-height: 38px;
  }
}
@media (max-width: 480px) {
  .logs-container {
    font-size: 11px;
  }
  .log-toolbar {
    grid-template-columns: auto minmax(0, 1fr);
  }
  .log-toolbar-actions .el-button {
    padding-inline: 10px;
  }
}
</style>
