import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Save, RotateCcw, Sliders, Play, FileText, Library, ExternalLink } from 'lucide-react'
import { Button } from '../components/ui/button'
import { useConfigStore } from '../stores/config'
import { notify } from '@/stores/notifications'
import { runsApi } from '@/api/runs'
import { contentsApi, type ContentSummary } from '@/api/contents'
import { getConcurrencySettings } from '@/hooks/useSettings'
import { 
  listPresets, 
  createPreset, 
  updatePreset,
  getPreset,
  type PresetSummary, 
  type PresetCreate,
  type PresetResponse,
  type ModelConfig,
  type GeneralConfigComplete as GeneralConfig,
  type FpfConfigComplete as FpfConfig,
  type GptrConfigComplete as GptrConfig,
  type DrConfigComplete as DrConfig,
  type MaConfigComplete as MaConfig,
  type EvalConfigComplete as EvalConfig,
  type ConcurrencyConfigComplete as ConcurrencyConfig,
  type CombineConfigComplete as CombineConfig
} from '@/api/presets'
import {
  GeneralPanel,
  FpfParamsPanel,
  GptrParamsPanel,
  DeepResearchPanel,
  MultiAgentPanel,
  EvalPanel,
  CombinePanel,
} from '../components/config'

// Helper to parse model string "provider:model"
function parseModelString(modelStr: string): { provider: string; model: string } {
  if (modelStr.includes(':')) {
    const [provider, ...rest] = modelStr.split(':');
    return { provider, model: rest.join(':') };
  }
  return { provider: 'openai', model: modelStr };
}

// Helper to format model to "provider:model" string for UI store
function formatModelString(provider: string, model: string): string {
  return `${provider}:${model}`;
}

// ============================================================================
// Serialize Config Store -> PresetCreate (for saving)
// ============================================================================
type ConfigStore = ReturnType<typeof useConfigStore.getState>;

function serializeConfigToPreset(
  config: ConfigStore,
  presetName: string,
  selectedInputDocIds: string[],
  fpfInstructions: string,
  selectedInstructionId: string | null
): PresetCreate {
  // Build models array from FPF selected models
  const models: ModelConfig[] = config.fpf.selectedModels.map(m => {
    const { provider, model } = parseModelString(m);
    return {
      provider,
      model,
      temperature: config.fpf.temperature,
      max_tokens: config.fpf.maxTokens
    };
  });

  // Add default if no models selected but FPF enabled
  if (config.fpf.enabled && models.length === 0) {
    models.push({
      provider: 'openai',
      model: 'gpt-5',
      temperature: 0.7,
      max_tokens: 4000
    });
  }

  // Serialize GeneralConfig - get settings from localStorage
  const concurrencySettings = getConcurrencySettings();
  const general_config: GeneralConfig = {
    iterations: concurrencySettings.iterations,
    eval_iterations: concurrencySettings.evalIterations,
    output_dir: config.general.outputDir,
    enable_logging: config.general.enableLogging,
    log_level: config.general.logLevel,
    save_intermediate: config.general.saveIntermediate,
    fpf_log_output: concurrencySettings.fpfLogOutput,
    fpf_log_file_path: concurrencySettings.fpfLogFilePath,
    post_combine_top_n: concurrencySettings.postCombineTopN,
  };

  // Serialize FpfConfig
  const fpf_config: FpfConfig = {
    enabled: config.fpf.enabled,
    selected_models: config.fpf.selectedModels,
    grounding_level: config.fpf.groundingLevel,
    max_tokens: config.fpf.maxTokens,
    thinking_budget_tokens: config.fpf.thinkingBudget,
    temperature: config.fpf.temperature,
    top_p: config.fpf.topP,
    top_k: config.fpf.topK,
    frequency_penalty: config.fpf.frequencyPenalty,
    presence_penalty: config.fpf.presencePenalty,
    stream_response: config.fpf.streamResponse,
    use_grounding: config.fpf.useGrounding,
    include_metadata: config.fpf.includeMetadata,
    save_prompt_history: config.fpf.savePromptHistory,
    prompt_template: fpfInstructions,
  };

  // Serialize GptrConfig
  const gptr_config: GptrConfig = {
    enabled: config.gptr.enabled,
    selected_models: config.gptr.selectedModels,
    fast_llm_token_limit: config.gptr.fastLlmTokenLimit,
    smart_llm_token_limit: config.gptr.smartLlmTokenLimit,
    strategic_llm_token_limit: config.gptr.strategicLlmTokenLimit,
    browse_chunk_max_length: config.gptr.browseChunkMaxLength,
    summary_token_limit: config.gptr.summaryTokenLimit,
    temperature: config.gptr.temperature,
    max_search_results_per_query: config.gptr.maxSearchResultsPerQuery,
    total_words: config.gptr.totalWords,
    max_iterations: config.gptr.maxIterations,
    max_subtopics: config.gptr.maxSubtopics,
    report_type: config.gptr.reportType,
    report_source: config.gptr.reportSource,
    tone: 'Objective',
    scrape_urls: config.gptr.scrapeUrls,
    add_source_urls: config.gptr.addSourceUrls,
    verbose_mode: config.gptr.verboseMode,
    follow_links: config.gptr.followLinks,
  };

  // Serialize DrConfig
  const dr_config: DrConfig = {
    enabled: config.dr.enabled,
    selected_models: config.dr.selectedModels,
    breadth: config.dr.breadth,
    depth: config.dr.depth,
    max_results: config.dr.maxResults,
    concurrency_limit: config.dr.concurrencyLimit,
    temperature: config.dr.temperature,
    max_tokens: config.dr.maxTokens,
    timeout: config.dr.timeout,
    search_provider: config.dr.searchProvider,
    enable_caching: config.dr.enableCaching,
    follow_links: config.dr.followLinks,
    extract_code: config.dr.extractCode,
    include_images: config.dr.includeImages,
    semantic_search: config.dr.semanticSearch,
    verbose_logging: config.dr.verboseLogging,
  };

  // Serialize MaConfig
  const ma_config: MaConfig = {
    enabled: config.ma.enabled,
    selected_models: config.ma.selectedModels,
    max_agents: config.ma.maxAgents,
    communication_style: config.ma.communicationStyle,
    enable_consensus: config.ma.enableConsensus,
    enable_debate: config.ma.enableDebate,
    enable_voting: config.ma.enableVoting,
    max_rounds: config.ma.maxRounds,
  };

  // Serialize EvalConfig
  const eval_config: EvalConfig = {
    enabled: config.eval.enabled,
    auto_run: config.eval.autoRun,
    iterations: config.eval.iterations,
    pairwise_top_n: config.eval.pairwiseTopN,
    judge_models: config.eval.judgeModels,
    timeout_seconds: config.eval.timeoutSeconds,
    retries: config.eval.retries,
    enable_semantic_similarity: config.eval.enableSemanticSimilarity,
    enable_factual_accuracy: config.eval.enableFactualAccuracy,
    enable_coherence: config.eval.enableCoherence,
    enable_relevance: config.eval.enableRelevance,
    enable_completeness: config.eval.enableCompleteness,
    enable_citation: config.eval.enableCitation,
  };

  // Serialize ConcurrencyConfig
  const concurrency_config: ConcurrencyConfig = {
    max_concurrent: config.concurrency.maxConcurrent,
    launch_delay: config.concurrency.launchDelay,
    enable_rate_limiting: config.concurrency.enableRateLimiting,
    max_retries: concurrencySettings.maxRetries,
    retry_delay: concurrencySettings.retryDelay,
    generation_concurrency: concurrencySettings.generationConcurrency,
    eval_concurrency: concurrencySettings.evalConcurrency,
    request_timeout: concurrencySettings.requestTimeout,
    eval_timeout: concurrencySettings.evalTimeout,
  };

  // Serialize CombineConfig
  const combine_config: CombineConfig = {
    enabled: config.combine.enabled,
    selected_models: config.combine.selectedModels,
    strategy: 'merge',
  };

  return {
    name: presetName,
    description: 'Saved from Build Preset page',
    documents: selectedInputDocIds,
    generators: [
      config.fpf.enabled ? 'fpf' : null,
      config.gptr.enabled ? 'gptr' : null,
      config.dr.enabled ? 'dr' : null,
      config.ma.enabled ? 'ma' : null,
    ].filter((g): g is string => g !== null),
    models: models,
    iterations: config.general.iterations,
    gptr_settings: {
      report_type: config.gptr.reportType,
      report_source: config.gptr.reportSource,
      tone: 'Objective',
      max_search_results: config.gptr.maxSearchResultsPerQuery,
      total_words: config.gptr.totalWords,
      fast_llm: config.gptr.selectedModels.length > 0 ? parseModelString(config.gptr.selectedModels[0]).model : 'gpt-5-mini',
      smart_llm: config.gptr.selectedModels.length > 0 ? parseModelString(config.gptr.selectedModels[0]).model : 'gpt-5'
    },
    evaluation: {
      enabled: config.eval.enabled,
      criteria: [],
      eval_model: config.eval.judgeModels.length > 0 ? parseModelString(config.eval.judgeModels[0]).model : 'gpt-5'
    },
    pairwise: {
      // Enable pairwise when evaluation is on AND we have 2+ models to compare
      enabled: config.eval.enabled && config.fpf.selectedModels.length >= 2,
      judge_model: config.eval.judgeModels.length > 0 ? parseModelString(config.eval.judgeModels[0]).model : 'gpt-5'
    },
    pairwise_config: {
      // Also include in pairwise_config for backend consistency
      enabled: config.eval.enabled && config.fpf.selectedModels.length >= 2,
      judge_models: config.eval.judgeModels,
    },
    fpf_settings: {
      prompt_template: fpfInstructions,
    },
    // NEW: Complete config objects
    general_config,
    fpf_config,
    gptr_config,
    dr_config,
    ma_config,
    eval_config,
    concurrency_config,
    combine_config,
    // Content Library instruction IDs
    single_eval_instructions_id: config.eval.singleEvalInstructionsId || undefined,
    pairwise_eval_instructions_id: config.eval.pairwiseEvalInstructionsId || undefined,
    eval_criteria_id: config.eval.evalCriteriaId || undefined,
    combine_instructions_id: config.combine.combineInstructionsId || undefined,
    generation_instructions_id: selectedInstructionId || undefined,
    // Logging - also at top level for backend
    log_level: config.general.logLevel,
  };
}

// ============================================================================
// Deserialize PresetResponse -> Config Store (for loading)
// ============================================================================
function deserializePresetToConfig(
  preset: PresetResponse,
  config: ConfigStore
): { fpfInstructions: string; generationInstructionsId: string | null } {
  // Load GeneralConfig
  if (preset.general_config) {
    config.updateGeneral({
      iterations: preset.general_config.iterations ?? config.general.iterations,
      outputDir: preset.general_config.output_dir ?? config.general.outputDir,
      enableLogging: preset.general_config.enable_logging ?? config.general.enableLogging,
      logLevel: preset.general_config.log_level ?? config.general.logLevel,
      saveIntermediate: preset.general_config.save_intermediate ?? config.general.saveIntermediate,
    });
  } else {
    // Fallback to legacy fields
    config.updateGeneral({
      iterations: preset.iterations ?? config.general.iterations,
    });
  }

  // Load FpfConfig
  if (preset.fpf_config) {
    config.updateFpf({
      enabled: preset.fpf_config.enabled ?? preset.generators?.includes('fpf') ?? config.fpf.enabled,
      selectedModels: preset.fpf_config.selected_models ?? config.fpf.selectedModels,
      groundingLevel: preset.fpf_config.grounding_level ?? config.fpf.groundingLevel,
      maxTokens: preset.fpf_config.max_tokens ?? config.fpf.maxTokens,
      thinkingBudget: preset.fpf_config.thinking_budget_tokens ?? config.fpf.thinkingBudget,
      temperature: preset.fpf_config.temperature ?? config.fpf.temperature,
      topP: preset.fpf_config.top_p ?? config.fpf.topP,
      topK: preset.fpf_config.top_k ?? config.fpf.topK,
      frequencyPenalty: preset.fpf_config.frequency_penalty ?? config.fpf.frequencyPenalty,
      presencePenalty: preset.fpf_config.presence_penalty ?? config.fpf.presencePenalty,
      streamResponse: preset.fpf_config.stream_response ?? config.fpf.streamResponse,
      useGrounding: preset.fpf_config.use_grounding ?? config.fpf.useGrounding,
      includeMetadata: preset.fpf_config.include_metadata ?? config.fpf.includeMetadata,
      savePromptHistory: preset.fpf_config.save_prompt_history ?? config.fpf.savePromptHistory,
    });
  } else {
    // Fallback to legacy models array
    const modelNames = preset.models?.map(m => formatModelString(m.provider, m.model)) ?? config.fpf.selectedModels;
    const firstModel = preset.models?.[0];
    config.updateFpf({
      enabled: preset.generators?.includes('fpf') ?? config.fpf.enabled,
      selectedModels: modelNames,
      temperature: firstModel?.temperature ?? config.fpf.temperature,
      maxTokens: firstModel?.max_tokens ?? config.fpf.maxTokens,
      thinkingBudget: (firstModel as any)?.thinking_budget_tokens ?? config.fpf.thinkingBudget,
    });
  }

  // Load GptrConfig
  if (preset.gptr_config) {
    config.updateGptr({
      enabled: preset.gptr_config.enabled ?? preset.generators?.includes('gptr') ?? config.gptr.enabled,
      selectedModels: preset.gptr_config.selected_models ?? config.gptr.selectedModels,
      fastLlmTokenLimit: preset.gptr_config.fast_llm_token_limit ?? config.gptr.fastLlmTokenLimit,
      smartLlmTokenLimit: preset.gptr_config.smart_llm_token_limit ?? config.gptr.smartLlmTokenLimit,
      strategicLlmTokenLimit: preset.gptr_config.strategic_llm_token_limit ?? config.gptr.strategicLlmTokenLimit,
      browseChunkMaxLength: preset.gptr_config.browse_chunk_max_length ?? config.gptr.browseChunkMaxLength,
      summaryTokenLimit: preset.gptr_config.summary_token_limit ?? config.gptr.summaryTokenLimit,
      temperature: preset.gptr_config.temperature ?? config.gptr.temperature,
      maxSearchResultsPerQuery: preset.gptr_config.max_search_results_per_query ?? config.gptr.maxSearchResultsPerQuery,
      totalWords: preset.gptr_config.total_words ?? config.gptr.totalWords,
      maxIterations: preset.gptr_config.max_iterations ?? config.gptr.maxIterations,
      maxSubtopics: preset.gptr_config.max_subtopics ?? config.gptr.maxSubtopics,
      reportType: preset.gptr_config.report_type ?? config.gptr.reportType,
      reportSource: preset.gptr_config.report_source ?? config.gptr.reportSource,
      scrapeUrls: preset.gptr_config.scrape_urls ?? config.gptr.scrapeUrls,
      addSourceUrls: preset.gptr_config.add_source_urls ?? config.gptr.addSourceUrls,
      verboseMode: preset.gptr_config.verbose_mode ?? config.gptr.verboseMode,
      followLinks: preset.gptr_config.follow_links ?? config.gptr.followLinks,
    });
  } else {
    // Fallback to legacy gptr_settings
    config.updateGptr({
      enabled: preset.generators?.includes('gptr') ?? config.gptr.enabled,
      reportType: preset.gptr_settings?.report_type ?? config.gptr.reportType,
      reportSource: preset.gptr_settings?.report_source ?? config.gptr.reportSource,
    });
  }

  // Load DrConfig
  if (preset.dr_config) {
    config.updateDr({
      enabled: preset.dr_config.enabled ?? config.dr.enabled,
      selectedModels: preset.dr_config.selected_models ?? config.dr.selectedModels,
      breadth: preset.dr_config.breadth ?? config.dr.breadth,
      depth: preset.dr_config.depth ?? config.dr.depth,
      maxResults: preset.dr_config.max_results ?? config.dr.maxResults,
      concurrencyLimit: preset.dr_config.concurrency_limit ?? config.dr.concurrencyLimit,
      temperature: preset.dr_config.temperature ?? config.dr.temperature,
      maxTokens: preset.dr_config.max_tokens ?? config.dr.maxTokens,
      timeout: preset.dr_config.timeout ?? config.dr.timeout,
      searchProvider: preset.dr_config.search_provider ?? config.dr.searchProvider,
      enableCaching: preset.dr_config.enable_caching ?? config.dr.enableCaching,
      followLinks: preset.dr_config.follow_links ?? config.dr.followLinks,
      extractCode: preset.dr_config.extract_code ?? config.dr.extractCode,
      includeImages: preset.dr_config.include_images ?? config.dr.includeImages,
      semanticSearch: preset.dr_config.semantic_search ?? config.dr.semanticSearch,
      verboseLogging: preset.dr_config.verbose_logging ?? config.dr.verboseLogging,
    });
  }

  // Load MaConfig
  if (preset.ma_config) {
    config.updateMa({
      enabled: preset.ma_config.enabled ?? config.ma.enabled,
      selectedModels: preset.ma_config.selected_models ?? config.ma.selectedModels,
      maxAgents: preset.ma_config.max_agents ?? config.ma.maxAgents,
      communicationStyle: preset.ma_config.communication_style ?? config.ma.communicationStyle,
      enableConsensus: preset.ma_config.enable_consensus ?? config.ma.enableConsensus,
      enableDebate: preset.ma_config.enable_debate ?? config.ma.enableDebate,
      enableVoting: preset.ma_config.enable_voting ?? config.ma.enableVoting,
      maxRounds: preset.ma_config.max_rounds ?? config.ma.maxRounds,
    });
  }

  // Load EvalConfig
  if (preset.eval_config) {
    config.updateEval({
      enabled: preset.eval_config.enabled ?? preset.evaluation?.enabled ?? config.eval.enabled,
      autoRun: preset.eval_config.auto_run ?? config.eval.autoRun,
      iterations: preset.eval_config.iterations ?? config.eval.iterations,
      pairwiseTopN: preset.eval_config.pairwise_top_n ?? config.eval.pairwiseTopN,
      judgeModels: preset.eval_config.judge_models ?? config.eval.judgeModels,
      timeoutSeconds: preset.eval_config.timeout_seconds ?? config.eval.timeoutSeconds,
      retries: preset.eval_config.retries ?? config.eval.retries,
      enableSemanticSimilarity: preset.eval_config.enable_semantic_similarity ?? config.eval.enableSemanticSimilarity,
      enableFactualAccuracy: preset.eval_config.enable_factual_accuracy ?? config.eval.enableFactualAccuracy,
      enableCoherence: preset.eval_config.enable_coherence ?? config.eval.enableCoherence,
      enableRelevance: preset.eval_config.enable_relevance ?? config.eval.enableRelevance,
      enableCompleteness: preset.eval_config.enable_completeness ?? config.eval.enableCompleteness,
      enableCitation: preset.eval_config.enable_citation ?? config.eval.enableCitation,
    });
  } else {
    // Fallback to legacy evaluation
    config.updateEval({
      enabled: preset.evaluation?.enabled ?? config.eval.enabled,
    });
  }
  
  // Load instruction IDs from preset (top-level fields)
  config.updateEval({
    singleEvalInstructionsId: (preset as any).single_eval_instructions_id ?? null,
    pairwiseEvalInstructionsId: (preset as any).pairwise_eval_instructions_id ?? null,
    evalCriteriaId: (preset as any).eval_criteria_id ?? null,
  });

  // Load ConcurrencyConfig
  if (preset.concurrency_config) {
    config.updateConcurrency({
      maxConcurrent: preset.concurrency_config.max_concurrent ?? config.concurrency.maxConcurrent,
      launchDelay: preset.concurrency_config.launch_delay ?? config.concurrency.launchDelay,
      enableRateLimiting: preset.concurrency_config.enable_rate_limiting ?? config.concurrency.enableRateLimiting,
      maxRetries: preset.concurrency_config.max_retries ?? config.concurrency.maxRetries,
      retryDelay: preset.concurrency_config.retry_delay ?? config.concurrency.retryDelay,
    });
  }

  // Load CombineConfig
  if (preset.combine_config) {
    config.updateCombine({
      enabled: preset.combine_config.enabled ?? config.combine.enabled,
      selectedModels: preset.combine_config.selected_models ?? config.combine.selectedModels,
      combineInstructionsId: (preset as any).combine_instructions_id ?? null,
    });
  }

  // Return extra local state values
  return {
    fpfInstructions: preset.fpf_settings?.prompt_template ?? preset.fpf_config?.prompt_template ?? '',
    generationInstructionsId: (preset as any).generation_instructions_id ?? null,
  };
}

export default function Configure() {
  const navigate = useNavigate()
  const config = useConfigStore()
  
  // UI State
  const [presets, setPresets] = useState<PresetSummary[]>([])
  const [selectedPresetId, setSelectedPresetId] = useState<string>('')
  const [presetName, setPresetName] = useState('')
  
  // Run State
  const [runName, setRunName] = useState('New Run')
  const [runDescription, setRunDescription] = useState('')
  const [fpfInstructions, setFpfInstructions] = useState<string>('')  // Instructions come from preset
  const [isSubmitting, setIsSubmitting] = useState(false)
  
  // Content Library State
  const [instructionContents, setInstructionContents] = useState<ContentSummary[]>([])
  const [selectedInstructionId, setSelectedInstructionId] = useState<string | null>(null)
  const [inputDocuments, setInputDocuments] = useState<ContentSummary[]>([])
  const [selectedInputDocIds, setSelectedInputDocIds] = useState<string[]>([])

  // Load presets and content library on mount
  useEffect(() => {
    loadPresets()
    loadInstructionContents()
    loadInputDocuments()
  }, [])

  const loadPresets = async () => {
    try {
      console.log('Loading presets...')
      const result = await listPresets(1, 100)
      console.log('Loaded presets:', result)
      setPresets(result.items)
      if (result.items.length > 0 && !selectedPresetId) {
        // Don't auto-select for now
      }
    } catch (err) {
      console.error('Failed to load presets:', err)
      notify.error(`Failed to load presets: ${err}`)
    }
  }

  const loadInstructionContents = async () => {
    try {
      const items = await contentsApi.getGenerationInstructions()
      setInstructionContents(items)
    } catch (err) {
      console.error('Failed to load instruction contents:', err)
      // Don't notify, just log - content library might be empty
    }
  }

  const loadInputDocuments = async () => {
    try {
      const items = await contentsApi.getInputDocuments()
      setInputDocuments(items)
    } catch (err) {
      console.error('Failed to load input documents:', err)
    }
  }

  const handleSelectInstruction = async (contentId: string | null) => {
    setSelectedInstructionId(contentId)
    if (!contentId) {
      setFpfInstructions('')
      return
    }
    try {
      const content = await contentsApi.get(contentId)
      setFpfInstructions(content.body)
    } catch (err) {
      console.error('Failed to load instruction content:', err)
      notify.error('Failed to load instruction content')
    }
  }

  const toggleInputDoc = (docId: string) => {
    setSelectedInputDocIds(prev => 
      prev.includes(docId) 
        ? prev.filter(d => d !== docId)
        : [...prev, docId]
    )
  }

  const handleSavePreset = async () => {
    if (!presetName) {
      notify.warning('Please enter a name for the preset')
      return
    }

    try {
      // Use the new complete serialization function
      const presetData = serializeConfigToPreset(config, presetName, selectedInputDocIds, fpfInstructions, selectedInstructionId);
      
      // Check if we are updating an existing preset (by name match or ID)
      const existing = presets.find(p => p.id === selectedPresetId)
      if (existing && existing.name === presetName) {
        await updatePreset(existing.id, presetData)
        notify.success('Preset updated!')
      } else {
        const created = await createPreset(presetData)
        setSelectedPresetId(created.id)
        // Optimistically update the list
        setPresets(prev => {
            const newSummary: PresetSummary = {
                id: created.id,
                name: created.name,
                description: created.description,
                document_count: created.documents.length,
                model_count: created.models.length,
                iterations: created.iterations,
                generators: created.generators,
                created_at: created.created_at,
                updated_at: created.updated_at,
                run_count: created.run_count
            }
            return [...prev, newSummary]
        })
        notify.success('Preset created!')
      }
      
      await loadPresets()
    } catch (err) {
      console.error('Failed to save preset:', err)
      notify.error('Failed to save preset')
    }
  }

  const handlePresetChange = async (e: React.ChangeEvent<HTMLSelectElement>) => {
    const id = e.target.value
    setSelectedPresetId(id)
    
    if (!id) {
      // New preset selected - reset to defaults
      setPresetName('')
      setRunName('New Run')
      setRunDescription('')
      setSelectedInstructionId(null)
      setSelectedInputDocIds([])
      setFpfInstructions('')
      config.resetToDefaults()
      return
    }
    
    try {
      // Fetch full preset details
      const preset = await getPreset(id)
      console.log('Loaded preset details:', preset)
      
      // Update local state
      setPresetName(preset.name)
      setRunName(preset.name)
      setRunDescription(preset.description || '')
      setSelectedInputDocIds(preset.documents || [])
      
      // Use the new complete deserialization function
      const { fpfInstructions: loadedFpfInstructions, generationInstructionsId } = deserializePresetToConfig(preset, config);
      setFpfInstructions(loadedFpfInstructions);
      setSelectedInstructionId(generationInstructionsId);
      
    } catch (err) {
      console.error('Failed to load preset:', err)
      notify.error('Failed to load preset details')
    }
  }

  const handleStartRun = async () => {
    setIsSubmitting(true)
    try {
      // Construct the run request based on store + local state
      // Note: All configuration is loaded from the preset (preset_id is always provided)
      // The backend will load complete config from the preset in the database
      const runRequest = {
        title: runName,
        description: runDescription,
        preset_id: selectedPresetId || undefined,  // Link run to preset - backend loads all config from this
        documents: selectedInputDocIds,  // Input documents from Content Library
        models: config.fpf.selectedModels.length > 0 ? config.fpf.selectedModels : ['gpt-5'],
        generators: [
            config.fpf.enabled ? 'fpf' : null,
            config.gptr.enabled ? 'gptr' : null
        ].filter((g): g is string => g !== null),
        iterations: config.general.iterations,
        log_level: config.general.logLevel,  // Pass log level to run
        evaluation_enabled: config.eval.enabled,
        // Enable pairwise when we have multiple models and evaluation is on
        pairwise_enabled: config.eval.enabled && config.fpf.selectedModels.length >= 2,
        // Combine settings from config store
        combine_enabled: config.combine.enabled,
        combine_settings: {
          strategy: 'intelligent_merge',
          model: config.combine.selectedModels.length > 0 ? config.combine.selectedModels[0] : 'gpt-5',
        },
        
        fpf_settings: {
          prompt_template: fpfInstructions,
        },
        
        gptr_settings: {
          report_type: config.gptr.reportType,
          tone: 'Objective',
          retriever: config.gptr.reportSource === 'web' ? 'tavily' : config.gptr.reportSource,
        },
        
        // Instruction IDs from Content Library
        single_eval_instructions_id: config.eval.singleEvalInstructionsId,
        pairwise_eval_instructions_id: config.eval.pairwiseEvalInstructionsId,
        eval_criteria_id: config.eval.evalCriteriaId,
        combine_instructions_id: config.combine.combineInstructionsId,
        
        // NOTE: Concurrency/timeout/iteration settings come from the preset
        // No need to pass them here - backend loads full config from preset_id
      }

      const created = await runsApi.create(runRequest)
      await runsApi.start(created.id)
      // Navigate to execute page with run ID
      navigate(`/execute/${created.id}`)
    } catch (err) {
      console.error('Failed to start run:', err)
      notify.error('Failed to start run. Check console for details.')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="min-h-screen bg-gray-900 text-gray-100 flex flex-col">
      {/* Hidden page state for automation/testing */}
      <div
        data-testid="page-state"
        data-preset-id={selectedPresetId || ''}
        data-preset-name={presetName}
        data-run-name={runName}
        data-selected-instruction={selectedInstructionId || ''}
        data-selected-documents={JSON.stringify(selectedInputDocIds)}
        data-fpf-enabled={config.fpf.enabled}
        data-fpf-models={JSON.stringify(config.fpf.selectedModels)}
        data-gptr-enabled={config.gptr.enabled}
        data-gptr-models={JSON.stringify(config.gptr.selectedModels)}
        data-eval-enabled={config.eval.enabled}
        data-eval-models={JSON.stringify(config.eval.judgeModels)}
        data-combine-enabled={config.combine.enabled}
        data-combine-models={JSON.stringify(config.combine.selectedModels)}
        data-iterations={config.general.iterations}
        data-is-submitting={isSubmitting}
        className="hidden"
        aria-hidden="true"
      />
      {/* Header */}
      <div className="border-b border-gray-700 bg-gray-800/50 sticky top-0 z-10 backdrop-blur">
        <div className="max-w-7xl mx-auto px-4 py-4">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-3">
              <Sliders className="w-8 h-8 text-blue-400" />
              <div>
                <h1 className="text-2xl font-bold">Build Preset</h1>
                <p className="text-sm text-gray-400">
                  Configure parameters and save as a preset
                </p>
              </div>
            </div>
            <div className="flex gap-2">
              <Button 
                variant="primary" 
                icon={<Play className="w-4 h-4" />}
                onClick={handleStartRun}
                disabled={isSubmitting}
                className="bg-green-600 hover:bg-green-700 text-white px-6"
              >
                {isSubmitting ? 'Starting...' : 'Execute Preset'}
              </Button>
            </div>
          </div>

          {/* Run Details Inputs */}
          <div className="grid grid-cols-2 gap-4 mb-2">
            <div>
                <label htmlFor="execution-name" className="block text-xs text-gray-400 mb-1">Execution Name</label>
                <input 
                    id="execution-name"
                    name="execution-name"
                    type="text" 
                    value={runName}
                    onChange={(e) => setRunName(e.target.value)}
                    className="w-full bg-gray-900 border border-gray-700 rounded px-3 py-2 text-sm focus:border-blue-500 outline-none"
                    data-field="execution-name"
                />
            </div>
            <div>
                <label htmlFor="description" className="block text-xs text-gray-400 mb-1">Description</label>
                <input 
                    id="description"
                    name="description"
                    type="text" 
                    value={runDescription}
                    onChange={(e) => setRunDescription(e.target.value)}
                    className="w-full bg-gray-900 border border-gray-700 rounded px-3 py-2 text-sm focus:border-blue-500 outline-none"
                    placeholder="Optional description..."
                    data-field="description"
                />
            </div>
          </div>
        </div>
      </div>

      {/* Preset Selector */}
      <div className="border-b border-gray-700 bg-gray-800/30">
        <div className="max-w-7xl mx-auto px-4">
          <div className="flex items-center justify-between py-3">
            {/* Preset Selector */}
            <div className="flex items-center gap-3">
              <label htmlFor="preset-selector" className="text-sm text-gray-400">Preset:</label>
              <select
                id="preset-selector"
                name="preset-selector"
                value={selectedPresetId}
                onChange={handlePresetChange}
                className="bg-gray-700 border border-gray-600 rounded px-3 py-1.5 text-sm text-gray-200 focus:outline-none focus:border-blue-500"
                data-field="preset-selector"
              >
                <option value="">-- New Preset --</option>
                {presets.map((preset) => (
                  <option key={preset.id} value={preset.id}>
                    {preset.name}
                  </option>
                ))}
              </select>
              <input
                id="preset-name"
                name="preset-name"
                type="text"
                value={presetName}
                onChange={(e) => setPresetName(e.target.value)}
                placeholder="Preset Name"
                className="bg-gray-700 border border-gray-600 rounded px-3 py-1.5 text-sm text-gray-200 focus:outline-none focus:border-blue-500 w-48"
                data-field="preset-name"
              />
              <Button 
                variant="ghost" 
                size="sm" 
                icon={<Save className="w-4 h-4" />}
                onClick={handleSavePreset}
                data-action="save-preset"
              >
                Save
              </Button>
              <Button variant="ghost" size="sm" icon={<RotateCcw className="w-4 h-4" />} onClick={config.resetToDefaults} data-action="reset">
                Reset
              </Button>
            </div>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto">
        <div className="max-w-7xl mx-auto px-4 py-6 pb-24">

          {/* Generate / Evaluate / Combine: 3 columns, always visible */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Generate */}
            <div className="space-y-6">
              <GeneralPanel />

              <div className="bg-gray-800 border border-gray-700 rounded-lg overflow-hidden">
                <div className="p-4 border-b border-gray-700 flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <Library className="w-5 h-5 text-purple-400" />
                    <div>
                      <h3 className="font-medium">Generation Instructions</h3>
                      <p className="text-sm text-gray-400">Prepended before input document in prompt</p>
                    </div>
                  </div>
                  <a 
                    href="/content" 
                    target="_blank"
                    className="inline-flex items-center gap-1 px-2 py-1 text-xs bg-gray-700 hover:bg-gray-600 rounded transition-colors"
                  >
                    <ExternalLink className="w-3 h-3" />
                    Library
                  </a>
                </div>

                <div className="p-4">
                  {instructionContents.length === 0 ? (
                    <p className="text-xs text-gray-500">No generation instructions in library</p>
                  ) : (
                    <select
                      value={selectedInstructionId || ''}
                      onChange={(e) => handleSelectInstruction(e.target.value || null)}
                      className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-purple-500"
                      data-testid="generation-instructions-select"
                    >
                      <option value="">-- No Instructions --</option>
                      {instructionContents.map((content) => (
                        <option key={content.id} value={content.id}>{content.name}</option>
                      ))}
                    </select>
                  )}
                </div>
              </div>

              {/* Input Documents Section */}
              <div className="bg-gray-800 border border-gray-700 rounded-lg overflow-hidden">
                <div className="p-4 border-b border-gray-700 flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <FileText className="w-5 h-5 text-blue-400" />
                    <div>
                      <h3 className="font-medium">Input Documents</h3>
                      <p className="text-sm text-gray-400">Select documents to process</p>
                    </div>
                  </div>
                  <a 
                    href="/content" 
                    target="_blank"
                    className="inline-flex items-center gap-2 px-3 py-1.5 bg-gray-700 hover:bg-gray-600 rounded text-sm transition-colors"
                  >
                    <ExternalLink className="w-4 h-4" />
                    Add Documents
                  </a>
                </div>

                <div className="p-4">
                  {inputDocuments.length === 0 ? (
                    <div className="text-center py-6 text-gray-400">
                      <FileText className="w-8 h-8 mx-auto mb-2 opacity-50" />
                      <p className="text-sm">No input documents in library</p>
                      <a href="/content" className="text-blue-400 hover:text-blue-300 text-sm mt-1 inline-block">
                        Create one in Content Library →
                      </a>
                    </div>
                  ) : (
                    <div className="grid gap-2 max-h-48 overflow-y-auto">
                      {inputDocuments.map((doc) => (
                        <label
                          key={doc.id}
                          data-testid={`input-doc-${doc.id}`}
                          className={`flex items-center gap-3 p-3 rounded-lg cursor-pointer transition-colors ${
                            selectedInputDocIds.includes(doc.id)
                              ? 'bg-blue-500/20 border border-blue-500'
                              : 'bg-gray-700/50 border border-transparent hover:bg-gray-700'
                          }`}
                        >
                          <input
                            type="checkbox"
                            checked={selectedInputDocIds.includes(doc.id)}
                            onChange={() => toggleInputDoc(doc.id)}
                            className="w-4 h-4 rounded border-gray-600 text-blue-600 focus:ring-blue-500 bg-gray-700"
                          />
                          <FileText className="w-5 h-5 text-blue-400" />
                          <div className="flex-1 min-w-0">
                            <div className="font-medium text-gray-200">{doc.name}</div>
                            <div className="text-xs text-gray-500 line-clamp-1">{doc.body_preview}</div>
                          </div>
                        </label>
                      ))}
                    </div>
                  )}
                </div>
              </div>

              <FpfParamsPanel />
              <GptrParamsPanel />
              <DeepResearchPanel />
              <MultiAgentPanel />
            </div>

            {/* Evaluate */}
            <div className="space-y-6">
              <EvalPanel />
            </div>

            {/* Combine */}
            <div className="space-y-6">
              <CombinePanel />
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
