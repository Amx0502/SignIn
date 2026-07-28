import { computed, getCurrentInstance, onUnmounted, ref } from 'vue'

import classCubeApi from '../api/classCube.js'
import {
  normalizeQrSession,
  reconcileSelection,
} from '../utils/classCube.js'

const TERMINAL_QR_STATES = new Set(['success', 'expired', 'error'])
const BACKGROUND_REFRESH_MS = 30_000
const QR_POLL_MS = 1_000
const TASK_FIELDS = new Set([
  'owner_user_id',
  'account_id',
  'course_id',
  'name',
  'enabled',
  'latitude',
  'longitude',
  'accuracy',
  'photo_path',
  'password',
  'clear_password',
])

function responseData(response, fallback = null) {
  if (response?.ok === false) {
    throw new Error(response.error || '班级魔方请求失败')
  }
  return response?.data ?? fallback
}

function taskRequest(payload, isEdit) {
  const request = Object.fromEntries(
    Object.entries(payload || {}).filter(([key]) => TASK_FIELDS.has(key)),
  )
  if (isEdit) {
    delete request.owner_user_id
    if (request.clear_password) {
      delete request.password
    } else if (!request.password) {
      delete request.password
      delete request.clear_password
    }
  } else {
    delete request.clear_password
  }
  return request
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
  const error = ref('')

  let backgroundTimer = null
  let qrPollTimer = null
  let qrCountdownTimer = null
  let qrGeneration = 0
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
    if (!accountId) {
      courses.value = []
      selectedCourseId.value = null
      items.value = []
      selectedItemId.value = null
      return []
    }
    const fresh = responseData(await api.listCourses(accountId), [])
    courses.value = Array.isArray(fresh) ? fresh : []
    const stable = reconcileSelection(courses.value, selectedCourseId.value)
    selectedCourseId.value = stable?.id ?? courses.value[0]?.id ?? null
    if (!selectedCourseId.value) {
      items.value = []
      selectedItemId.value = null
    }
    return courses.value
  }

  async function loadItems(courseId = selectedCourseId.value) {
    if (!courseId) {
      items.value = []
      selectedItemId.value = null
      return []
    }
    const fresh = responseData(await api.listItems(courseId), [])
    items.value = Array.isArray(fresh) ? fresh : []
    const stable = reconcileSelection(items.value, selectedItemId.value)
    selectedItemId.value = stable?.id ?? items.value[0]?.id ?? null
    return items.value
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
    selectedAccountId.value = accountId
    selectedCourseId.value = null
    selectedItemId.value = null
    await loadCourses(accountId)
    return loadItems()
  }

  async function selectCourse(courseId) {
    selectedCourseId.value = courseId
    selectedItemId.value = null
    return loadItems(courseId)
  }

  async function syncCourses(accountId = selectedAccountId.value) {
    await api.syncCourses(accountId)
    return loadCourses(accountId)
  }

  async function syncItems(courseId = selectedCourseId.value) {
    await api.syncItems(courseId)
    return loadItems(courseId)
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
        stopQrPolling()
      }
    }, QR_POLL_MS)
  }

  async function startQrLogin(accountId = null) {
    stopQrPolling({ clear: true })
    error.value = ''
    const generation = qrGeneration
    try {
      const payload = accountId ? { account_id: accountId } : {}
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

  return {
    accounts,
    courses,
    items,
    tasks,
    runs,
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
    error,
    loadAccounts,
    loadCourses,
    loadItems,
    loadTasks,
    loadRuns,
    loadInitial,
    selectAccount,
    selectCourse,
    syncCourses,
    syncItems,
    saveTask,
    removeTasks,
    refreshBackground,
    startBackgroundPolling,
    stopBackgroundPolling,
    startQrLogin,
    stopQrPolling,
    dispose,
    uploadPhoto: (...args) => invoke(api.uploadPhoto, ...args),
    manualCheckin,
    updateAccount: (...args) => invoke(api.updateAccount, ...args),
    deleteAccount: (...args) => invoke(api.deleteAccount, ...args),
    deleteTask: (...args) => invoke(api.deleteTask, ...args),
    runTask: (...args) => invoke(api.runTask, ...args),
    retryClaim: (...args) => invoke(api.retryClaim, ...args),
  }
}
