import { ref, onMounted, onUnmounted } from 'vue'
import api from '../api'

const state = ref({
  accounts: [],
  refresh_times: [],
  auto_enabled: true,
  account_count: 0,
  task_count: 0,
  enabled_task_count: 0,
  server_time: '-'
})
const logs = ref([])
const loading = ref(false)
const selectedAccountIndex = ref(undefined)

let stateTimer = null
let logsTimer = null

export function useAppState() {
  async function refreshState() {
    try {
      const res = await api.getState()
      if (res.ok) state.value = res.data
    } catch (err) {
      console.error('刷新状态失败', err)
    }
  }

  async function refreshLogs() {
    try {
      const res = await api.getLogs()
      if (res.ok) logs.value = res.data || []
    } catch (err) {
      console.error('刷新日志失败', err)
    }
  }

  async function loadAll() {
    loading.value = true
    await Promise.all([refreshState(), refreshLogs()])
    loading.value = false
  }

  function startPolling() {
    stopPolling()
    stateTimer = setInterval(refreshState, 3000)
    logsTimer = setInterval(refreshLogs, 3000)
  }

  function stopPolling() {
    if (stateTimer) clearInterval(stateTimer)
    if (logsTimer) clearInterval(logsTimer)
    stateTimer = null
    logsTimer = null
  }

  function isLoggedIn() {
    const token = localStorage.getItem('access_token')
    const expiresAt = localStorage.getItem('expires_at')
    return token && expiresAt && new Date(expiresAt) > new Date()
  }

  onMounted(() => {
    if (isLoggedIn()) {
      loadAll()
      startPolling()
    }
  })

  onUnmounted(() => {
    stopPolling()
  })

  return {
    state,
    logs,
    loading,
    selectedAccountIndex,
    refreshState,
    refreshLogs,
    loadAll,
    startPolling,
    stopPolling
  }
}
