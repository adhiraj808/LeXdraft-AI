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
    if (err.response?.status === 401) {
      localStorage.removeItem('access_token')
      localStorage.removeItem('user')
      window.location.href = '/login'
    }
    return Promise.reject(err)
  }
)

export const authAPI = {
  register: (data) => api.post('/auth/register', data),
  login: (data) => api.post('/auth/login', data),
  googleLogin: (credential) => api.post('/auth/google', { credential }),
  me: () => api.get('/auth/me'),
}

export const casesAPI = {
  submit: (data) => api.post('/cases/submit', data),
  list: (skip = 0, limit = 20) => api.get(`/cases/?skip=${skip}&limit=${limit}`),
  get: (id) => api.get(`/cases/${id}`),
  delete: (id) => api.delete(`/cases/${id}`),
  regenerate: (id, section, additionalContext = null) =>
    api.post(`/cases/${id}/regenerate`, { section, additional_context: additionalContext }),
  exportPdf: (id) => api.get(`/cases/${id}/export/pdf`, { responseType: 'blob' }),
}

export const healthAPI = { check: () => api.get('/health') }

export default api
