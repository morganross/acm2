// config.ts - RunConfig store (all settings)
// Default configuration matching ACM 1.0 defaults

import { create } from 'zustand'

// ============================================================================
// FPF (FilePromptForge) Configuration
// ============================================================================
interface FpfConfig {
  enabled: boolean
  selectedModels: string[]
  groundingLevel: number
  maxTokens: number
  thinkingBudget: number
  temperature: number
  topP: number
  topK: number
  frequencyPenalty: number
  presencePenalty: number
  streamResponse: boolean
  useGrounding: boolean
  includeMetadata: boolean
  savePromptHistory: boolean
}

// ============================================================================
// GPTR (GPT-Researcher) Configuration
// ============================================================================
interface GptrConfig {
  enabled: boolean
  selectedModels: string[]
  fastLlmTokenLimit: number
  smartLlmTokenLimit: number
  strategicLlmTokenLimit: number
  browseChunkMaxLength: number
  summaryTokenLimit: number
  temperature: number
  maxSearchResultsPerQuery: number
  totalWords: number
  maxIterations: number
  maxSubtopics: number
  reportType: string
  reportSource: string
  scrapeUrls: boolean
  addSourceUrls: boolean
  verboseMode: boolean
  followLinks: boolean
}

// ============================================================================
// DR (Deep Research) Configuration
// ============================================================================
interface DrConfig {
  enabled: boolean
  selectedModels: string[]
  breadth: number
  depth: number
  maxResults: number
  concurrencyLimit: number
  temperature: number
  maxTokens: number
  timeout: number
  searchProvider: string
  enableCaching: boolean
  followLinks: boolean
  extractCode: boolean
  includeImages: boolean
  semanticSearch: boolean
  verboseLogging: boolean
}

// ============================================================================
// MA (Multi-Agent) Configuration
// ============================================================================
interface MaConfig {
  enabled: boolean
  selectedModels: string[]
  maxAgents: number
  communicationStyle: string
  enableConsensus: boolean
  enableDebate: boolean
  enableVoting: boolean
  maxRounds: number
}

// ============================================================================
// Eval Configuration
// ============================================================================
interface EvalConfig {
  enabled: boolean
  autoRun: boolean
  iterations: number
  pairwiseTopN: number
  judgeModels: string[]
  timeoutSeconds: number  // Per-call timeout for judge LLM
  retries: number  // Retry count for transient failures
  enableSemanticSimilarity: boolean
  enableFactualAccuracy: boolean
  enableCoherence: boolean
  enableRelevance: boolean
  enableCompleteness: boolean
  enableCitation: boolean
  // Content Library instruction IDs
  singleEvalInstructionsId: string | null
  pairwiseEvalInstructionsId: string | null
  evalCriteriaId: string | null
}

// ============================================================================
// Concurrency Configuration
// ============================================================================
interface ConcurrencyConfig {
  maxConcurrent: number
  launchDelay: number
  enableRateLimiting: boolean
  maxRetries: number
  retryDelay: number
}

// ============================================================================
// Combine Configuration
// ============================================================================
interface CombineConfig {
  enabled: boolean
  selectedModels: string[]
  // Content Library instruction ID
  combineInstructionsId: string | null
}

// ============================================================================
// General Run Configuration
// ============================================================================
interface GeneralConfig {
  iterations: number
  outputDir: string
  enableLogging: boolean
  logLevel: string
  saveIntermediate: boolean
}

// ============================================================================
// Full Config Store Interface
// ============================================================================
interface ConfigState {
  general: GeneralConfig
  fpf: FpfConfig
  gptr: GptrConfig
  dr: DrConfig
  ma: MaConfig
  eval: EvalConfig
  concurrency: ConcurrencyConfig
  combine: CombineConfig
  
  // Update methods
  updateGeneral: (updates: Partial<GeneralConfig>) => void
  updateFpf: (updates: Partial<FpfConfig>) => void
  updateGptr: (updates: Partial<GptrConfig>) => void
  updateDr: (updates: Partial<DrConfig>) => void
  updateMa: (updates: Partial<MaConfig>) => void
  updateEval: (updates: Partial<EvalConfig>) => void
  updateConcurrency: (updates: Partial<ConcurrencyConfig>) => void
  updateCombine: (updates: Partial<CombineConfig>) => void
  resetToDefaults: () => void
}

// ============================================================================
// Default Values (matching ACM 1.0)
// ============================================================================
const defaultGeneral: GeneralConfig = {
  iterations: 3,
  outputDir: './output',
  enableLogging: true,
  logLevel: 'INFO',
  saveIntermediate: true,
}

const defaultFpf: FpfConfig = {
  enabled: true,
  selectedModels: [],  // REQUIRED from preset - no hardcoded default
  groundingLevel: 5,
  maxTokens: 32000,
  thinkingBudget: 2048,
  temperature: 0.7,
  topP: 0.95,
  topK: 40,
  frequencyPenalty: 0.0,
  presencePenalty: 0.0,
  streamResponse: true,
  useGrounding: true,
  includeMetadata: true,
  savePromptHistory: true,
}

const defaultGptr: GptrConfig = {
  enabled: true,
  selectedModels: [],  // REQUIRED from preset - no hardcoded default
  fastLlmTokenLimit: 4000,
  smartLlmTokenLimit: 8000,
  strategicLlmTokenLimit: 16000,
  browseChunkMaxLength: 8000,
  summaryTokenLimit: 2000,
  temperature: 0.4,
  maxSearchResultsPerQuery: 5,
  totalWords: 3000,
  maxIterations: 4,
  maxSubtopics: 5,
  reportType: 'research_report',
  reportSource: 'web',
  scrapeUrls: true,
  addSourceUrls: true,
  verboseMode: false,
  followLinks: true,
}

const defaultDr: DrConfig = {
  enabled: true,
  selectedModels: [],  // REQUIRED from preset - no hardcoded default
  breadth: 4,
  depth: 3,
  maxResults: 10,
  concurrencyLimit: 5,
  temperature: 0.5,
  maxTokens: 16000,
  timeout: 600, // Increased from 300 to handle slow LLM evaluations
  searchProvider: 'tavily',
  enableCaching: true,
  followLinks: true,
  extractCode: true,
  includeImages: false,
  semanticSearch: true,
  verboseLogging: false,
}

const defaultMa: MaConfig = {
  enabled: false,
  selectedModels: [],  // REQUIRED from preset - no hardcoded default
  maxAgents: 3,
  communicationStyle: 'sequential',
  enableConsensus: true,
  enableDebate: false,
  enableVoting: false,
  maxRounds: 3,
}

const defaultEval: EvalConfig = {
  enabled: true,
  autoRun: true,
  iterations: 3,
  pairwiseTopN: 5,
  judgeModels: [],  // REQUIRED from preset - no hardcoded default
  timeoutSeconds: 600,  // 10 min per-call timeout
  retries: 3,  // Retry count for transient failures
  enableSemanticSimilarity: true,
  enableFactualAccuracy: true,
  enableCoherence: true,
  enableRelevance: true,
  enableCompleteness: true,
  enableCitation: false,
  singleEvalInstructionsId: null,
  pairwiseEvalInstructionsId: null,
  evalCriteriaId: null,
}

const defaultConcurrency: ConcurrencyConfig = {
  maxConcurrent: 5,
  launchDelay: 1.0,
  enableRateLimiting: true,
  maxRetries: 3,
  retryDelay: 2.0,
}

const defaultCombine: CombineConfig = {
  enabled: true,
  selectedModels: [],  // REQUIRED from preset - no hardcoded default
  combineInstructionsId: null,
}

// ============================================================================
// Zustand Store
// ============================================================================
export const useConfigStore = create<ConfigState>((set) => ({
  general: { ...defaultGeneral },
  fpf: { ...defaultFpf },
  gptr: { ...defaultGptr },
  dr: { ...defaultDr },
  ma: { ...defaultMa },
  eval: { ...defaultEval },
  concurrency: { ...defaultConcurrency },
  combine: { ...defaultCombine },

  updateGeneral: (updates) =>
    set((state) => ({ general: { ...state.general, ...updates } })),
  
  updateFpf: (updates) =>
    set((state) => ({ fpf: { ...state.fpf, ...updates } })),
  
  updateGptr: (updates) =>
    set((state) => ({ gptr: { ...state.gptr, ...updates } })),
  
  updateDr: (updates) =>
    set((state) => ({ dr: { ...state.dr, ...updates } })),
  
  updateMa: (updates) =>
    set((state) => ({ ma: { ...state.ma, ...updates } })),
  
  updateEval: (updates) =>
    set((state) => ({ eval: { ...state.eval, ...updates } })),
  
  updateConcurrency: (updates) =>
    set((state) => ({ concurrency: { ...state.concurrency, ...updates } })),
  
  updateCombine: (updates) =>
    set((state) => ({ combine: { ...state.combine, ...updates } })),

  resetToDefaults: () =>
    set({
      general: { ...defaultGeneral },
      fpf: { ...defaultFpf },
      gptr: { ...defaultGptr },
      dr: { ...defaultDr },
      ma: { ...defaultMa },
      eval: { ...defaultEval },
      concurrency: { ...defaultConcurrency },
      combine: { ...defaultCombine },
    }),
}))