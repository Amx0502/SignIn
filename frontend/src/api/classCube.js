import { instance as defaultInstance } from './index.js'

export function createClassCubeApi(instance = defaultInstance) {
  const root = '/class-cube'

  return {
    getSettings: () => instance.get(`${root}/settings`),
    updateSettings: data => instance.put(`${root}/settings`, data),
    createQrSession: (data = {}) =>
      instance.post(`${root}/qr-sessions`, data),
    pollQrSession: token =>
      instance.get(`${root}/qr-sessions/${encodeURIComponent(token)}`),

    listAccounts: (params = {}) =>
      instance.get(`${root}/accounts`, { params }),
    updateAccount: (accountId, data) =>
      instance.put(`${root}/accounts/${accountId}`, data),
    deleteAccount: accountId =>
      instance.delete(`${root}/accounts/${accountId}`),
    batchDeleteAccounts: ids =>
      instance.post(`${root}/accounts/batch-delete`, { ids }),
    syncCourses: accountId =>
      instance.post(`${root}/accounts/${accountId}/courses/sync`),
    listCourses: accountId =>
      instance.get(`${root}/accounts/${accountId}/courses`),

    syncItems: courseId =>
      instance.post(`${root}/courses/${courseId}/items/sync`),
    listItems: courseId =>
      instance.get(`${root}/courses/${courseId}/items`),
    manualCheckin: (itemId, data) =>
      instance.post(`${root}/items/${itemId}/checkin`, data),
    uploadPhoto: (file, accountId = null) => {
      const formData = new FormData()
      formData.append('file', file)
      const params = accountId ? { account_id: accountId } : {}
      return instance.post(`${root}/photos`, formData, {
        params,
        headers: { 'Content-Type': 'multipart/form-data' },
      })
    },

    listTasks: (params = {}) =>
      instance.get(`${root}/tasks`, { params }),
    createTask: data => instance.post(`${root}/tasks`, data),
    updateTask: (taskId, data) =>
      instance.put(`${root}/tasks/${taskId}`, data),
    deleteTask: taskId =>
      instance.delete(`${root}/tasks/${taskId}`),
    batchDeleteTasks: ids =>
      instance.post(`${root}/tasks/batch-delete`, { ids }),
    runTask: taskId =>
      instance.post(`${root}/tasks/${taskId}/run`, null, {
        timeout: 60_000,
      }),
    retryClaim: claimId =>
      instance.post(`${root}/claims/${claimId}/retry`),

    listRuns: (params = {}) =>
      instance.get(`${root}/runs`, { params }),
    listLogs: (limit = 200) =>
      instance.get(`${root}/logs`, { params: { limit } }),
  }
}

export default createClassCubeApi()
