import { computed, getCurrentInstance, onUnmounted, ref } from 'vue'

import classCubeApi from '../api/classCube.js'
import {
  normalizeQrSession,
  reconcileSelection,
} from '../utils/classCube.js'
import { latestSyncedDayItems } from '../utils/classCubeItems.js'
import { taskRequest } from '../utils/classCubeTaskForm.js'

const TERMINAL_QR_STATES = new Set(['success', 'expired', 'error'])
const BACKGROUND_REFRESH_MS = 30_000
const QR_POLL_MS = 1_000
function responseData(response, fallback = null) {
  if (response?.ok === false) {
    throw new Error(response.error || '班级魔方请求失败')
  }
  return response?.data ?? fallback
}

export function normalizeClassCubeError(error) {
  if (error instanceof Error && error.message) return error.message
  if (typeof error === 'string' && error) return error
  return error?.response?.data?.error || '班级魔方请求失败'
}

export function useClassCube(api = classCubeApi) {
  const accounts = ref([])
  const courses = ref([])
  const items = ref([])
  const tasks = ref([])
  const runs = ref([])
  const logs = ref([])
  const batchTargets = ref([])

  const selectedAccountId = ref(null)
  const selectedCourseId = ref(null)
  const selectedItemId = ref(null)
  const selectedTaskIds = ref(new Set())
  const taskDraft = ref(null)
  const accountFilters = ref({})
  const taskFilters = ref({})
  const runFilters = ref({})

  const qrSession = ref(null)
  const qrRemainingSeconds = ref(0)
  const loading = ref(false)
  const coursesLoading = ref(false)
  const itemsLoading = ref(false)
  const itemsSyncing = ref(false)
  const error = ref('')

  let backgroundTimer = null
  let qrPollTimer = null
  let qrCountdownTimer = null
  let qrGeneration = 0
  let courseRequestGeneration = 0
  let itemRequestGeneration = 0
  let batchTargetRequestGeneration = 0
  let accountSelectionGeneration = 0
  let courseSelectionGeneration = 0
  let disposed = false

  const selectedAccount = computed(() =>
    reconcileSelection(accounts.value, selectedAccountId.value))
  const selectedCourse = computed(() =>
    reconcileSelection(courses.value, selectedCourseId.value))
  const selectedItem = computed(() =>
    reconcileSelection(items.value, selectedItemId.value))

  function reportError(caught) {
    error.value = normalizeClassCubeError(caught)
    return error.value
  }

  function preserveIds(source, ids) {
    const available = new Set(source.map(row => row.id))
    return new Set([...ids].filter(id => available.has(id)))
  }

  async function loadAccounts(params = accountFilters.value) {
    accountFilters.value = { ...params }
    const fresh = responseData(await api.listAccounts(params), [])
    accounts.value = Array.isArray(fresh) ? fresh : []
    const stable = reconcileSelection(accounts.value, selectedAccountId.value)
    selectedAccountId.value = stable?.id ?? accounts.value[0]?.id ?? null
    return accounts.value
  }

  async function loadCourses(accountId = selectedAccountId.value) {
    const generation = ++courseRequestGeneration
    if (!accountId) {
      courses.value = []
      selectedCourseId.value = null
      items.value = []
      selectedItemId.value = null
      coursesLoading.value = false
      return []
    }
    coursesLoading.value = true
    try {
      const fresh = responseData(await api.listCourses(accountId), [])
      if (generation !== courseRequestGeneration || accountId !== selectedAccountId.value) return []
      courses.value = Array.isArray(fresh) ? fresh : []
      const stable = reconcileSelection(courses.value, selectedCourseId.value)
      selectedCourseId.value = stable?.id ?? courses.value[0]?.id ?? null
      if (!selectedCourseId.value) {
        items.value = []
        selectedItemId.value = null
      }
      return courses.value
    } finally {
      if (generation === courseRequestGeneration) coursesLoading.value = false
    }
  }

  async function loadItems(courseId = selectedCourseId.value) {
    const generation = ++itemRequestGeneration
    if (!courseId) {
      items.value = []
      selectedItemId.value = null
      itemsLoading.value = false
      return []
    }
    itemsLoading.value = true
    try {
      const fresh = responseData(await api.listItems(courseId, { latest_only: 1 }), [])
      if (generation !== itemRequestGeneration || courseId !== selectedCourseId.value) return []
      items.value = latestSyncedDayItems(
        Array.isArray(fresh) ? fresh : [],
      )
      const stable = reconcileSelection(items.value, selectedItemId.value)
      selectedItemId.value = stable?.id ?? items.value[0]?.id ?? null
      return items.value
    } finally {
      if (generation === itemRequestGeneration) itemsLoading.value = false
    }
  }

  async function loadBatchTargets(itemId = selectedItemId.value) {
    const generation = ++batchTargetRequestGeneration
    batchTargets.value = []
    if (!itemId) {
      return []
    }
    const fresh = responseData(await api.listBatchTargets(itemId), [])
    if (
      generation !== batchTargetRequestGeneration
      || itemId !== selectedItemId.value
    ) return []
    batchTargets.value = Array.isArray(fresh) ? fresh : []
    return batchTargets.value
  }

  async function loadTasks(params = taskFilters.value) {
    taskFilters.value = { ...params }
    const fresh = responseData(await api.listTasks(params), [])
    tasks.value = Array.isArray(fresh) ? fresh : []
    selectedTaskIds.value = preserveIds(
      tasks.value,
      selectedTaskIds.value,
    )
    return tasks.value
  }

  async function loadRuns(params = runFilters.value) {
    runFilters.value = { ...params }
    const fresh = responseData(await api.listRuns(params), [])
    runs.value = Array.isArray(fresh) ? fresh : []
    return runs.value
  }

  async function loadLogs(limit = 200) {
    const fresh = responseData(await api.listLogs(limit), [])
    logs.value = Array.isArray(fresh) ? fresh : []
    return logs.value
  }

  async function loadInitial({ accountParams = {}, taskParams = {} } = {}) {
    loading.value = true
    error.value = ''
    try {
      await Promise.all([
        loadAccounts(accountParams),
        loadTasks(taskParams),
        loadRuns(),
      ])
      await loadCourses()
      await loadItems()
    } catch (caught) {
      reportError(caught)
      throw caught
    } finally {
      loading.value = false
    }
  }

  async function selectAccount(accountId) {
    const selectionGeneration = ++accountSelectionGeneration
    selectedAccountId.value = accountId
    selectedCourseId.value = null
    selectedItemId.value = null
    courses.value = []
    items.value = []
    ++courseSelectionGeneration
    ++itemRequestGeneration
    await loadCourses(accountId)
    if (selectionGeneration !== accountSelectionGeneration || accountId !== selectedAccountId.value) return []
    return loadItems()
  }

  async function selectCourse(courseId) {
    const selectionGeneration = ++courseSelectionGeneration
    selectedCourseId.value = courseId
    selectedItemId.value = null
    items.value = []
    const loaded = await loadItems(courseId)
    if (selectionGeneration !== courseSelectionGeneration || courseId !== selectedCourseId.value) return []
    return loaded
  }

  async function syncCourses(accountId = selectedAccountId.value) {
    await api.syncCourses(accountId)
    return loadCourses(accountId)
  }

  async function syncItems(courseId = selectedCourseId.value) {
    if (!courseId) return []
    itemsSyncing.value = true
    try {
      const fresh = responseData(await api.syncItems(courseId), null)
      if (!Array.isArray(fresh)) return loadItems(courseId)
      items.value = latestSyncedDayItems(fresh)
      const stable = reconcileSelection(items.value, selectedItemId.value)
      selectedItemId.value = stable?.id ?? items.value[0]?.id ?? null
      return items.value
    } finally {
      itemsSyncing.value = false
    }
  }

  async function saveTask(payload, taskId = null) {
    const request = taskRequest(payload, taskId !== null)
    const response = taskId
      ? await api.updateTask(taskId, request)
      : await api.createTask(request)
    await loadTasks()
    return responseData(response)
  }

  async function removeTasks(ids = [...selectedTaskIds.value]) {
    if (!ids.length) return []
    await api.batchDeleteTasks(ids)
    selectedTaskIds.value = new Set()
    return loadTasks()
  }

  async function deleteAccounts(ids) {
    if (!ids.length) return 0
    const response = await api.batchDeleteAccounts(ids)
    return responseData(response, 0)
  }

  async function refreshBackground() {
    try {
      await Promise.all([loadTasks(), loadRuns()])
    } catch (caught) {
      reportError(caught)
    }
  }

  function startBackgroundPolling() {
    stopBackgroundPolling()
    backgroundTimer = setInterval(
      refreshBackground,
      BACKGROUND_REFRESH_MS,
    )
  }

  function stopBackgroundPolling() {
    if (backgroundTimer !== null) clearInterval(backgroundTimer)
    backgroundTimer = null
  }

  function stopQrPolling({ clear = false } = {}) {
    qrGeneration += 1
    if (qrPollTimer !== null) clearTimeout(qrPollTimer)
    if (qrCountdownTimer !== null) clearInterval(qrCountdownTimer)
    qrPollTimer = null
    qrCountdownTimer = null
    if (clear) {
      qrSession.value = null
      qrRemainingSeconds.value = 0
    }
  }

  function updateQrCountdown(generation) {
    if (generation !== qrGeneration || !qrSession.value) return
    qrRemainingSeconds.value = Math.max(
      0,
      Math.ceil((qrSession.value.deadlineMs - Date.now()) / 1000),
    )
    if (qrRemainingSeconds.value === 0) {
      qrSession.value = { ...qrSession.value, status: 'expired' }
      stopQrPolling()
    }
  }

  function scheduleQrPoll(token, generation) {
    qrPollTimer = setTimeout(async () => {
      if (disposed || generation !== qrGeneration) return
      try {
        const status = responseData(await api.pollQrSession(token), {})
        if (generation !== qrGeneration) return
        qrSession.value = {
          ...qrSession.value,
          status: status.status || 'pending',
          retryable: Boolean(status.retryable),
          syncWarning: status.sync_warning || '',
        }
        if (qrSession.value.status === 'error' && qrSession.value.retryable) {
          scheduleQrPoll(token, generation)
          return
        }
        if (TERMINAL_QR_STATES.has(qrSession.value.status)) {
          stopQrPolling()
          if (qrSession.value.status === 'success') {
            await Promise.all([loadAccounts(), loadTasks()])
            await loadCourses()
            await loadItems()
          }
          return
        }
        scheduleQrPoll(token, generation)
      } catch (caught) {
        if (generation !== qrGeneration) return
        qrSession.value = {
          ...qrSession.value,
          status: 'error',
          retryable: true,
        }
        reportError(caught)
        scheduleQrPoll(token, generation)
      }
    }, QR_POLL_MS)
  }

  async function startQrLogin(accountId = null) {
    stopQrPolling({ clear: true })
    error.value = ''
    const generation = qrGeneration
    try {
      const numericAccountId = Number(accountId)
      const payload = Number.isInteger(numericAccountId) && numericAccountId > 0
        ? { account_id: numericAccountId }
        : {}
      const created = responseData(await api.createQrSession(payload), {})
      if (disposed || generation !== qrGeneration) return null
      qrSession.value = normalizeQrSession(created)
      qrRemainingSeconds.value = qrSession.value.expiresInSeconds
      qrCountdownTimer = setInterval(
        () => updateQrCountdown(generation),
        QR_POLL_MS,
      )
      scheduleQrPoll(qrSession.value.token, generation)
      return qrSession.value
    } catch (caught) {
      if (generation === qrGeneration) {
        qrSession.value = {
          token: '',
          qrImage: '',
          status: 'error',
          retryable: true,
          expiresInSeconds: 0,
          deadlineMs: Date.now(),
        }
        qrRemainingSeconds.value = 0
      }
      reportError(caught)
      throw caught
    }
  }

  function dispose() {
    disposed = true
    stopBackgroundPolling()
    stopQrPolling()
  }

  if (getCurrentInstance()) onUnmounted(dispose)

  async function invoke(method, ...args) {
    return responseData(await method(...args))
  }

  function manualCheckin(itemId, payload = {}) {
    const request = { ...payload }
    if (Object.hasOwn(request, 'photoPath')) {
      request.photo_path = request.photoPath
      delete request.photoPath
    }
    return invoke(api.manualCheckin, itemId, request)
  }

  function batchCheckin(itemId, payload = {}, accountIds = []) {
    return invoke(api.batchCheckin, itemId, {
      ...payload,
      account_ids: accountIds,
    })
  }

  function syncClassItems(courseId) {
    return invoke(api.syncClassItems, courseId)
  }

  function syncAllAccountItems() {
    return invoke(api.syncAllAccountItems)
  }

  return {
    accounts,
    courses,
    items,
    tasks,
    runs,
    logs,
    batchTargets,
    selectedAccountId,
    selectedCourseId,
    selectedItemId,
    selectedTaskIds,
    selectedAccount,
    selectedCourse,
    selectedItem,
    taskDraft,
    accountFilters,
    taskFilters,
    runFilters,
    qrSession,
    qrRemainingSeconds,
    loading,
    coursesLoading,
    itemsLoading,
    itemsSyncing,
    error,
    loadAccounts,
    loadCourses,
    loadItems,
    loadBatchTargets,
    loadTasks,
    loadRuns,
    loadLogs,
    loadInitial,
    selectAccount,
    selectCourse,
    syncCourses,
    syncItems,
    saveTask,
    removeTasks,
    deleteAccounts,
    refreshBackground,
    startBackgroundPolling,
    stopBackgroundPolling,
    startQrLogin,
    stopQrPolling,
    dispose,
    uploadPhoto: (...args) => invoke(api.uploadPhoto, ...args),
    manualCheckin,
    batchCheckin,
    syncClassItems,
    syncAllAccountItems,
    updateAccount: (...args) => invoke(api.updateAccount, ...args),
    deleteAccount: (...args) => invoke(api.deleteAccount, ...args),
    deleteTask: (...args) => invoke(api.deleteTask, ...args),
    runTask: (...args) => invoke(api.runTask, ...args),
    retryClaim: (...args) => invoke(api.retryClaim, ...args),
  }
}
