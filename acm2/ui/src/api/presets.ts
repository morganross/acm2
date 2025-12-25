/**
 * Presets API client
 */
import { apiClient } from './client';

// Types
export interface ModelConfig {
  provider: string;
  model: string;
  temperature: number;
  max_tokens: number;
}

export interface GptrSettings {
  report_type: string;
  report_source: string;
  tone: string;
  max_search_results: number;
  total_words: number;
  fast_llm: string;
  smart_llm: string;
}

export interface EvaluationSettings {
  enabled: boolean;
  criteria: string[];
  eval_model: string;
}

export interface PairwiseSettings {
  enabled: boolean;
  judge_model: string;
}

export interface FpfSettings {
  prompt_template: string;
}

// ============================================================================
// Complete Config Interfaces (for full preset persistence)
// ============================================================================

export interface FpfConfigComplete {
  enabled: boolean;
  selected_models: string[];
  max_tokens: number;
  thinking_budget_tokens?: number;
  temperature: number;
  top_p: number;
  top_k: number;
  frequency_penalty: number;
  presence_penalty: number;
  stream_response: boolean;
  include_metadata: boolean;
  save_prompt_history: boolean;
  prompt_template: string;
}

export interface GptrConfigComplete {
  enabled: boolean;
  selected_models: string[];
  fast_llm_token_limit: number;
  smart_llm_token_limit: number;
  strategic_llm_token_limit: number;
  browse_chunk_max_length: number;
  summary_token_limit: number;
  temperature: number;
  max_search_results_per_query: number;
  total_words: number;
  max_iterations: number;
  max_subtopics: number;
  report_type: string;
  report_source: string;
  tone: string;
  scrape_urls: boolean;
  add_source_urls: boolean;
  verbose_mode: boolean;
  follow_links: boolean;
}

export interface DrConfigComplete {
  enabled: boolean;
  selected_models: string[];
  breadth: number;
  depth: number;
  max_results: number;
  concurrency_limit: number;
  temperature: number;
  max_tokens: number;
  timeout: number | null;
  search_provider: string;
  enable_caching: boolean;
  follow_links: boolean;
  extract_code: boolean;
  include_images: boolean;
  semantic_search: boolean;
  verbose_logging: boolean;
}

export interface MaConfigComplete {
  enabled: boolean;
  selected_models: string[];
  max_agents: number;
  communication_style: string;
  enable_consensus: boolean;
  enable_debate: boolean;
  enable_voting: boolean;
  max_rounds: number;
}

export interface EvalConfigComplete {
  enabled: boolean;
  auto_run: boolean;
  iterations: number;
  pairwise_top_n: number;
  judge_models: string[];
  timeout_seconds: number | null;  // Per-call timeout for judge LLM
  retries: number;  // Retry count for transient failures
  enable_semantic_similarity: boolean;
  enable_factual_accuracy: boolean;
  enable_coherence: boolean;
  enable_relevance: boolean;
  enable_completeness: boolean;
  enable_citation: boolean;
}

export interface PairwiseConfigComplete {
  enabled: boolean;
  judge_models: string[];
}

export interface CombineConfigComplete {
  enabled: boolean;
  selected_models: string[];
  strategy: string;
}

export interface GeneralConfigComplete {
  iterations: number;
  eval_iterations: number;
  output_dir: string;
  enable_logging: boolean;
  log_level: string;
  save_intermediate: boolean;
  fpf_log_output: string;
  fpf_log_file_path: string | null;
  post_combine_top_n: number | null;
}

export interface ConcurrencyConfigComplete {
  max_concurrent: number;
  launch_delay: number;
  enable_rate_limiting: boolean;
  generation_concurrency: number;
  eval_concurrency: number;
  request_timeout: number | null;
  eval_timeout: number | null;
}

// ============================================================================
// Request/Response Types
// ============================================================================

export interface PresetCreate {
  name: string;
  description?: string;
  documents: string[];
  
  // Complete config objects (NEW)
  general_config?: GeneralConfigComplete;
  fpf_config?: FpfConfigComplete;
  gptr_config?: GptrConfigComplete;
  dr_config?: DrConfigComplete;
  ma_config?: MaConfigComplete;
  eval_config?: EvalConfigComplete;
  pairwise_config?: PairwiseConfigComplete;
  combine_config?: CombineConfigComplete;
  concurrency_config?: ConcurrencyConfigComplete;
  
  // Logging configuration
  log_level?: string;  // ERROR, WARNING, INFO, DEBUG, VERBOSE
  
  // Content Library instruction IDs
  single_eval_instructions_id?: string;
  pairwise_eval_instructions_id?: string;
  eval_criteria_id?: string;
  combine_instructions_id?: string;
  generation_instructions_id?: string;
  
  // Legacy fields (backward compatibility)
  generators?: string[];
  models?: ModelConfig[];
  iterations?: number;
  gptr_settings?: GptrSettings;
  fpf_settings?: FpfSettings;
  evaluation?: EvaluationSettings;
  pairwise?: PairwiseSettings;
}

export interface PresetUpdate {
  name?: string;
  description?: string;
  documents?: string[];
  
  // Complete config objects (NEW)
  general_config?: GeneralConfigComplete;
  fpf_config?: FpfConfigComplete;
  gptr_config?: GptrConfigComplete;
  dr_config?: DrConfigComplete;
  ma_config?: MaConfigComplete;
  eval_config?: EvalConfigComplete;
  pairwise_config?: PairwiseConfigComplete;
  combine_config?: CombineConfigComplete;
  concurrency_config?: ConcurrencyConfigComplete;
  
  // Content Library instruction IDs
  single_eval_instructions_id?: string;
  pairwise_eval_instructions_id?: string;
  eval_criteria_id?: string;
  combine_instructions_id?: string;
  generation_instructions_id?: string;
  
  // Logging configuration
  log_level?: string;
  
  // Legacy fields
  generators?: string[];
  models?: ModelConfig[];
  iterations?: number;
  gptr_settings?: GptrSettings;
  fpf_settings?: FpfSettings;
  evaluation?: EvaluationSettings;
  pairwise?: PairwiseSettings;
}

export interface PresetResponse {
  id: string;
  name: string;
  description?: string;
  documents: string[];
  
  // Complete config objects (NEW)
  general_config?: GeneralConfigComplete;
  fpf_config?: FpfConfigComplete;
  gptr_config?: GptrConfigComplete;
  dr_config?: DrConfigComplete;
  ma_config?: MaConfigComplete;
  eval_config?: EvalConfigComplete;
  pairwise_config?: PairwiseConfigComplete;
  combine_config?: CombineConfigComplete;
  concurrency_config?: ConcurrencyConfigComplete;
  
  // Logging configuration
  log_level?: string;  // ERROR, WARNING, INFO, DEBUG, VERBOSE
  
  // Content Library instruction IDs
  single_eval_instructions_id?: string;
  pairwise_eval_instructions_id?: string;
  eval_criteria_id?: string;
  combine_instructions_id?: string;
  generation_instructions_id?: string;
  
  // Legacy fields
  generators: string[];
  models: ModelConfig[];
  iterations: number;
  gptr_settings?: GptrSettings;
  fpf_settings?: FpfSettings;
  evaluation: EvaluationSettings;
  pairwise: PairwiseSettings;
  
  created_at: string;
  updated_at?: string;
  run_count: number;
  last_run_at?: string;
}

export interface PresetSummary {
  id: string;
  name: string;
  description?: string;
  document_count: number;
  model_count: number;
  iterations: number;
  generators: string[];
  created_at: string;
  updated_at?: string;
  run_count: number;
}

export interface PresetList {
  items: PresetSummary[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

// API Functions

export async function createPreset(data: PresetCreate): Promise<PresetResponse> {
  return apiClient.post<PresetResponse>('/presets', data);
}

export async function listPresets(
  page: number = 1,
  pageSize: number = 20
): Promise<PresetList> {
  return apiClient.get<PresetList>('/presets', {
    page: page.toString(),
    page_size: pageSize.toString(),
  });
}

export async function getPreset(presetId: string): Promise<PresetResponse> {
  return apiClient.get<PresetResponse>(`/presets/${presetId}`);
}

export async function updatePreset(
  presetId: string,
  data: PresetUpdate
): Promise<PresetResponse> {
  return apiClient.put<PresetResponse>(`/presets/${presetId}`, data);
}

export async function deletePreset(
  presetId: string,
  permanent: boolean = false
): Promise<{ status: string; preset_id: string; permanent: boolean }> {
  const params = permanent ? { permanent: 'true' } : undefined;
  return apiClient.delete(`/presets/${presetId}`, params);
}

export async function duplicatePreset(
  presetId: string,
  newName: string
): Promise<PresetResponse> {
  return apiClient.post<PresetResponse>(
    `/presets/${presetId}/duplicate`,
    null,
    { new_name: newName }
  );
}

export async function executePreset(
  presetId: string
): Promise<{ status: string; run_id: string; preset_id: string; preset_name: string }> {
  return apiClient.post(`/presets/${presetId}/execute`);
}
