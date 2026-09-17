import axios from 'axios'

export const instance = axios.create({
  baseURL: '/api',
  headers: { 'Content-Type': 'application/json' }
})

instance.interceptors.request.use(config => {
  const token = localStorage.getItem('access_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

instance.interceptors.response.use(
  res => res.data,
  err => {
    if (err.response?.status === 401) {
      localStorage.removeItem('access_token')
      localStorage.removeItem('expires_at')
      localStorage.removeItem('user')
      if (window.location.pathname !== '/login') {
        window.location.href = '/login'
      }
    }
    const msg = err.response?.data?.error || err.message || '请求失败'
    const error = new Error(msg)
    error.status = err.response?.status
    error.data = err.response?.data
    return Promise.reject(error)
  }
)

export const loginApi = data => instance.post('/auth/login', data)
export const logoutApi = () => instance.post('/auth/logout')
export const verifyTokenApi = () => instance.post('/auth/verify')
export const changePasswordApi = data => instance.post('/auth/change-password', data)
export const getUsersApi = (params = {}) => instance.get('/users', { params })
export const exportArchivedUsersApi = (params = {}) => instance.get('/users/archived/export', {
  params,
  responseType: 'blob',
})
export const exportUsersApi = (params = {}) => instance.get('/users/export', {
  params,
  responseType: 'blob',
})
export const getUserCredentialsApi = id => instance.get(`/users/${id}/credentials`)
export const createUserApi = data => instance.post('/users', data)
export const createPlatformMemberApi = data => instance.post('/users/members', data)
export const updateUserApi = (id, data) => instance.put(`/users/${id}`, data)
export const resetUserPasswordApi = (id, data) => instance.post(`/users/${id}/reset-password`, data)
export const deleteUserApi = id => instance.delete(`/users/${id}`)
export const getMenuCatalogApi = () => instance.get('/menu/catalog')
export const getAdminMenuConfigApi = userId => instance.get('/admin/menu-config', {
  params: userId ? { user_id: userId } : {},
})
export const updateGlobalMenuConfigApi = data => instance.put('/admin/menu-config/global', data)
export const updateUserMenuOverridesApi = (userId, data) => instance.put(`/admin/menu-config/users/${userId}`, data)
export const getMenuConfigLogsApi = (limit = 100) => instance.get('/admin/menu-config/logs', { params: { limit } })
export const getCheckinDelaySettingsApi = () => instance.get('/admin/checkin-delay-settings')
export const updateCheckinDelaySettingsApi = data => instance.put('/admin/checkin-delay-settings', data)
export const getSiteConfigApi = () => instance.get('/site/config')
export const getPurchaseLinkSettingsApi = () => instance.get('/admin/purchase-link-settings')
export const updatePurchaseLinkSettingsApi = data => instance.put('/admin/purchase-link-settings', data)
export const locationApi = {
  getLocationConfig: () => instance.get('/locations/config'),
  searchLocations: (query, region, limit = 6, options = {}) =>
    instance.post('/locations/search', { query, region, limit }, {
      signal: options.signal,
      timeout: 12_000,
    }),
  reverseLocation: (latitude, longitude) =>
    instance.post('/locations/reverse', { latitude, longitude }),
}
export const getDashboardSummaryApi = range => instance.get('/admin/dashboard/summary', {
  params: { range },
})
export const listXxqdRunsApi = (params = {}) => instance.get('/xxqd/runs', { params })

export default {
  getState: () => instance.get('/state'),
  getLogs: (limit = 200) => instance.get('/xxqd/logs', { params: { limit } }),

  addAccount: data => instance.post('/accounts', data),
  updateAccount: (index, data) => instance.put(`/accounts/${index}`, data),
  deleteAccount: index => instance.delete(`/accounts/${index}`),
  loginAccount: index => instance.post(`/accounts/${index}/login`),
  refreshAccountToken: index => instance.post(`/accounts/${index}/refresh-token`),
  fetchProjects: index => instance.get(`/accounts/${index}/projects`),
  fetchFillOptions: (index, projectIndex) => instance.get(`/accounts/${index}/fill-options`, { params: { project_index: projectIndex } }),

  addTask: (index, data) => instance.post(`/accounts/${index}/tasks`, data),
  updateTask: (accountIndex, taskIndex, data) => instance.put(`/accounts/${accountIndex}/tasks/${taskIndex}`, data),
  deleteTask: (accountIndex, taskIndex) => instance.delete(`/accounts/${accountIndex}/tasks/${taskIndex}`),
  runTask: (accountIndex, taskIndex) => instance.post(`/accounts/${accountIndex}/tasks/${taskIndex}/run`, null, { timeout: 60000 }),

  refreshAllTokens: () => instance.post('/accounts/refresh-all'),
  runAllEnabledTasks: () => instance.post('/run-all'),
  setSettings: data => instance.post('/settings', data),
  uploadImage: file => {
    const formData = new FormData()
    formData.append('file', file)
    return instance.post('/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
  }
}
