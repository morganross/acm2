// Backend API URL
// In WordPress: use acm2Config.apiUrl from PHP
// In dev mode: use localhost
// Otherwise: use relative path
declare global {
  interface Window {
    acm2Config?: {
      apiUrl: string
      apiKey: string
      currentUser: string
      nonce: string
    }
  }
}

const isDev = window.location.port === '5173' || window.location.port === '5174'
export const API_BASE_URL = window.acm2Config?.apiUrl || (isDev ? 'http://127.0.0.1:8002/api/v1' : '/api/v1')
const API_BASE = API_BASE_URL

// Get API key from WordPress config or localStorage (for dev)
function getApiKey(): string | null {
  return window.acm2Config?.apiKey || localStorage.getItem('acm_api_key')
}

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public data?: unknown
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const data = await response.json().catch(() => null)
    throw new ApiError(
      data?.detail || response.statusText,
      response.status,
      data
    )
  }
  return response.json()
}

const attachParams = (endpoint: string, params?: Record<string, string | number | boolean>) => {
  if (!params || Object.keys(params).length === 0) {
    return `${API_BASE}${endpoint}`
  }
  // Use window.location.origin as base for relative URLs
  const url = new URL(`${API_BASE}${endpoint}`, window.location.origin)
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null) {
      url.searchParams.set(key, String(value))
    }
  })
  return url.toString()
}

export const apiClient = {
  async get<T>(endpoint: string, params?: Record<string, string | number | boolean>): Promise<T> {
    const headers: Record<string, string> = { 'Content-Type': 'application/json' }
    const apiKey = getApiKey()
    if (apiKey) headers['X-ACM2-API-Key'] = apiKey
    const response = await fetch(attachParams(endpoint, params), {
      method: 'GET',
      headers,
    })
    return handleResponse<T>(response)
  },

  async post<T>(endpoint: string, data?: unknown, params?: Record<string, string | number | boolean>): Promise<T> {
    const headers: Record<string, string> = { 'Content-Type': 'application/json' }
    const apiKey = getApiKey()
    if (apiKey) headers['X-ACM2-API-Key'] = apiKey
    const response = await fetch(attachParams(endpoint, params), {
      method: 'POST',
      headers,
      body: data ? JSON.stringify(data) : undefined,
    })
    return handleResponse<T>(response)
  },

  async put<T>(endpoint: string, data?: unknown): Promise<T> {
    const headers: Record<string, string> = { 'Content-Type': 'application/json' }
    const apiKey = getApiKey()
    if (apiKey) headers['X-ACM2-API-Key'] = apiKey
    const response = await fetch(`${API_BASE}${endpoint}`, {
      method: 'PUT',
      headers,
      body: data ? JSON.stringify(data) : undefined,
    })
    return handleResponse<T>(response)
  },

  async delete<T>(endpoint: string, params?: Record<string, string | number | boolean>): Promise<T> {
    const headers: Record<string, string> = { 'Content-Type': 'application/json' }
    const apiKey = getApiKey()
    if (apiKey) headers['X-ACM2-API-Key'] = apiKey
    const response = await fetch(attachParams(endpoint, params), {
      method: 'DELETE',
      headers,
    })
    return handleResponse<T>(response)
  },
}
