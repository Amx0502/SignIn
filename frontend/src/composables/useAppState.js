import { onMounted, onUnmounted, ref, watch } from 'vue'

import api from '../api'
import {
  isCurrentMenuVisible,
  menuState,
} from '../menu/menuStore.js'

const emptyState = () => ({
  accounts: [],
  refresh_times: [],
  auto_enabled: true,
  account_count: 0,
  task_count: 0,
  enabled_task_count: 0,
  server_time: '-',
})

const state = ref(emptyState())
const logs = ref([])
const loading = ref(false)
const selectedAccountIndex = ref(undefined)

let stateTimer = null
let logsTimer = null
let consumerCount = 0
let stopPermissionWatch = null

function currentUser() {
  try {
    return JSON.parse(localStorage.getItem('user') || 'null')
  } catch {
    return null
  }
}

function isLoggedIn() {
  const token = localStorage.getItem('access_token')
  const expiresAt = localStorage.getItem('expires_at')
  return Boolean(token && expiresAt && new Date(expiresAt) > new Date())
}

function canAccessMenu(menuKey) {
  if (!isLoggedIn()) return false
  const user = currentUser()
  if (user?.role === 'admin') return true
  if (!user || !menuState.loaded) return false
  return isCurrentMenuVisible(menuKey, user)
}

async function refreshState() {
  if (!canAccessMenu('xxqd')) return false
  try {
    const res = await api.getState()
    if (res.ok) state.value = res.data
    return Boolean(res.ok)
  } catch (err) {
    if (err?.status !== 403) console.error('刷新状态失败', err)
    return false
  }
}

async function refreshLogs() {
  if (!canAccessMenu('xxqd.logs')) return false
  try {
    const res = await api.getLogs()
    if (res.ok) logs.value = res.data || []
    return Boolean(res.ok)
  } catch (err) {
    if (err?.status !== 403) console.error('刷新日志失败', err)
    return false
  }
}

async function loadAll() {
  loading.value = true
  await Promise.all([refreshState(), refreshLogs()])
  loading.value = false
}

function stopPolling() {
  if (stateTimer) clearInterval(stateTimer)
  if (logsTimer) clearInterval(logsTimer)
  stateTimer = null
  logsTimer = null
}

function startPolling() {
  stopPolling()
  if (!isLoggedIn()) return

  if (canAccessMenu('xxqd')) {
    void refreshState()
    stateTimer = window.setInterval(refreshState, 3000)
  } else {
    state.value = emptyState()
  }

  if (canAccessMenu('xxqd.logs')) {
    void refreshLogs()
    logsTimer = window.setInterval(refreshLogs, 3000)
  } else {
    logs.value = []
  }
}

function beginSharedPolling() {
  if (stopPermissionWatch) return
  stopPermissionWatch = watch(
    [() => menuState.loaded, () => menuState.version],
    startPolling,
  )
  startPolling()
}

function endSharedPolling() {
  stopPermissionWatch?.()
  stopPermissionWatch = null
  stopPolling()
}

export function useAppState() {
  onMounted(() => {
    consumerCount += 1
    if (consumerCount === 1) beginSharedPolling()
  })

  onUnmounted(() => {
    consumerCount = Math.max(0, consumerCount - 1)
    if (consumerCount === 0) endSharedPolling()
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
    stopPolling,
  }
}
