<template><div class="cube-subpage"><el-card><template #header>运行记录</template><RunHistoryPanel :runs="runs" :tasks="tasks" :accounts="accounts" :courses="courses" :is-admin="isAdmin" :load-runs-action="loadRuns" :retry-claim-action="retryClaim" /><div class="cube-logs"><div class="log-title">班级魔方日志</div><pre v-for="(line,index) in logs" :key="index">{{ line }}</pre></div></el-card></div></template>
<script setup>
import { computed, onMounted, onUnmounted } from 'vue'
import RunHistoryPanel from '../components/class-cube/RunHistoryPanel.vue'
import { useClassCube } from '../composables/useClassCube.js'
const {runs,tasks,accounts,courses,logs,loadRuns,loadLogs,retryClaim,loadInitial}=useClassCube(); const user=JSON.parse(localStorage.getItem('user')||'{}'); const isAdmin=computed(()=>user.role==='admin'); let timer; onMounted(async()=>{await loadInitial().catch(()=>{});await loadLogs();timer=setInterval(loadLogs,3000)});onUnmounted(()=>clearInterval(timer))
</script><style scoped>.cube-subpage{display:grid;gap:18px}.cube-logs{margin-top:18px;padding:14px;border-radius:14px;background:#0f172a;color:#dbeafe;max-height:320px;overflow:auto}.log-title{margin-bottom:8px;color:#93c5fd;font-weight:700}.cube-logs pre{margin:4px 0;white-space:pre-wrap;font:12px/1.5 ui-monospace,monospace}</style>
