import { apiClient } from './client'

export const generateCover = async (data) => apiClient.post('/api/v1/content/generate-cover', data)
export const generateStoryVideo = async (data) => apiClient.post('/api/v1/content/generate-story-video', data)
export const startStoryVideoTask = async (data) => apiClient.post('/api/v1/content/generate-story-video/start', data)
export const getStoryVideoTaskStatus = async (taskId, provider = 'seedance') =>
  apiClient.get(`/api/v1/content/generate-story-video/tasks/${taskId}`, { params: { provider } })
