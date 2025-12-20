# ACM2 PRESET PERSISTENCE: COMPLETE IMPLEMENTATION PLAN

**Document Version:** 1.0  
**Date:** December 13, 2025  
**Author:** Development Team  
**Status:** Ready for Implementation  
**Estimated Effort:** 8-12 hours  

---

# TABLE OF CONTENTS

1. [Executive Summary](#1-executive-summary)
2. [Current State Analysis](#2-current-state-analysis)
3. [Target State Architecture](#3-target-state-architecture)
4. [Implementation Phases](#4-implementation-phases)
5. [Phase 1: Backend Schema Updates](#5-phase-1-backend-schema-updates)
6. [Phase 2: Frontend API Types](#6-phase-2-frontend-api-types)
7. [Phase 3: Save Implementation](#7-phase-3-save-implementation)
8. [Phase 4: Load Implementation](#8-phase-4-load-implementation)
9. [Phase 5: Testing Strategy](#9-phase-5-testing-strategy)
10. [Rollout Plan](#10-rollout-plan)

---

# 1. EXECUTIVE SUMMARY

## 1.1 Problem Statement

The ACM2 Build Preset page allows users to configure ~77 distinct settings across 7 configuration sections. Currently, only ~10 of these settings are persisted when saving a preset. This means 87% of user configuration is lost on save/reload.

## 1.2 Business Impact

- Users cannot reliably save and reuse configurations
- Every preset load requires manual reconfiguration
- Defeats the core value proposition of presets
- Creates frustration and wastes user time

## 1.3 Solution Overview

Implement complete bidirectional serialization between:
- **Zustand Config Store** (frontend state)
- **Preset API** (network transport)
- **SQLite Database** (persistent storage)

## 1.4 Success Criteria

After implementation:
1. User configures ANY field on Build Preset page
2. User saves preset
3. User closes browser, reopens, loads preset
4. ALL fields are restored exactly as configured
5. 100% round-trip fidelity for all 77 fields

---

# 2. CURRENT STATE ANALYSIS

## 2.1 Configuration Sections Inventory

| Section | UI Component | Store Namespace | Total Fields | Currently Saved | Gap |
|---------|--------------|-----------------|--------------|-----------------|-----|
| General | GeneralPanel | `config.general` | 5 | 1 | 4 |
| FPF | FpfParamsPanel | `config.fpf` | 18 | 4 | 14 |
| GPTR | GptrParamsPanel | `config.gptr` | 16 | 4 | 12 |
| Deep Research | DeepResearchPanel | `config.dr` | 16 | 0 | 16 |
| Multi-Agent | MultiAgentPanel | `config.ma` | 8 | 0 | 8 |
| Evaluation | EvalPanel | `config.eval` | 12 | 1 | 11 |
| Combine | CombinePanel | `config.combine` | 2 | 0 | 2 |
| **TOTAL** | | | **77** | **10** | **67** |

## 2.2 Detailed Field Inventory

### 2.2.1 General Settings (5 fields)
```typescript
interface GeneralConfig {
  iterations: number        // ✅ SAVED
  outputDir: string         // ❌ NOT SAVED
  enableLogging: boolean    // ❌ NOT SAVED
  logLevel: string          // ❌ NOT SAVED
  saveIntermediate: boolean // ❌ NOT SAVED
}
```

### 2.2.2 FPF Settings (18 fields)
```typescript
interface FpfConfig {
  enabled: boolean           // ✅ SAVED (via generators[])
  selectedModels: string[]   // ✅ SAVED (as models[])
  groundingLevel: number     // ❌ NOT SAVED
  maxTokens: number          // ✅ SAVED
  temperature: number        // ✅ SAVED
  topP: number               // ❌ NOT SAVED
  topK: number               // ❌ NOT SAVED
  frequencyPenalty: number   // ❌ NOT SAVED
  presencePenalty: number    // ❌ NOT SAVED
  streamResponse: boolean    // ❌ NOT SAVED
  useGrounding: boolean      // ❌ NOT SAVED
  includeMetadata: boolean   // ❌ NOT SAVED
  savePromptHistory: boolean // ❌ NOT SAVED
}
```

### 2.2.3 GPTR Settings (16 fields)
```typescript
interface GptrConfig {
  enabled: boolean              // ✅ SAVED (via generators[])
  selectedModels: string[]      // ❌ NOT SAVED (only fast_llm/smart_llm)
  fastLlmTokenLimit: number     // ❌ NOT SAVED
  smartLlmTokenLimit: number    // ❌ NOT SAVED
  strategicLlmTokenLimit: number // ❌ NOT SAVED
  browseChunkMaxLength: number  // ❌ NOT SAVED
  summaryTokenLimit: number     // ❌ NOT SAVED
  temperature: number           // ❌ NOT SAVED
  maxSearchResultsPerQuery: number // ✅ SAVED
  totalWords: number            // ✅ SAVED
  maxIterations: number         // ❌ NOT SAVED
  maxSubtopics: number          // ❌ NOT SAVED
  reportType: string            // ✅ SAVED
  reportSource: string          // ✅ SAVED
  scrapeUrls: boolean           // ❌ NOT SAVED
  addSourceUrls: boolean        // ❌ NOT SAVED
  verboseMode: boolean          // ❌ NOT SAVED
  followLinks: boolean          // ❌ NOT SAVED
}
```

### 2.2.4 Deep Research Settings (16 fields)
```typescript
interface DrConfig {
  enabled: boolean          // ❌ NOT SAVED
  selectedModels: string[]  // ❌ NOT SAVED
  breadth: number           // ❌ NOT SAVED
  depth: number             // ❌ NOT SAVED
  maxResults: number        // ❌ NOT SAVED
  concurrencyLimit: number  // ❌ NOT SAVED
  temperature: number       // ❌ NOT SAVED
  maxTokens: number         // ❌ NOT SAVED
  timeout: number           // ❌ NOT SAVED
  searchProvider: string    // ❌ NOT SAVED
  enableCaching: boolean    // ❌ NOT SAVED
  followLinks: boolean      // ❌ NOT SAVED
  extractCode: boolean      // ❌ NOT SAVED
  includeImages: boolean    // ❌ NOT SAVED
  semanticSearch: boolean   // ❌ NOT SAVED
  verboseLogging: boolean   // ❌ NOT SAVED
}
```

### 2.2.5 Multi-Agent Settings (8 fields)
```typescript
interface MaConfig {
  enabled: boolean             // ❌ NOT SAVED
  selectedModels: string[]     // ❌ NOT SAVED
  maxAgents: number            // ❌ NOT SAVED
  communicationStyle: string   // ❌ NOT SAVED
  enableConsensus: boolean     // ❌ NOT SAVED
  enableDebate: boolean        // ❌ NOT SAVED
  enableVoting: boolean        // ❌ NOT SAVED
  maxRounds: number            // ❌ NOT SAVED
}
```

### 2.2.6 Evaluation Settings (12 fields)
```typescript
interface EvalConfig {
  enabled: boolean                 // ✅ SAVED
  autoRun: boolean                 // ❌ NOT SAVED
  iterations: number               // ❌ NOT SAVED
  pairwiseTopN: number             // ❌ NOT SAVED
  judgeModels: string[]            // ❌ NOT SAVED (only first as eval_model)
  enableSemanticSimilarity: boolean // ❌ NOT SAVED
  enableFactualAccuracy: boolean   // ❌ NOT SAVED
  enableCoherence: boolean         // ❌ NOT SAVED
  enableRelevance: boolean         // ❌ NOT SAVED
  enableCompleteness: boolean      // ❌ NOT SAVED
  enableCitation: boolean          // ❌ NOT SAVED
}
```

### 2.2.7 Combine Settings (2 fields)
```typescript
interface CombineConfig {
  enabled: boolean          // ❌ NOT SAVED
  selectedModels: string[]  // ❌ NOT SAVED
}
```

## 2.3 Current Data Flow

```
┌──────────────────────────────────────────────────────────────────┐
│                        CURRENT FLOW                               │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│  UI State (77 fields)                                            │
│       │                                                          │
│       ▼                                                          │
│  handleSavePreset() ──── Only extracts 10 fields ────►           │
│       │                                                          │
│       ▼                                                          │
│  PresetCreate object (10 fields)                                 │
│       │                                                          │
│       ▼                                                          │
│  POST /api/v1/presets                                            │
│       │                                                          │
│       ▼                                                          │
│  Backend saves to DB (10 fields stored)                          │
│       │                                                          │
│       ▼                                                          │
│  GET /api/v1/presets/:id                                         │
│       │                                                          │
│       ▼                                                          │
│  handlePresetChange() ──── Only restores 5 fields ────►          │
│       │                                                          │
│       ▼                                                          │
│  UI State (5 fields restored, 72 fields at defaults)             │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘
```

---

# 3. TARGET STATE ARCHITECTURE

## 3.1 Design Principles

1. **Complete Serialization**: Every field in config store must have a corresponding field in API schema
2. **Bidirectional Mapping**: Clear mapping between store keys and API keys
3. **Format Consistency**: Model IDs use `provider:model` format everywhere
4. **Backward Compatibility**: Existing presets should still load (missing fields get defaults)
5. **Type Safety**: Full TypeScript types on frontend, Pydantic models on backend

## 3.2 Target Data Flow

```
┌──────────────────────────────────────────────────────────────────┐
│                        TARGET FLOW                                │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│  UI State (77 fields)                                            │
│       │                                                          │
│       ▼                                                          │
│  serializeConfigToPreset() ──── Extracts ALL 77 fields ────►    │
│       │                                                          │
│       ▼                                                          │
│  PresetCreate object (77 fields in nested structure)             │
│       │                                                          │
│       ▼                                                          │
│  POST /api/v1/presets                                            │
│       │                                                          │
│       ▼                                                          │
│  Backend saves to DB (77 fields in JSON columns)                 │
│       │                                                          │
│       ▼                                                          │
│  GET /api/v1/presets/:id                                         │
│       │                                                          │
│       ▼                                                          │
│  deserializePresetToConfig() ──── Restores ALL 77 fields ────►  │
│       │                                                          │
│       ▼                                                          │
│  UI State (77 fields restored exactly)                           │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘
```

## 3.3 Storage Strategy

The database already has JSON columns that can store arbitrary data:
- `gptr_config` (JSON) - GPTR settings
- `fpf_config` (JSON) - FPF settings  
- `config_overrides` (JSON) - Everything else

We will use these JSON columns to store complete configuration objects.

## 3.4 API Schema Strategy

Expand the API schemas to include all fields. Use nested objects to organize:

```typescript
interface PresetCreate {
  name: string
  description?: string
  documents: string[]
  iterations: number
  
  // Generator configs (complete)
  generators: string[]
  fpf_config: FpfConfigComplete
  gptr_config: GptrConfigComplete
  dr_config: DrConfigComplete
  ma_config: MaConfigComplete
  
  // Phase configs (complete)
  eval_config: EvalConfigComplete
  pairwise_config: PairwiseConfigComplete
  combine_config: CombineConfigComplete
  
  // General configs
  general_config: GeneralConfigComplete
  concurrency_config: ConcurrencyConfigComplete
}
```

---

# 4. IMPLEMENTATION PHASES

## 4.1 Phase Overview

| Phase | Description | Files Modified | Effort |
|-------|-------------|----------------|--------|
| 1 | Backend Schema Updates | 2 files | 1 hour |
| 2 | Frontend API Types | 1 file | 30 min |
| 3 | Save Implementation | 1 file | 2 hours |
| 4 | Load Implementation | 1 file | 2 hours |
| 5 | Testing | 2 files | 2 hours |

## 4.2 Dependency Graph

```
Phase 1 (Backend Schemas)
    │
    ▼
Phase 2 (Frontend Types)
    │
    ├────────────────┐
    ▼                ▼
Phase 3 (Save)    Phase 4 (Load)
    │                │
    └────────┬───────┘
             ▼
        Phase 5 (Testing)
```

---

# 5. PHASE 1: BACKEND SCHEMA UPDATES

## 5.1 Overview

Update Pydantic schemas to support complete configuration objects.

## 5.2 File: `app/api/schemas/runs.py`

### 5.2.1 Add Extended Settings Classes

```python
# Add after existing classes

class FpfConfigComplete(BaseModel):
    """Complete FPF configuration."""
    enabled: bool = True
    selected_models: list[str] = Field(default_factory=lambda: ["openai:gpt-5"])
    grounding_level: int = Field(5, ge=0, le=100)
    max_tokens: int = Field(32000, ge=1)
    temperature: float = Field(0.7, ge=0, le=2)
    top_p: float = Field(0.95, ge=0, le=1)
    top_k: int = Field(40, ge=1)
    frequency_penalty: float = Field(0.0, ge=-2, le=2)
    presence_penalty: float = Field(0.0, ge=-2, le=2)
    stream_response: bool = True
    use_grounding: bool = True
    include_metadata: bool = True
    save_prompt_history: bool = True
    prompt_template: str = "Summarize this text."


class GptrConfigComplete(BaseModel):
    """Complete GPTR configuration."""
    enabled: bool = True
    selected_models: list[str] = Field(default_factory=lambda: ["openai:gpt-5"])
    fast_llm_token_limit: int = Field(4000, ge=1000)
    smart_llm_token_limit: int = Field(8000, ge=1000)
    strategic_llm_token_limit: int = Field(16000, ge=1000)
    browse_chunk_max_length: int = Field(8000, ge=1000)
    summary_token_limit: int = Field(2000, ge=100)
    temperature: float = Field(0.4, ge=0, le=2)
    max_search_results_per_query: int = Field(5, ge=1, le=20)
    total_words: int = Field(3000, ge=100, le=10000)
    max_iterations: int = Field(4, ge=1, le=10)
    max_subtopics: int = Field(5, ge=1, le=20)
    report_type: str = "research_report"
    report_source: str = "web"
    tone: str = "Objective"
    scrape_urls: bool = True
    add_source_urls: bool = True
    verbose_mode: bool = False
    follow_links: bool = True


class DrConfigComplete(BaseModel):
    """Complete Deep Research configuration."""
    enabled: bool = False
    selected_models: list[str] = Field(default_factory=lambda: ["openai:gpt-5"])
    breadth: int = Field(4, ge=1, le=8)
    depth: int = Field(3, ge=1, le=8)
    max_results: int = Field(10, ge=1, le=20)
    concurrency_limit: int = Field(5, ge=1, le=10)
    temperature: float = Field(0.5, ge=0, le=2)
    max_tokens: int = Field(16000, ge=1000)
    timeout: int = Field(300, ge=60)
    search_provider: str = "tavily"
    enable_caching: bool = True
    follow_links: bool = True
    extract_code: bool = True
    include_images: bool = False
    semantic_search: bool = True
    verbose_logging: bool = False


class MaConfigComplete(BaseModel):
    """Complete Multi-Agent configuration."""
    enabled: bool = False
    selected_models: list[str] = Field(default_factory=lambda: ["openai:gpt-5"])
    max_agents: int = Field(3, ge=1, le=10)
    communication_style: str = "sequential"
    enable_consensus: bool = True
    enable_debate: bool = False
    enable_voting: bool = False
    max_rounds: int = Field(3, ge=1, le=10)


class EvalConfigComplete(BaseModel):
    """Complete Evaluation configuration."""
    enabled: bool = True
    auto_run: bool = True
    iterations: int = Field(3, ge=1, le=9)
    pairwise_top_n: int = Field(5, ge=1, le=10)
    judge_models: list[str] = Field(default_factory=lambda: ["openai:gpt-5"])
    enable_semantic_similarity: bool = True
    enable_factual_accuracy: bool = True
    enable_coherence: bool = True
    enable_relevance: bool = True
    enable_completeness: bool = True
    enable_citation: bool = False


class PairwiseConfigComplete(BaseModel):
    """Complete Pairwise configuration."""
    enabled: bool = False
    judge_models: list[str] = Field(default_factory=lambda: ["openai:gpt-5"])


class CombineConfigComplete(BaseModel):
    """Complete Combine configuration."""
    enabled: bool = False
    selected_models: list[str] = Field(default_factory=lambda: ["openai:gpt-5"])
    strategy: str = "intelligent_merge"


class GeneralConfigComplete(BaseModel):
    """Complete General configuration."""
    iterations: int = Field(3, ge=1, le=10)
    output_dir: str = "./output"
    enable_logging: bool = True
    log_level: str = "info"
    save_intermediate: bool = True


class ConcurrencyConfigComplete(BaseModel):
    """Complete Concurrency configuration."""
    max_concurrent: int = Field(5, ge=1, le=20)
    launch_delay: float = Field(1.0, ge=0)
    enable_rate_limiting: bool = True
    max_retries: int = Field(3, ge=0, le=10)
    retry_delay: float = Field(2.0, ge=0)
```

## 5.3 File: `app/api/schemas/presets.py`

### 5.3.1 Update PresetCreate

```python
class PresetCreate(BaseModel):
    """Request to create a new preset - COMPLETE VERSION."""
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)
    documents: list[str] = Field(default_factory=list)
    
    # Complete configuration objects
    general_config: Optional[GeneralConfigComplete] = None
    fpf_config: Optional[FpfConfigComplete] = None
    gptr_config: Optional[GptrConfigComplete] = None
    dr_config: Optional[DrConfigComplete] = None
    ma_config: Optional[MaConfigComplete] = None
    eval_config: Optional[EvalConfigComplete] = None
    pairwise_config: Optional[PairwiseConfigComplete] = None
    combine_config: Optional[CombineConfigComplete] = None
    concurrency_config: Optional[ConcurrencyConfigComplete] = None
    
    # Legacy fields for backward compatibility
    generators: Optional[list[GeneratorType]] = None
    models: Optional[list[ModelConfig]] = None
    iterations: Optional[int] = None
    gptr_settings: Optional[GptrSettings] = None
    fpf_settings: Optional[FpfSettings] = None
    evaluation: Optional[EvaluationSettings] = None
    pairwise: Optional[PairwiseSettings] = None
    combine: Optional[CombineSettings] = None
```

## 5.4 File: `app/api/routes/presets.py`

### 5.4.1 Update Create Endpoint

```python
@router.post("", response_model=PresetResponse)
async def create_preset(
    data: PresetCreate,
    db: AsyncSession = Depends(get_db)
) -> PresetResponse:
    repo = PresetRepository(db)
    
    # Check for duplicate name
    existing = await repo.get_by_name(data.name)
    if existing:
        raise HTTPException(status_code=400, detail=f"Preset with name '{data.name}' already exists")
    
    # Build complete config_overrides from new config objects
    config_overrides = {}
    
    if data.general_config:
        config_overrides["general"] = data.general_config.model_dump()
    if data.fpf_config:
        config_overrides["fpf"] = data.fpf_config.model_dump()
    if data.gptr_config:
        config_overrides["gptr"] = data.gptr_config.model_dump()
    if data.dr_config:
        config_overrides["dr"] = data.dr_config.model_dump()
    if data.ma_config:
        config_overrides["ma"] = data.ma_config.model_dump()
    if data.eval_config:
        config_overrides["eval"] = data.eval_config.model_dump()
    if data.pairwise_config:
        config_overrides["pairwise"] = data.pairwise_config.model_dump()
    if data.combine_config:
        config_overrides["combine"] = data.combine_config.model_dump()
    if data.concurrency_config:
        config_overrides["concurrency"] = data.concurrency_config.model_dump()
    
    # Handle legacy fields for backward compatibility
    # ... existing code ...
    
    preset = await repo.create(
        name=data.name,
        description=data.description,
        documents=data.documents,
        config_overrides=config_overrides if config_overrides else None,
        # ... other fields ...
    )
    
    return _preset_to_response(preset)
```

### 5.4.2 Update Response Builder

```python
def _preset_to_response(preset) -> PresetResponse:
    """Convert DB preset to API response with complete configs."""
    runs = _get_runs_safely(preset)
    overrides = preset.config_overrides or {}
    
    return PresetResponse(
        id=preset.id,
        name=preset.name,
        description=preset.description,
        documents=preset.documents or [],
        
        # Complete config objects from overrides
        general_config=GeneralConfigComplete(**overrides.get("general", {})) if "general" in overrides else None,
        fpf_config=FpfConfigComplete(**overrides.get("fpf", {})) if "fpf" in overrides else None,
        gptr_config=GptrConfigComplete(**overrides.get("gptr", {})) if "gptr" in overrides else None,
        dr_config=DrConfigComplete(**overrides.get("dr", {})) if "dr" in overrides else None,
        ma_config=MaConfigComplete(**overrides.get("ma", {})) if "ma" in overrides else None,
        eval_config=EvalConfigComplete(**overrides.get("eval", {})) if "eval" in overrides else None,
        pairwise_config=PairwiseConfigComplete(**overrides.get("pairwise", {})) if "pairwise" in overrides else None,
        combine_config=CombineConfigComplete(**overrides.get("combine", {})) if "combine" in overrides else None,
        concurrency_config=ConcurrencyConfigComplete(**overrides.get("concurrency", {})) if "concurrency" in overrides else None,
        
        # Legacy fields for backward compatibility
        # ... existing code ...
    )
```

---

# 6. PHASE 2: FRONTEND API TYPES

## 6.1 File: `ui/src/api/presets.ts`

### 6.1.1 Add Complete Config Interfaces

```typescript
// Complete configuration interfaces matching backend schemas

export interface FpfConfigComplete {
  enabled: boolean;
  selected_models: string[];
  grounding_level: number;
  max_tokens: number;
  temperature: number;
  top_p: number;
  top_k: number;
  frequency_penalty: number;
  presence_penalty: number;
  stream_response: boolean;
  use_grounding: boolean;
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
  timeout: number;
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
  output_dir: string;
  enable_logging: boolean;
  log_level: string;
  save_intermediate: boolean;
}

export interface ConcurrencyConfigComplete {
  max_concurrent: number;
  launch_delay: number;
  enable_rate_limiting: boolean;
  max_retries: number;
  retry_delay: number;
}
```

### 6.1.2 Update PresetCreate and PresetResponse

```typescript
export interface PresetCreate {
  name: string;
  description?: string;
  documents: string[];
  
  // Complete config objects
  general_config?: GeneralConfigComplete;
  fpf_config?: FpfConfigComplete;
  gptr_config?: GptrConfigComplete;
  dr_config?: DrConfigComplete;
  ma_config?: MaConfigComplete;
  eval_config?: EvalConfigComplete;
  pairwise_config?: PairwiseConfigComplete;
  combine_config?: CombineConfigComplete;
  concurrency_config?: ConcurrencyConfigComplete;
}

export interface PresetResponse {
  id: string;
  name: string;
  description?: string;
  documents: string[];
  
  // Complete config objects
  general_config?: GeneralConfigComplete;
  fpf_config?: FpfConfigComplete;
  gptr_config?: GptrConfigComplete;
  dr_config?: DrConfigComplete;
  ma_config?: MaConfigComplete;
  eval_config?: EvalConfigComplete;
  pairwise_config?: PairwiseConfigComplete;
  combine_config?: CombineConfigComplete;
  concurrency_config?: ConcurrencyConfigComplete;
  
  created_at: string;
  updated_at?: string;
  run_count: number;
  last_run_at?: string;
}
```

---

# 7. PHASE 3: SAVE IMPLEMENTATION

## 7.1 File: `ui/src/pages/Configure.tsx`

### 7.1.1 Create Serialization Function

```typescript
/**
 * Serialize the complete Zustand config store to a PresetCreate object.
 * This is the SINGLE SOURCE OF TRUTH for save logic.
 */
function serializeConfigToPreset(
  config: ConfigState,
  presetName: string,
  selectedDocs: string[],
  fpfInstructions: string
): PresetCreate {
  return {
    name: presetName,
    description: 'Saved from Build Preset page',
    documents: selectedDocs,
    
    general_config: {
      iterations: config.general.iterations,
      output_dir: config.general.outputDir,
      enable_logging: config.general.enableLogging,
      log_level: config.general.logLevel,
      save_intermediate: config.general.saveIntermediate,
    },
    
    fpf_config: {
      enabled: config.fpf.enabled,
      selected_models: config.fpf.selectedModels,
      grounding_level: config.fpf.groundingLevel,
      max_tokens: config.fpf.maxTokens,
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
    },
    
    gptr_config: {
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
    },
    
    dr_config: {
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
    },
    
    ma_config: {
      enabled: config.ma.enabled,
      selected_models: config.ma.selectedModels,
      max_agents: config.ma.maxAgents,
      communication_style: config.ma.communicationStyle,
      enable_consensus: config.ma.enableConsensus,
      enable_debate: config.ma.enableDebate,
      enable_voting: config.ma.enableVoting,
      max_rounds: config.ma.maxRounds,
    },
    
    eval_config: {
      enabled: config.eval.enabled,
      auto_run: config.eval.autoRun,
      iterations: config.eval.iterations,
      pairwise_top_n: config.eval.pairwiseTopN,
      judge_models: config.eval.judgeModels,
      enable_semantic_similarity: config.eval.enableSemanticSimilarity,
      enable_factual_accuracy: config.eval.enableFactualAccuracy,
      enable_coherence: config.eval.enableCoherence,
      enable_relevance: config.eval.enableRelevance,
      enable_completeness: config.eval.enableCompleteness,
      enable_citation: config.eval.enableCitation,
    },
    
    pairwise_config: {
      enabled: false, // TODO: Add UI for this
      judge_models: config.eval.judgeModels,
    },
    
    combine_config: {
      enabled: config.combine.enabled,
      selected_models: config.combine.selectedModels,
      strategy: 'intelligent_merge',
    },
    
    concurrency_config: {
      max_concurrent: config.concurrency.maxConcurrent,
      launch_delay: config.concurrency.launchDelay,
      enable_rate_limiting: config.concurrency.enableRateLimiting,
      max_retries: config.concurrency.maxRetries,
      retry_delay: config.concurrency.retryDelay,
    },
  };
}
```

### 7.1.2 Update handleSavePreset

```typescript
const handleSavePreset = async () => {
  if (!presetName) {
    alert('Please enter a name for the preset');
    return;
  }

  try {
    // Serialize complete config to preset
    const presetData = serializeConfigToPreset(
      config,
      presetName,
      selectedDocs,
      fpfInstructions
    );
    
    console.log('Saving preset with complete config:', presetData);

    const existing = presets.find(p => p.id === selectedPresetId);
    if (existing && existing.name === presetName) {
      await updatePreset(existing.id, presetData);
      alert('Preset updated!');
    } else {
      const created = await createPreset(presetData);
      setSelectedPresetId(created.id);
      alert('Preset created!');
    }
    
    await loadPresets();
  } catch (err) {
    console.error('Failed to save preset:', err);
    alert('Failed to save preset');
  }
};
```

---

# 8. PHASE 4: LOAD IMPLEMENTATION

## 8.1 File: `ui/src/pages/Configure.tsx`

### 8.1.1 Create Deserialization Function

```typescript
/**
 * Deserialize a PresetResponse into Zustand config store updates.
 * This is the SINGLE SOURCE OF TRUTH for load logic.
 */
function deserializePresetToConfig(
  preset: PresetResponse,
  config: ConfigState
): void {
  // General config
  if (preset.general_config) {
    config.updateGeneral({
      iterations: preset.general_config.iterations,
      outputDir: preset.general_config.output_dir,
      enableLogging: preset.general_config.enable_logging,
      logLevel: preset.general_config.log_level,
      saveIntermediate: preset.general_config.save_intermediate,
    });
  }
  
  // FPF config
  if (preset.fpf_config) {
    config.updateFpf({
      enabled: preset.fpf_config.enabled,
      selectedModels: preset.fpf_config.selected_models,
      groundingLevel: preset.fpf_config.grounding_level,
      maxTokens: preset.fpf_config.max_tokens,
      temperature: preset.fpf_config.temperature,
      topP: preset.fpf_config.top_p,
      topK: preset.fpf_config.top_k,
      frequencyPenalty: preset.fpf_config.frequency_penalty,
      presencePenalty: preset.fpf_config.presence_penalty,
      streamResponse: preset.fpf_config.stream_response,
      useGrounding: preset.fpf_config.use_grounding,
      includeMetadata: preset.fpf_config.include_metadata,
      savePromptHistory: preset.fpf_config.save_prompt_history,
    });
  }
  
  // GPTR config
  if (preset.gptr_config) {
    config.updateGptr({
      enabled: preset.gptr_config.enabled,
      selectedModels: preset.gptr_config.selected_models,
      fastLlmTokenLimit: preset.gptr_config.fast_llm_token_limit,
      smartLlmTokenLimit: preset.gptr_config.smart_llm_token_limit,
      strategicLlmTokenLimit: preset.gptr_config.strategic_llm_token_limit,
      browseChunkMaxLength: preset.gptr_config.browse_chunk_max_length,
      summaryTokenLimit: preset.gptr_config.summary_token_limit,
      temperature: preset.gptr_config.temperature,
      maxSearchResultsPerQuery: preset.gptr_config.max_search_results_per_query,
      totalWords: preset.gptr_config.total_words,
      maxIterations: preset.gptr_config.max_iterations,
      maxSubtopics: preset.gptr_config.max_subtopics,
      reportType: preset.gptr_config.report_type,
      reportSource: preset.gptr_config.report_source,
      scrapeUrls: preset.gptr_config.scrape_urls,
      addSourceUrls: preset.gptr_config.add_source_urls,
      verboseMode: preset.gptr_config.verbose_mode,
      followLinks: preset.gptr_config.follow_links,
    });
  }
  
  // DR config
  if (preset.dr_config) {
    config.updateDr({
      enabled: preset.dr_config.enabled,
      selectedModels: preset.dr_config.selected_models,
      breadth: preset.dr_config.breadth,
      depth: preset.dr_config.depth,
      maxResults: preset.dr_config.max_results,
      concurrencyLimit: preset.dr_config.concurrency_limit,
      temperature: preset.dr_config.temperature,
      maxTokens: preset.dr_config.max_tokens,
      timeout: preset.dr_config.timeout,
      searchProvider: preset.dr_config.search_provider,
      enableCaching: preset.dr_config.enable_caching,
      followLinks: preset.dr_config.follow_links,
      extractCode: preset.dr_config.extract_code,
      includeImages: preset.dr_config.include_images,
      semanticSearch: preset.dr_config.semantic_search,
      verboseLogging: preset.dr_config.verbose_logging,
    });
  }
  
  // MA config
  if (preset.ma_config) {
    config.updateMa({
      enabled: preset.ma_config.enabled,
      selectedModels: preset.ma_config.selected_models,
      maxAgents: preset.ma_config.max_agents,
      communicationStyle: preset.ma_config.communication_style,
      enableConsensus: preset.ma_config.enable_consensus,
      enableDebate: preset.ma_config.enable_debate,
      enableVoting: preset.ma_config.enable_voting,
      maxRounds: preset.ma_config.max_rounds,
    });
  }
  
  // Eval config
  if (preset.eval_config) {
    config.updateEval({
      enabled: preset.eval_config.enabled,
      autoRun: preset.eval_config.auto_run,
      iterations: preset.eval_config.iterations,
      pairwiseTopN: preset.eval_config.pairwise_top_n,
      judgeModels: preset.eval_config.judge_models,
      enableSemanticSimilarity: preset.eval_config.enable_semantic_similarity,
      enableFactualAccuracy: preset.eval_config.enable_factual_accuracy,
      enableCoherence: preset.eval_config.enable_coherence,
      enableRelevance: preset.eval_config.enable_relevance,
      enableCompleteness: preset.eval_config.enable_completeness,
      enableCitation: preset.eval_config.enable_citation,
    });
  }
  
  // Combine config
  if (preset.combine_config) {
    config.updateCombine({
      enabled: preset.combine_config.enabled,
      selectedModels: preset.combine_config.selected_models,
    });
  }
  
  // Concurrency config
  if (preset.concurrency_config) {
    config.updateConcurrency({
      maxConcurrent: preset.concurrency_config.max_concurrent,
      launchDelay: preset.concurrency_config.launch_delay,
      enableRateLimiting: preset.concurrency_config.enable_rate_limiting,
      maxRetries: preset.concurrency_config.max_retries,
      retryDelay: preset.concurrency_config.retry_delay,
    });
  }
}
```

### 8.1.2 Update handlePresetChange

```typescript
const handlePresetChange = async (e: React.ChangeEvent<HTMLSelectElement>) => {
  const id = e.target.value;
  setSelectedPresetId(id);
  
  if (!id) {
    // New preset - reset to defaults
    setPresetName('');
    setRunName('New Run');
    setRunDescription('');
    setSelectedDocs(['intro.md']);
    setFpfInstructions('Summarize this text.');
    config.resetToDefaults();
    return;
  }
  
  try {
    const preset = await getPreset(id);
    console.log('Loaded preset with complete config:', preset);
    
    // Update local state
    setPresetName(preset.name);
    setRunName(preset.name);
    setRunDescription(preset.description || '');
    setSelectedDocs(preset.documents || []);
    setFpfInstructions(preset.fpf_config?.prompt_template || 'Summarize this text.');
    
    // Deserialize complete config to store
    deserializePresetToConfig(preset, config);
    
  } catch (err) {
    console.error('Failed to load preset:', err);
    alert('Failed to load preset details');
  }
};
```

---

# 9. PHASE 5: TESTING STRATEGY

## 9.1 Unit Tests

### 9.1.1 Serialization Tests

```typescript
// File: ui/src/pages/__tests__/Configure.serialize.test.ts

describe('serializeConfigToPreset', () => {
  it('should serialize all general config fields', () => {
    const config = createMockConfig({
      general: {
        iterations: 5,
        outputDir: '/custom/output',
        enableLogging: false,
        logLevel: 'debug',
        saveIntermediate: false,
      }
    });
    
    const preset = serializeConfigToPreset(config, 'Test', [], '');
    
    expect(preset.general_config.iterations).toBe(5);
    expect(preset.general_config.output_dir).toBe('/custom/output');
    expect(preset.general_config.enable_logging).toBe(false);
    expect(preset.general_config.log_level).toBe('debug');
    expect(preset.general_config.save_intermediate).toBe(false);
  });
  
  it('should serialize all eval config fields including judge_models array', () => {
    const config = createMockConfig({
      eval: {
        enabled: true,
        autoRun: false,
        iterations: 7,
        pairwiseTopN: 3,
        judgeModels: ['openai:gpt-5', 'google:gemini-pro'],
        enableSemanticSimilarity: false,
        enableFactualAccuracy: true,
        enableCoherence: false,
        enableRelevance: true,
        enableCompleteness: false,
        enableCitation: true,
      }
    });
    
    const preset = serializeConfigToPreset(config, 'Test', [], '');
    
    expect(preset.eval_config.judge_models).toEqual(['openai:gpt-5', 'google:gemini-pro']);
    expect(preset.eval_config.iterations).toBe(7);
    expect(preset.eval_config.enable_citation).toBe(true);
  });
  
  // Add tests for all 77 fields...
});
```

### 9.1.2 Deserialization Tests

```typescript
// File: ui/src/pages/__tests__/Configure.deserialize.test.ts

describe('deserializePresetToConfig', () => {
  it('should restore all eval config fields', () => {
    const preset = createMockPresetResponse({
      eval_config: {
        enabled: true,
        auto_run: false,
        iterations: 7,
        pairwise_top_n: 3,
        judge_models: ['openai:gpt-5', 'google:gemini-pro'],
        enable_semantic_similarity: false,
        enable_factual_accuracy: true,
        enable_coherence: false,
        enable_relevance: true,
        enable_completeness: false,
        enable_citation: true,
      }
    });
    
    const config = createMockConfigStore();
    deserializePresetToConfig(preset, config);
    
    expect(config.eval.judgeModels).toEqual(['openai:gpt-5', 'google:gemini-pro']);
    expect(config.eval.iterations).toBe(7);
    expect(config.eval.enableCitation).toBe(true);
  });
});
```

## 9.2 Integration Tests

### 9.2.1 Round-Trip Test

```typescript
// File: ui/src/pages/__tests__/Configure.roundtrip.test.ts

describe('Preset Round-Trip', () => {
  it('should preserve all 77 fields through save/load cycle', async () => {
    // Create a config with ALL fields set to non-default values
    const originalConfig = createFullyCustomConfig();
    
    // Serialize to preset
    const presetData = serializeConfigToPreset(originalConfig, 'Test', ['doc1.md'], 'Custom prompt');
    
    // Simulate API save/load (mock)
    const savedPreset = await mockSavePreset(presetData);
    const loadedPreset = await mockLoadPreset(savedPreset.id);
    
    // Deserialize back to config
    const restoredConfig = createEmptyConfigStore();
    deserializePresetToConfig(loadedPreset, restoredConfig);
    
    // Verify every single field matches
    expect(restoredConfig.general).toEqual(originalConfig.general);
    expect(restoredConfig.fpf).toEqual(originalConfig.fpf);
    expect(restoredConfig.gptr).toEqual(originalConfig.gptr);
    expect(restoredConfig.dr).toEqual(originalConfig.dr);
    expect(restoredConfig.ma).toEqual(originalConfig.ma);
    expect(restoredConfig.eval).toEqual(originalConfig.eval);
    expect(restoredConfig.combine).toEqual(originalConfig.combine);
    expect(restoredConfig.concurrency).toEqual(originalConfig.concurrency);
  });
});
```

## 9.3 E2E Tests

### 9.3.1 Browser Test

```javascript
// File: browser_tools/test_preset_roundtrip.cjs

const { chromium } = require('playwright');

async function testPresetRoundTrip() {
  const browser = await chromium.launch({ headless: false });
  const page = await browser.newPage();
  
  await page.goto('http://localhost:8002/configure');
  
  // Step 1: Configure ALL fields to non-default values
  // ... click checkboxes, move sliders, etc.
  
  // Step 2: Save preset
  await page.fill('input[placeholder="Preset Name"]', 'E2E Test Preset');
  await page.click('button:has-text("Save")');
  
  // Step 3: Reset to defaults
  await page.click('button:has-text("Reset")');
  
  // Step 4: Load the preset
  await page.selectOption('select', { label: 'E2E Test Preset' });
  
  // Step 5: Verify all fields match
  // ... check checkbox states, slider values, etc.
  
  await browser.close();
}
```

---

# 10. ROLLOUT PLAN

## 10.1 Implementation Order

| Step | Task | Time | Dependencies |
|------|------|------|--------------|
| 1 | Update backend schemas | 1 hr | None |
| 2 | Update frontend types | 30 min | Step 1 |
| 3 | Implement serializeConfigToPreset | 1 hr | Step 2 |
| 4 | Update handleSavePreset | 30 min | Step 3 |
| 5 | Implement deserializePresetToConfig | 1 hr | Step 2 |
| 6 | Update handlePresetChange | 30 min | Step 5 |
| 7 | Write unit tests | 1 hr | Steps 3, 5 |
| 8 | Write integration tests | 1 hr | Steps 4, 6 |
| 9 | Manual testing | 1 hr | All above |
| 10 | Deploy | 30 min | All above |

## 10.2 Backward Compatibility

Existing presets will continue to work:
- Old presets without new fields will use defaults when loaded
- New code checks for undefined/null before accessing new fields
- Legacy API fields maintained alongside new fields

## 10.3 Migration Strategy

No data migration needed:
- Existing presets load with defaults for missing fields
- User can re-save presets to include all fields
- Optional: Add "Upgrade Preset" button to re-save with all current values

## 10.4 Verification Checklist

- [ ] Backend starts without errors
- [ ] Frontend builds without errors
- [ ] Can create new preset with all fields
- [ ] Can load preset and see all fields restored
- [ ] Can update preset and see changes persisted
- [ ] Old presets still load (backward compatible)
- [ ] All unit tests pass
- [ ] All integration tests pass
- [ ] E2E test passes

## 10.5 Rollback Plan

If issues arise:
1. Revert frontend changes (git revert)
2. Backend changes are additive, no revert needed
3. Old presets continue to work unchanged

---

# APPENDIX A: FIELD MAPPING REFERENCE

## A.1 General Config

| Store Key | API Key | DB Column |
|-----------|---------|-----------|
| `general.iterations` | `general_config.iterations` | `config_overrides.general.iterations` |
| `general.outputDir` | `general_config.output_dir` | `config_overrides.general.output_dir` |
| `general.enableLogging` | `general_config.enable_logging` | `config_overrides.general.enable_logging` |
| `general.logLevel` | `general_config.log_level` | `config_overrides.general.log_level` |
| `general.saveIntermediate` | `general_config.save_intermediate` | `config_overrides.general.save_intermediate` |

## A.2 FPF Config

| Store Key | API Key | DB Column |
|-----------|---------|-----------|
| `fpf.enabled` | `fpf_config.enabled` | `config_overrides.fpf.enabled` |
| `fpf.selectedModels` | `fpf_config.selected_models` | `config_overrides.fpf.selected_models` |
| `fpf.groundingLevel` | `fpf_config.grounding_level` | `config_overrides.fpf.grounding_level` |
| `fpf.maxTokens` | `fpf_config.max_tokens` | `config_overrides.fpf.max_tokens` |
| `fpf.temperature` | `fpf_config.temperature` | `config_overrides.fpf.temperature` |
| `fpf.topP` | `fpf_config.top_p` | `config_overrides.fpf.top_p` |
| `fpf.topK` | `fpf_config.top_k` | `config_overrides.fpf.top_k` |
| `fpf.frequencyPenalty` | `fpf_config.frequency_penalty` | `config_overrides.fpf.frequency_penalty` |
| `fpf.presencePenalty` | `fpf_config.presence_penalty` | `config_overrides.fpf.presence_penalty` |
| `fpf.streamResponse` | `fpf_config.stream_response` | `config_overrides.fpf.stream_response` |
| `fpf.useGrounding` | `fpf_config.use_grounding` | `config_overrides.fpf.use_grounding` |
| `fpf.includeMetadata` | `fpf_config.include_metadata` | `config_overrides.fpf.include_metadata` |
| `fpf.savePromptHistory` | `fpf_config.save_prompt_history` | `config_overrides.fpf.save_prompt_history` |

## A.3 GPTR Config

| Store Key | API Key | DB Column |
|-----------|---------|-----------|
| `gptr.enabled` | `gptr_config.enabled` | `config_overrides.gptr.enabled` |
| `gptr.selectedModels` | `gptr_config.selected_models` | `config_overrides.gptr.selected_models` |
| `gptr.fastLlmTokenLimit` | `gptr_config.fast_llm_token_limit` | `config_overrides.gptr.fast_llm_token_limit` |
| `gptr.smartLlmTokenLimit` | `gptr_config.smart_llm_token_limit` | `config_overrides.gptr.smart_llm_token_limit` |
| `gptr.strategicLlmTokenLimit` | `gptr_config.strategic_llm_token_limit` | `config_overrides.gptr.strategic_llm_token_limit` |
| `gptr.browseChunkMaxLength` | `gptr_config.browse_chunk_max_length` | `config_overrides.gptr.browse_chunk_max_length` |
| `gptr.summaryTokenLimit` | `gptr_config.summary_token_limit` | `config_overrides.gptr.summary_token_limit` |
| `gptr.temperature` | `gptr_config.temperature` | `config_overrides.gptr.temperature` |
| `gptr.maxSearchResultsPerQuery` | `gptr_config.max_search_results_per_query` | `config_overrides.gptr.max_search_results_per_query` |
| `gptr.totalWords` | `gptr_config.total_words` | `config_overrides.gptr.total_words` |
| `gptr.maxIterations` | `gptr_config.max_iterations` | `config_overrides.gptr.max_iterations` |
| `gptr.maxSubtopics` | `gptr_config.max_subtopics` | `config_overrides.gptr.max_subtopics` |
| `gptr.reportType` | `gptr_config.report_type` | `config_overrides.gptr.report_type` |
| `gptr.reportSource` | `gptr_config.report_source` | `config_overrides.gptr.report_source` |
| `gptr.scrapeUrls` | `gptr_config.scrape_urls` | `config_overrides.gptr.scrape_urls` |
| `gptr.addSourceUrls` | `gptr_config.add_source_urls` | `config_overrides.gptr.add_source_urls` |
| `gptr.verboseMode` | `gptr_config.verbose_mode` | `config_overrides.gptr.verbose_mode` |
| `gptr.followLinks` | `gptr_config.follow_links` | `config_overrides.gptr.follow_links` |

## A.4 Eval Config

| Store Key | API Key | DB Column |
|-----------|---------|-----------|
| `eval.enabled` | `eval_config.enabled` | `config_overrides.eval.enabled` |
| `eval.autoRun` | `eval_config.auto_run` | `config_overrides.eval.auto_run` |
| `eval.iterations` | `eval_config.iterations` | `config_overrides.eval.iterations` |
| `eval.pairwiseTopN` | `eval_config.pairwise_top_n` | `config_overrides.eval.pairwise_top_n` |
| `eval.judgeModels` | `eval_config.judge_models` | `config_overrides.eval.judge_models` |
| `eval.enableSemanticSimilarity` | `eval_config.enable_semantic_similarity` | `config_overrides.eval.enable_semantic_similarity` |
| `eval.enableFactualAccuracy` | `eval_config.enable_factual_accuracy` | `config_overrides.eval.enable_factual_accuracy` |
| `eval.enableCoherence` | `eval_config.enable_coherence` | `config_overrides.eval.enable_coherence` |
| `eval.enableRelevance` | `eval_config.enable_relevance` | `config_overrides.eval.enable_relevance` |
| `eval.enableCompleteness` | `eval_config.enable_completeness` | `config_overrides.eval.enable_completeness` |
| `eval.enableCitation` | `eval_config.enable_citation` | `config_overrides.eval.enable_citation` |

## A.5 Combine Config

| Store Key | API Key | DB Column |
|-----------|---------|-----------|
| `combine.enabled` | `combine_config.enabled` | `config_overrides.combine.enabled` |
| `combine.selectedModels` | `combine_config.selected_models` | `config_overrides.combine.selected_models` |

---

# APPENDIX B: CODE SNIPPETS READY FOR COPY

See implementation sections above for complete, copy-paste ready code.

---

**END OF IMPLEMENTATION PLAN**
