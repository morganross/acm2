import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'

// Concurrency settings interface - shared with Settings.tsx
export interface ConcurrencySettings {
  generationConcurrency: number
  evalConcurrency: number
  requestTimeout: number
  maxRetries: number
  retryDelay: number
}

interface Settings {
  apiKeys: {
    openai?: string
    anthropic?: string
    google?: string
  }
  defaults: {
    generatorAdapter: 'fpf' | 'gptr'
    generatorModel: string
    evaluatorModel: string
    rubricType: 'scale_1_5' | 'binary' | 'percentage'
  }
  concurrency: ConcurrencySettings
  advanced: {
    databasePath: string
    reportsDirectory: string
  }
}

const defaultConcurrency: ConcurrencySettings = {
  generationConcurrency: 3,
  evalConcurrency: 3,
  requestTimeout: 1800,
  maxRetries: 3,
  retryDelay: 2,
}

const defaultSettings: Settings = {
  apiKeys: {},
  defaults: {
    generatorAdapter: 'fpf',
    generatorModel: 'gpt-5',
    evaluatorModel: 'gpt-5',
    rubricType: 'scale_1_5',
  },
  concurrency: defaultConcurrency,
  advanced: {
    databasePath: '~/.acm2/acm2.db',
    reportsDirectory: '~/.acm2/reports',
  },
}

// Helper to load concurrency settings from localStorage
export function getConcurrencySettings(): ConcurrencySettings {
  try {
    const stored = localStorage.getItem('acm_concurrency_settings')
    if (stored) {
      return { ...defaultConcurrency, ...JSON.parse(stored) }
    }
  } catch (e) {
    console.error('Failed to load concurrency settings:', e)
  }
  return defaultConcurrency
}

// In a real app, these would call the API
async function fetchSettings(): Promise<Settings> {
  // return apiClient.get<Settings>('/settings')
  return defaultSettings
}

async function updateSettings(settings: Partial<Settings>): Promise<Settings> {
  // return apiClient.put<Settings>('/settings', settings)
  return { ...defaultSettings, ...settings }
}

export function useSettings() {
  return useQuery({
    queryKey: ['settings'],
    queryFn: fetchSettings,
    staleTime: Infinity, // Settings don't change often
  })
}

export function useUpdateSettings() {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: updateSettings,
    onSuccess: (data) => {
      queryClient.setQueryData(['settings'], data)
    },
  })
}
