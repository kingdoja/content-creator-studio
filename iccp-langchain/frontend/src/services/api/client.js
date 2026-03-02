import axios from 'axios'

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
export const TOKEN_KEY = 'iccp_access_token'

function getErrorMessage(error) {
  const data = error?.response?.data
  if (typeof data?.detail === 'string') return data.detail
  if (data?.detail && typeof data.detail === 'object' && data.detail.error) return data.detail.error
  if (typeof data?.error === 'string') return data.error
  if (typeof data?.message === 'string') return data.message
  return '请求失败'
}

function isLikelyLLMEndpoint(url = '') {
  return /dashscope\.aliyuncs\.com|api\.openai\.com/i.test(url)
}

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

apiClient.interceptors.request.use(
  (config) => {
    if (isLikelyLLMEndpoint(API_BASE_URL)) {
      throw new Error(`VITE_API_BASE_URL 配置错误：当前为 ${API_BASE_URL}，应指向后端（如 http://localhost:8000）`)
    }
    const token = localStorage.getItem(TOKEN_KEY)
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error)
)

apiClient.interceptors.response.use(
  (response) => response.data,
  (error) => {
    if (error.response) throw new Error(getErrorMessage(error))
    if (error.request) throw new Error('无法连接到服务器，请检查后端服务是否运行')
    throw new Error(error.message || '请求失败')
  }
)

export const resolveAssetUrl = (path) => {
  if (!path) return ''
  if (/^https?:\/\//i.test(path)) return path
  const normalized = path.startsWith('/') ? path : `/${path}`
  return `${API_BASE_URL}${normalized}`
}

export const buildAuthHeaders = (extraHeaders = {}) => {
  const headers = { ...extraHeaders }
  const token = localStorage.getItem(TOKEN_KEY)
  if (token) headers.Authorization = `Bearer ${token}`
  return headers
}
