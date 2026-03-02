const { API_BASE } = require('./env')
const DEFAULT_API_BASE = API_BASE

function getAppSafe() {
  try {
    return getApp()
  } catch {
    return null
  }
}

function getBaseUrl() {
  const app = getAppSafe()
  return app?.globalData?.apiBase || DEFAULT_API_BASE
}

function toAbsoluteApiUrl(url = '') {
  if (!url || typeof url !== 'string') return ''
  if (/^https?:\/\//i.test(url)) return url
  if (url.startsWith('/')) return `${getBaseUrl()}${url}`
  return `${getBaseUrl()}/${url}`
}

function getHeaders() {
  const headers = { 'Content-Type': 'application/json' }
  const app = getAppSafe()
  const token =
    (app && typeof app.getToken === 'function' && app.getToken()) ||
    wx.getStorageSync('token') ||
    ''
  if (token) headers['Authorization'] = `Bearer ${token}`
  return headers
}

function request(method, path, data = {}) {
  return new Promise((resolve, reject) => {
    wx.request({
      url: `${getBaseUrl()}${path}`,
      method,
      data,
      header: getHeaders(),
      timeout: 120000,
      success(res) {
        if (res.statusCode >= 200 && res.statusCode < 300) {
          resolve(res.data)
        } else if (res.statusCode === 401) {
          wx.removeStorageSync('token')
          wx.removeStorageSync('userInfo')
          const app = getAppSafe()
          if (app?.globalData) {
            app.globalData.token = null
            app.globalData.userInfo = null
          }
          reject(new Error('登录已过期，请重新登录'))
        } else {
          const detail = res.data?.detail || res.data?.error || '请求失败'
          reject(new Error(typeof detail === 'string' ? detail : JSON.stringify(detail)))
        }
      },
      fail(err) {
        reject(new Error(err.errMsg || '网络请求失败'))
      },
    })
  })
}

const get = (path, params = {}) => {
  const query = Object.entries(params)
    .filter(([, v]) => v !== undefined && v !== null && v !== '')
    .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(v)}`)
    .join('&')
  return request('GET', query ? `${path}?${query}` : path)
}
const post = (path, data = {}) => request('POST', path, data)
const put = (path, data = {}) => request('PUT', path, data)
const del = (path, data = {}) => request('DELETE', path, data)

// ==================== Auth ====================
const wxLogin = (code) => post('/api/v1/auth/wx-login', { code })
const getMe = () => get('/api/v1/auth/me')

// ==================== Content ====================
const getCategories = () => get('/api/v1/content/categories')
const createContent = (data) => post('/api/v1/content/create', data)
const getContentHistory = (limit = 10, userId) =>
  get('/api/v1/content/history', { limit, user_id: userId })
const getContentDetail = (recordId, userId) =>
  get(`/api/v1/content/record/${recordId}`, { user_id: userId })
const suggestAgent = (data) => post('/api/v1/content/suggest-agent', data)

// ==================== Chat ====================
const createChatSession = (data = {}) => post('/api/v1/chat/sessions', data)
const listChatSessions = (params = {}) =>
  get('/api/v1/chat/sessions', {
    user_id: params.user_id,
    module: params.module || 'chat',
    limit: params.limit || 20,
  })
const getChatSession = (sessionId) => get(`/api/v1/chat/sessions/${sessionId}`)
const getChatMessages = (sessionId, limit = 50) =>
  get(`/api/v1/chat/sessions/${sessionId}/messages`, { limit })
const sendChatMessage = (sessionId, data) =>
  post(`/api/v1/chat/sessions/${sessionId}/message`, data)
const closeChatSession = (sessionId) =>
  post(`/api/v1/chat/sessions/${sessionId}/close`)
const deleteChatSession = (sessionId) =>
  del(`/api/v1/chat/sessions/${sessionId}`)

// ==================== Cover ====================
const generateCover = (data) => post('/api/v1/content/generate-cover', data)

// ==================== Video ====================
const startStoryVideo = (data) => post('/api/v1/content/generate-story-video/start', data)
const getVideoTaskStatus = (taskId, provider = 'seedance') =>
  get(`/api/v1/content/generate-story-video/tasks/${taskId}`, { provider })

module.exports = {
  get, post, put, del,
  toAbsoluteApiUrl,
  wxLogin, getMe,
  getCategories, createContent, getContentHistory, getContentDetail, suggestAgent,
  createChatSession, listChatSessions, getChatSession, getChatMessages,
  sendChatMessage, closeChatSession, deleteChatSession,
  generateCover,
  startStoryVideo, getVideoTaskStatus,
}
