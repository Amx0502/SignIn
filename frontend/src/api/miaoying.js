import { instance } from './index.js'

const root = '/miaoying'
const data = request => request.then(response => response.data)
export default {
  createQr: () => data(instance.post(`${root}/qr-sessions`)),
  pollQr: id => data(instance.get(`${root}/qr-sessions/${encodeURIComponent(id)}`)),
  listAccounts: () => data(instance.get(`${root}/accounts`)),
  updateAccount: (id, payload) => data(instance.put(`${root}/accounts/${id}`, payload)),
  deleteAccount: id => data(instance.delete(`${root}/accounts/${id}`)),
  syncForms: id => data(instance.post(`${root}/accounts/${id}/forms/sync`, null, { timeout: 60_000 })),
  listForms: id => data(instance.get(`${root}/accounts/${id}/forms`)),
  manualCheckin: (formId, payload) => data(instance.post(`${root}/forms/${formId}/checkin`, payload, { timeout: 60_000 })),
  getLocationConfig: () => instance.get(`${root}/locations/config`),
  searchLocations: (query, region, limit = 6, options = {}) =>
    instance.post(`${root}/locations/search`, { query, region, limit }, {
      signal: options.signal,
      timeout: 12_000,
    }),
  getSettings: () => data(instance.get(`${root}/settings`)),
  updateSettings: payload => data(instance.put(`${root}/settings`, payload)),
  listTasks: () => data(instance.get(`${root}/tasks`)),
  createTask: payload => data(instance.post(`${root}/tasks`, payload)),
  updateTask: (id, payload) => data(instance.put(`${root}/tasks/${id}`, payload)),
  deleteTask: id => data(instance.delete(`${root}/tasks/${id}`)),
  runTask: id => data(instance.post(`${root}/tasks/${id}/run`, null, { timeout: 60_000 })),
  listRuns: (limit = 200) => data(instance.get(`${root}/runs`, { params: { limit } })),
}
