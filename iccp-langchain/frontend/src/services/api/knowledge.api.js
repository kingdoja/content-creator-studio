import { apiClient } from './client'

export const uploadKnowledge = async (data) => apiClient.post('/api/v1/knowledge/upload', data)
export const listKnowledgeDocuments = async () => apiClient.get('/api/v1/knowledge/documents')
export const deleteKnowledgeDocument = async (docId) => apiClient.delete(`/api/v1/knowledge/documents/${docId}`)
export const searchKnowledge = async (data) => apiClient.post('/api/v1/knowledge/search', data)
export const getKnowledgeStats = async () => apiClient.get('/api/v1/knowledge/stats')
export const getKnowledgeReferences = async (params = {}) => {
  const search = new URLSearchParams()
  if (params.document_id) search.set('document_id', params.document_id)
  if (params.limit) search.set('limit', String(params.limit))
  const query = search.toString()
  return apiClient.get(`/api/v1/knowledge/references${query ? `?${query}` : ''}`)
}
