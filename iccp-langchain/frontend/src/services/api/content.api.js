import { API_BASE_URL, apiClient } from './client'
import { streamSseJson } from './sse'

export const createContent = async (data) => apiClient.post('/api/v1/content/create', data)

const streamContent = async (path, data, { onStart, onNodeUpdate, onContentChunk, onComplete, onError } = {}) => {
  try {
    await streamSseJson(`${API_BASE_URL}${path}`, data, {
      onStart,
      onNodeUpdate,
      onContentChunk,
      onComplete,
      onError,
    })
  } catch (e) {
    throw new Error(e?.message || '流式请求失败')
  }
}

export const createContentStream = async (data, handlers = {}) =>
  streamContent('/api/v1/content/create/stream', data, handlers)

export const refineContentStream = async (data, handlers = {}) =>
  streamContent('/api/v1/content/refine/stream', data, handlers)

export const getCategories = async () => apiClient.get('/api/v1/content/categories')
export const getCategoryPrompt = async (categoryId) =>
  apiClient.get(`/api/v1/content/categories/${encodeURIComponent(categoryId)}/prompt`)
export const updateCategoryPrompt = async (categoryId, data) =>
  apiClient.put(`/api/v1/content/categories/${encodeURIComponent(categoryId)}/prompt`, data)
export const suggestAgent = async (data) => apiClient.post('/api/v1/content/suggest-agent', data)
export const evaluateContent = async (data) => apiClient.post('/api/v1/content/evaluate', data)
export const compareAgents = async (data) => apiClient.post('/api/v1/content/compare', data)
export const compareModels = async (data) => apiClient.post('/api/v1/content/compare-models', data)
export const refineContent = async (data) => apiClient.post('/api/v1/content/refine', data)
export const getContentHistory = async (limit = 8, asUserId) =>
  apiClient.get(
    `/api/v1/content/history?limit=${limit}${asUserId ? `&user_id=${encodeURIComponent(asUserId)}` : ''}`
  )
export const getContentDetail = async (recordId, asUserId) =>
  apiClient.get(
    `/api/v1/content/record/${recordId}${asUserId ? `?user_id=${encodeURIComponent(asUserId)}` : ''}`
  )
