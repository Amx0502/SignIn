import axios from 'axios'

const instance = axios.create({
  baseURL: '/api',
  headers: { 'Content-Type': 'application/json' }
})

instance.interceptors.response.use(
  res => res.data,
  err => {
    const msg = err.response?.data?.error || err.message || '请求失败'
    return Promise.reject(new Error(msg))
  }
)

export default {
  getState: () => instance.get('/state'),
  getLogs: (limit = 200) => instance.get('/logs', { params: { limit } }),

  addAccount: data => instance.post('/accounts', data),
  updateAccount: (index, data) => instance.put(`/accounts/${index}`, data),
  deleteAccount: index => instance.delete(`/accounts/${index}`),
  loginAccount: index => instance.post(`/accounts/${index}/login`),
  refreshAccountToken: index => instance.post(`/accounts/${index}/refresh-token`),
  fetchProjects: index => instance.get(`/accounts/${index}/projects`),

  addTask: (index, data) => instance.post(`/accounts/${index}/tasks`, data),
  updateTask: (accountIndex, taskIndex, data) => instance.put(`/accounts/${accountIndex}/tasks/${taskIndex}`, data),
  deleteTask: (accountIndex, taskIndex) => instance.delete(`/accounts/${accountIndex}/tasks/${taskIndex}`),
  runTask: (accountIndex, taskIndex) => instance.post(`/accounts/${accountIndex}/tasks/${taskIndex}/run`),

  runAccountTasks: index => instance.post(`/accounts/${index}/run-all`),
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
