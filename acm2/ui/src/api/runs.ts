import { apiClient } from './client'

// Types matching backend schemas
export interface RunConfig {
  title: string
  description?: string
  documents: string[]
  models: string[]
  generators: string[]
  iterations: number
  evaluation_enabled: boolean
  pairwise_enabled: boolean
  log_level?: string
  config_overrides?: Record<string, unknown>
}

export interface GeneratedDocInfo {
  id: string
  model: string
  source_doc_id: string
  generator: string
  iteration: number
  cost_usd?: number
}

export interface PairwiseRanking {
  doc_id: string
  wins: number
  losses: number
  elo: number
}

export interface PairwiseComparison {
  doc_id_a: string
  doc_id_b: string
  winner: string  // doc_id of winner
  judge_model: string
  trial?: number
  reason: string
}

export interface PairwiseResults {
  total_comparisons: number
  winner_doc_id?: string
  rankings: PairwiseRanking[]
  comparisons?: PairwiseComparison[]  // ACM1-style head-to-head comparisons
}

// ============================================================================
// ACM1-Style Timeline & Generation Events
// ============================================================================

export type TimelinePhase =
  | 'initialization'
  | 'generation'
  | 'evaluation'
  | 'pairwise'
  | 'combination'
  | 'completion'

export interface TimelineEvent {
  phase: TimelinePhase
  event_type: string
  description: string
  model?: string | null
  timestamp?: string | null
  completed_at?: string | null  // ISO timestamp for end time
  duration_seconds?: number | null
  success?: boolean
  details?: Record<string, unknown> | null
}

export interface GenerationEvent {
  doc_id: string
  generator: string  // fpf, gptr, dr
  model?: string | null  // provider:model
  source_doc_id?: string | null
  iteration?: number
  duration_seconds?: number | null
  cost_usd?: number | null
  success?: boolean
  status?: 'pending' | 'running' | 'completed' | 'failed'
  error?: string
  token_count?: number
  started_at?: string | null  // ISO timestamp
  completed_at?: string | null  // ISO timestamp
}

// ============================================================================
// ACM1-Style Detailed Evaluation Types
// ============================================================================

export interface CriterionScoreInfo {
  criterion: string
  score: number  // 1-5 scale
  reason: string  // Evaluator's rationale/explanation
}

export interface JudgeEvaluation {
  judge_model: string
  trial: number
  scores: CriterionScoreInfo[]  // Score per criterion
  average_score: number
}

export interface DocumentEvalDetail {
  evaluations: JudgeEvaluation[]  // All evaluations by all judges
  overall_average: number
}

export interface FpfStats {
  total_calls: number
  successful_calls: number
  failed_calls: number
  retries: number
  current_phase?: string
  current_call?: string
  last_error?: string
}

// ============================================================================
// Per-Source-Document Results (Multi-Doc Pipeline)
// ============================================================================

export type SourceDocStatus =
  | 'pending'
  | 'generating'
  | 'single_eval'
  | 'pairwise_eval'
  | 'combining'
  | 'post_combine_eval'
  | 'completed'
  | 'completed_with_errors'
  | 'failed'
  | 'cancelled'

export interface SourceDocResult {
  source_doc_id: string
  source_doc_name: string
  status: SourceDocStatus
  
  // Generated documents for this source
  generated_docs: GeneratedDocInfo[]
  
  // Evaluation results
  single_eval_scores: Record<string, number>  // { gen_doc_id: avg_score }
  single_eval_detailed?: Record<string, DocumentEvalDetail>
  pairwise_results?: PairwiseResults
  
  // Winner and combined output
  winner_doc_id?: string
  combined_doc?: GeneratedDocInfo  // Legacy: first combined doc
  combined_docs?: GeneratedDocInfo[]  // All combined docs
  
  // Post-combine evaluation
  post_combine_eval_scores?: Record<string, number>
  post_combine_pairwise?: PairwiseResults
  
  // Timeline events for this source doc
  timeline_events?: TimelineEvent[]
  
  // Per-document stats
  errors: string[]
  cost_usd: number
  duration_seconds: number
  started_at?: string
  completed_at?: string
}

export interface Run {
  id: string
  title: string
  name?: string
  description?: string
  status: 'pending' | 'running' | 'paused' | 'completed' | 'failed' | 'cancelled'
  mode?: string
  preset_id?: string
  log_level?: string  // Log level: ERROR, WARNING, INFO, DEBUG, VERBOSE
  config: RunConfig
  progress: {
    total_tasks: number
    completed_tasks: number
    failed_tasks: number
    current_task?: string
  }
  fpf_stats?: FpfStats
  tasks?: any[]
  current_phase?: string
  created_at: string
  started_at?: string
  completed_at?: string
  // Compatibility fields
  documentCount?: number
  modelCount?: number
  createdAt?: string
  completedAt?: string
  error_message?: string
  // Legacy evaluation results format
  eval_scores?: Record<string, Record<string, number>>  // { source_doc_id: { gen_model: score } }
  winner?: string
  // New structured evaluation data for heatmaps
  generated_docs?: GeneratedDocInfo[]  // List of generated documents
  pre_combine_evals?: any[]  // Array of evaluation results for UI accumulation
  post_combine_evals?: Record<string, Record<string, number>>  // { combined_doc_id: { judge_model: score } }
  pairwise_results?: PairwiseResults
  post_combine_pairwise?: PairwiseResults  // Pairwise comparison: combined doc vs winner
  combined_doc_id?: string  // Legacy: first combined doc ID
  combined_doc_ids?: string[]  // All combined document IDs
  // ACM1-style detailed evaluation data with criteria breakdown
  pre_combine_evals_detailed?: Record<string, DocumentEvalDetail>  // { gen_doc_id: DocumentEvalDetail }
  post_combine_evals_detailed?: Record<string, DocumentEvalDetail>  // { combined_doc_id: DocumentEvalDetail }
  criteria_list?: string[]  // All criteria used
  evaluator_list?: string[]  // All evaluator model names
  // ACM1-style timeline and generation events
  timeline_events?: TimelineEvent[]  // All timeline events
  generation_events?: GenerationEvent[]  // Generation event records
  // === NEW: Per-source-document results (multi-doc pipeline) ===
  source_doc_results?: Record<string, SourceDocResult>  // { source_doc_id: SourceDocResult }
  // UI-specific fields
  duration_seconds?: number // For running time display
}
export interface CreateRunRequest {
  title: string
  description?: string
  preset_id?: string  // Link to preset
  log_level?: string  // INFO, DEBUG, VERBOSE, etc.
  documents: string[]
  // Models can be provided as simple strings (e.g. 'openai:gpt-4o') or full objects
  models: (string | { provider: string; model: string; temperature?: number; max_tokens?: number; thinking_budget_tokens?: number })[]
  generators?: string[]
  iterations?: number
  evaluation_enabled?: boolean
  pairwise_enabled?: boolean
  combine_enabled?: boolean
  combine_settings?: {
    strategy?: string
    model?: string
  }
  fpf_settings?: {
    prompt_template?: string
  }
  gptr_settings?: {
    report_type?: string
    tone?: string
    retriever?: string
  }
}

export const runsApi = {
  // List all runs with optional filters
  async list(params?: { status?: string; limit?: number; offset?: number }): Promise<Run[]> {
    const query = new URLSearchParams()
    if (params?.status) query.set('status', params.status)
    if (params?.limit) query.set('limit', params.limit.toString())
    if (params?.offset) query.set('offset', params.offset.toString())
    const queryString = query.toString()
    const resp = await apiClient.get<{ items: any[]; total: number; page: number; page_size: number; pages: number }>(`/runs${queryString ? `?${queryString}` : ''}`)
    // API returns paginated response with items array
    return (resp.items || []).map(runsApi.mapRun)
  },

  // Get a single run by ID
  async get(id: string): Promise<Run> {
    const resp = await apiClient.get<any>(`/runs/${id}`)
    return runsApi.mapRun(resp)
  },

  // Helper: Map backend Run shape into UI Run
  mapRun: (r: any): Run => {
    const tasks = r.tasks || []
    const total = tasks.length
    const completed = tasks.filter((t: any) => t.status === 'completed').length
    const failed = tasks.filter((t: any) => t.status === 'failed').length

    return {
      id: r.id,
      title: r.name,
      name: r.name,
      description: r.description,
      status: r.status,
      preset_id: r.preset_id,
      log_level: r.log_level,  // Include log_level from API response
      // Compatibility fields expected by UI components
      documentCount: r.document_count || (r.document_ids ? r.document_ids.length : 0),
      modelCount: r.model_count || (r.models ? r.models.length : 0),
      createdAt: r.created_at,
      created_at: r.created_at,
      completedAt: r.completed_at,
      completed_at: r.completed_at,
      started_at: r.started_at,
      config: {
        title: r.name,
        description: r.description,
        documents: r.document_ids,
        models: (r.models || []).map((m: any) => m.provider ? `${m.provider}:${m.model}` : m),
        generators: (r.generators || []),
        iterations: r.iterations,
        evaluation_enabled: r.evaluation?.enabled ?? true,
        pairwise_enabled: r.pairwise?.enabled ?? false,
      },
      // Backwards compatible mode field - default to full
      mode: 'full',
      progress: typeof r.progress === 'number' ? {
        total_tasks: total,
        completed_tasks: completed,
        failed_tasks: failed,
        current_task: tasks.find((t: any) => t.status === 'running')?.name
      } : r.progress,
      tasks: r.tasks,
      current_phase: r.status === 'running' ? 'Processing' : undefined,
      error_message: r.error_message,
      // Legacy evaluation results for heatmap display
      eval_scores: r.eval_scores || {},
      winner: r.winner,
      // New structured evaluation data
      generated_docs: r.generated_docs || [],
      pre_combine_evals: r.pre_combine_evals || [],
      post_combine_evals: r.post_combine_evals || {},
      pairwise_results: r.pairwise_results,
      post_combine_pairwise: r.post_combine_pairwise,  // Post-combine pairwise: combined doc vs winner
      combined_doc_id: r.combined_doc_id,
      // ACM1-style detailed evaluation data
      pre_combine_evals_detailed: r.pre_combine_evals_detailed || {},
      post_combine_evals_detailed: r.post_combine_evals_detailed || {},
      criteria_list: r.criteria_list || [],
      evaluator_list: r.evaluator_list || [],
      // ACM1-style timeline and generation events
      timeline_events: r.timeline_events || [],
      generation_events: r.generation_events || [],
      // Per-source-document results (multi-doc pipeline)
      source_doc_results: r.source_doc_results || {},
    }
  },


  // Create a new run
  async create(data: CreateRunRequest): Promise<Run> {
    // Map UI-friendly payload into backend RunCreate shape
    const mapModel = (m: string | { provider: string; model: string; temperature?: number; max_tokens?: number; thinking_budget_tokens?: number }) => {
      if (typeof m === 'string') {
        if (m.includes(':')) {
          const [provider, model] = m.split(':', 2)
          return { provider, model }
        }
        return { provider: 'openai', model: m }
      }
      return {
        provider: m.provider,
        model: m.model,
        ...(m.temperature !== undefined ? { temperature: m.temperature } : {}),
        ...(m.max_tokens !== undefined ? { max_tokens: m.max_tokens } : {}),
        ...(m.thinking_budget_tokens !== undefined ? { thinking_budget_tokens: m.thinking_budget_tokens } : {}),
      }
    }

    const payload: any = {
      name: data.title,
      description: data.description,
      preset_id: data.preset_id,  // Link run to preset
      log_level: data.log_level || 'INFO',  // Pass log level
      document_ids: data.documents,
      generators: (data.generators && data.generators.length > 0) ? data.generators : ['gptr'],
      models: data.models.map(mapModel),
      iterations: data.iterations || 1,
      gptr_settings: {
        report_type: data.gptr_settings?.report_type || 'research_report',
        report_source: 'web',
        tone: data.gptr_settings?.tone || 'Objective',
        max_search_results: 5,
        total_words: 1000,
        fast_llm: 'gpt-4o-mini',
        smart_llm: 'gpt-4o',
      },
      fpf_config: {
        prompt_template: data.fpf_settings?.prompt_template || '',  // Instructions from preset, no fallback
      },
      evaluation: {
        enabled: data.evaluation_enabled ?? true,
        criteria: ['accuracy','completeness','coherence'],
        eval_model: 'gpt-4o',
      },
      pairwise: {
        enabled: data.pairwise_enabled ?? false,
        judge_model: 'gpt-4o',
      },
      combine: {
        enabled: data.combine_enabled ?? false,
        strategy: data.combine_settings?.strategy || 'intelligent_merge',
        model: data.combine_settings?.model || 'gpt-4o',
      },
      tags: [],
    }

    const resp = await apiClient.post<any>('/runs', payload)
    return runsApi.mapRun(resp)
  },

  // Start a run
  async start(id: string): Promise<Run> {
    const resp = await apiClient.post<any>(`/runs/${id}/start`)
    return runsApi.mapRun(resp)
  },

  // Pause a run
  async pause(id: string): Promise<Run> {
    const resp = await apiClient.post<any>(`/runs/${id}/pause`)
    return runsApi.mapRun(resp)
  },

  // Cancel a running run
  async cancel(id: string): Promise<Run> {
    const resp = await apiClient.post<any>(`/runs/${id}/cancel`)
    return runsApi.mapRun(resp)
  },

  // Delete a run
  async delete(id: string): Promise<void> {
    return apiClient.delete<void>(`/runs/${id}`)
  },

  async bulkDelete(target: 'failed' | 'completed_failed'): Promise<{ deleted: number; target: string }> {
    return apiClient.delete<{ deleted: number; target: string }>(`/runs/bulk`, { target })
  },

  async progress(id: string): Promise<Run['progress']> {
    const run = await this.get(id)
    return run.progress
  },
}
