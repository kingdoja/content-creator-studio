import { TOKEN_KEY, apiClient } from './client'

export const register = async (data) => {
  const resp = await apiClient.post('/api/v1/auth/register', data)
  if (resp?.access_token) localStorage.setItem(TOKEN_KEY, resp.access_token)
  return resp
}

export const login = async (data) => {
  const resp = await apiClient.post('/api/v1/auth/login', data)
  if (resp?.access_token) localStorage.setItem(TOKEN_KEY, resp.access_token)
  return resp
}

export const getMe = async () => apiClient.get('/api/v1/auth/me')

export const logout = () => localStorage.removeItem(TOKEN_KEY)

export const getObservabilityStatus = async () => apiClient.get('/api/v1/observability/status')
export const healthCheck = async () => apiClient.get('/health')
