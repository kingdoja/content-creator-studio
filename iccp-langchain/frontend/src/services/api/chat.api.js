import { API_BASE_URL, apiClient } from './client'
import { streamSseJson } from './sse'

export const createChatSession = async (data = {}) => apiClient.post('/api/v1/chat/sessions', data)
export const listChatSessions = async (params = {}) => {
  const search = new URLSearchParams()
  if (params.as_user_id) search.set('user_id', params.as_user_id)
  if (params.module) search.set('module', params.module)
  if (params.limit) search.set('limit', String(params.limit))
  const query = search.toString()
  return apiClient.get(`/api/v1/chat/sessions${query ? `?${query}` : ''}`)
}
export const getChatSession = async (sessionId) => apiClient.get(`/api/v1/chat/sessions/${sessionId}`)
export const getChatSessionMessages = async (sessionId, limit = 50) =>
  apiClient.get(`/api/v1/chat/sessions/${sessionId}/messages?limit=${limit}`)
export const sendChatSessionMessage = async (sessionId, data) =>
  apiClient.post(`/api/v1/chat/sessions/${sessionId}/message`, data)

export const sendChatSessionMessageStream = async (
  sessionId,
  data,
  { onStart, onNodeUpdate, onContentChunk, onComplete, onError } = {}
) => {
  try {
    await streamSseJson(
      `${API_BASE_URL}/api/v1/chat/sessions/${sessionId}/message/stream`,
      data,
      { onStart, onNodeUpdate, onContentChunk, onComplete, onError }
    )
  } catch (e) {
    throw new Error(e?.message || '聊天流式请求失败')
  }
}
export const closeChatSession = async (sessionId) => apiClient.post(`/api/v1/chat/sessions/${sessionId}/close`)
export const getChatPreferences = async (asUserId) =>
  apiClient.get(`/api/v1/chat/preferences${asUserId ? `?user_id=${encodeURIComponent(asUserId)}` : ''}`)
