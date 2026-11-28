import axios from 'axios'

const BASE_URL = import.meta.env.VITE_API_URL || ''

const api = axios.create({
  baseURL: `${BASE_URL}/api/v1`,
  headers: { 'Content-Type': 'application/json' },
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

api.interceptors.response.use(
  (res) => res,
  (err) => {
    const url = err.config?.url || ''
    const isAuthCall = /\/auth\/(login|register|google)/.test(url)
    // A failed *login* must not bounce the user to /login: that hard reload
    // wipes out the error toast before LoginPage can show it.
    const onAuthPage = ['/login', '/register'].includes(window.location.pathname)
    if (err.response?.status === 401 && !isAuthCall && !onAuthPage) {
      localStorage.removeItem('access_token')
      localStorage.removeItem('user')
      window.location.href = '/login'
    }
    return Promise.reject(err)
  }
)

/**
 * Turn an axios error into a message safe to show in the UI.
 * FastAPI validation errors (422) return `detail` as an array of objects -
 * passing that array straight to toast.error() puts an object where React
 * expects a string and crashes the page ("Objects are not valid as a React
 * child").
 */
export function getErrorMessage(err, fallback = 'Something went wrong. Please try again.') {
  const detail = err?.response?.data?.detail
  if (Array.isArray(detail) && detail.length > 0) {
    const first = detail[0]
    const where = first?.loc ? (Array.isArray(first.loc) ? first.loc.join('.') : String(first.loc)) : 'input'
    return first?.msg ? `${first.msg} (${where})` : fallback
  }
  if (typeof detail === 'string' && detail.trim()) return detail
  if (!err?.response) return 'Cannot reach the server. Is the backend running?'
  return err?.response?.data?.message || fallback
}

export const authAPI = {
  register: (data) => api.post('/auth/register', data),
  login: (data) => api.post('/auth/login', data),
  googleLogin: (credential) => api.post('/auth/google', { credential }),
  me: () => api.get('/auth/me'),
}

export const casesAPI = {
  submit: (data) => api.post('/cases/submit', data),
  prompt: (data) => api.post('/cases/prompt', data),
  list: (skip = 0, limit = 100) => api.get(`/cases/?skip=${skip}&limit=${limit}`),
  get: (id) => api.get(`/cases/${id}`),
  delete: (id) => api.delete(`/cases/${id}`),
  regenerate: (id, section, additionalContext = null) =>
    api.post(`/cases/${id}/regenerate`, { section, additional_context: additionalContext }),
  exportPdf: (id) => api.get(`/cases/${id}/export/pdf`, { responseType: 'blob' }),
  getModels: () => api.get('/admin/models-public'),
  ask: (data) => api.post('/ask', data),
}

export const healthAPI = { check: () => api.get('/health') }

export const adminAPI = {
  users: () => api.get('/admin/users'),
  setRole: (id, role) => api.patch(`/admin/users/${id}`, { role }),
  deleteUser: (id) => api.delete(`/admin/users/${id}`),
  cases: (skip = 0, limit = 100) => api.get(`/admin/cases?skip=${skip}&limit=${limit}`),
  deleteCase: (id) => api.delete(`/admin/cases/${id}`),
  reprocess: (id) => api.post(`/admin/cases/${id}/reprocess`),
  status: () => api.get('/admin/status'),
  toggleLLM: () => api.post('/admin/toggle-llm'),
  setModel: (model) => api.post('/admin/set-model', { model }),
  addModel: (model) => api.post('/admin/add-model', model),
  deleteModel: (id) => api.delete(`/admin/models/${id}`),
  getModels: () => api.get('/admin/models'),
  blockUser: (userId, removeData = false) => api.post('/admin/block-user', { user_id: userId, remove_data: removeData }),
  unblockUser: (userId) => api.post('/admin/unblock-user', { user_id: userId }),
  deleteUserData: (userId) => api.post('/admin/delete-user-data', { user_id: userId }),
}

export default api
