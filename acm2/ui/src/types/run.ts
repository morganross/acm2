export type RunStatus = 'pending' | 'running' | 'paused' | 'completed' | 'failed' | 'cancelled'

export interface Run {
  id: string
  name: string
  description?: string
  status: RunStatus

  // Config
  generators: string[]
  models: any[]
  document_ids: string[]
  iterations: number
  log_level?: string  // Log level: ERROR, WARNING, INFO, DEBUG, VERBOSE
  gptr_settings?: any
  evaluation: any
  pairwise: any

  // Progress & Stats
  progress: number // Percentage 0-100
  tasks: TaskSummary[]
  total_cost_usd: number
  cost_by_model: Record<string, number>
  cost_by_document: Record<string, number>

  // Timing
  created_at: string
  started_at?: string
  completed_at?: string
  total_duration_seconds?: number
  duration_seconds?: number // For running time calculation

  tags: string[]

  // Legacy/UI specific fields that might be needed or were used
  mode?: string
  current_phase?: string
  pre_combine_evals?: any[] // Array of evaluation results
  fpf_stats?: any // FPF live stats
  pairwise_results?: any // Pairwise evaluation results
}

export interface TaskSummary {
  id: string
  name: string
  status: string
  generator: string
  duration_seconds?: number
  cost_usd: number
  error?: string
  // UI might expect these
  document_name?: string
  model?: string
  iteration?: number
  progress?: number
  message?: string
}

export interface RunConfig {
  generator: GeneratorConfig
  evaluator: EvaluatorConfig
}

export interface GeneratorConfig {
  adapter: string
  model: string
  temperature: number
  maxTokens: number
  options?: Record<string, unknown>
}

export interface EvaluatorConfig {
  model: string
  rubricType: 'scale_1_5' | 'binary' | 'percentage'
  passThreshold: number
  dimensions: string[]
}

export interface CreateRunRequest {
  title: string
  description?: string
  documents: string[]
  models: string[]
  generators?: string[]
  iterations?: number
  evaluation_enabled?: boolean
  pairwise_enabled?: boolean
  // Legacy shape fields kept optional for compatibility with older callers
  name?: string
  mode?: string
  documentIds?: string[]
  config?: RunConfig
}
