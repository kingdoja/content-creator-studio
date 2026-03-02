import { apiClient } from './client'

export const listMemoryEntries = async (params = {}) => {
  const search = new URLSearchParams()
  if (params.as_user_id) search.set('user_id', params.as_user_id)
  if (params.memory_type) search.set('memory_type', params.memory_type)
  if (params.source_module) search.set('source_module', params.source_module)
  if (params.created_from) search.set('created_from', params.created_from)
  if (params.created_to) search.set('created_to', params.created_to)
  if (params.offset !== undefined) search.set('offset', String(params.offset))
  if (params.limit) search.set('limit', String(params.limit))
  const query = search.toString()
  return apiClient.get(`/api/v1/memory/entries${query ? `?${query}` : ''}`)
}

export const deleteMemoryEntry = async (entryId, asUserId) =>
  apiClient.delete(
    `/api/v1/memory/entries/${entryId}${asUserId ? `?user_id=${encodeURIComponent(asUserId)}` : ''}`
  )

export const getMemoryEntry = async (entryId, asUserId) =>
  apiClient.get(
    `/api/v1/memory/entries/${entryId}${asUserId ? `?user_id=${encodeURIComponent(asUserId)}` : ''}`
  )

export const getMemoryStats = async (asUserId) =>
  apiClient.get(`/api/v1/memory/stats${asUserId ? `?user_id=${encodeURIComponent(asUserId)}` : ''}`)

export const getMemoryConfig = async () => apiClient.get('/api/v1/memory/config')

export const recallMemories = async ({ query, as_user_id, memory_types, top_k = 5 } = {}) => {
  const search = new URLSearchParams()
  if (query) search.set('query', query)
  if (as_user_id) search.set('user_id', as_user_id)
  if (memory_types) search.set('memory_types', memory_types)
  if (top_k !== undefined) search.set('top_k', String(top_k))
  return apiClient.get(`/api/v1/memory/recall?${search.toString()}`)
}

export const listMemoryLinks = async (params = {}) => {
  const search = new URLSearchParams()
  if (params.source_type) search.set('source_type', params.source_type)
  if (params.source_id) search.set('source_id', params.source_id)
  if (params.target_type) search.set('target_type', params.target_type)
  if (params.target_id) search.set('target_id', params.target_id)
  if (params.relation) search.set('relation', params.relation)
  if (params.limit !== undefined) search.set('limit', String(params.limit))
  const query = search.toString()
  return apiClient.get(`/api/v1/memory/links${query ? `?${query}` : ''}`)
}

export const createMemoryLink = async (payload) => apiClient.post('/api/v1/memory/links', payload)

export const getMemoryPreferences = async (asUserId) =>
  apiClient.get(`/api/v1/memory/preferences${asUserId ? `?user_id=${encodeURIComponent(asUserId)}` : ''}`)

export const updateMemoryPreference = async (payload) =>
  apiClient.put('/api/v1/memory/preferences', payload)
