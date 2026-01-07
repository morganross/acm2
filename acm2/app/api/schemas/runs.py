"""
API Schemas for Runs/Executions.

These Pydantic models define the request/response shapes for the runs API.
"""
from datetime import datetime
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field


# ============================================================================
# Enums
# ============================================================================

class GeneratorType(str, Enum):
    """Types of content generators."""
    FPF = "fpf"
    GPTR = "gptr"
    DR = "dr"
    MA = "ma"


class RunStatus(str, Enum):
    """Status of a run/execution."""
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskStatus(str, Enum):
    """Status of an individual generation task."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# ============================================================================
# Nested Models
# ============================================================================

class ModelConfig(BaseModel):
    """Configuration for a single model in a run.
    
    Note: Model validation is delegated to FPF/GPTR adapters.
    ACM passes model strings through without validation.
    """
    provider: str = Field("openai", description="LLM provider (openai, anthropic, google)")
    model: str = Field("gpt-5", description="Model identifier - see /api/v1/models for available options")
    temperature: float = Field(0.7, ge=0, le=2)
    max_tokens: int = Field(4000, ge=1)


class GptrSettings(BaseModel):
    """GPT-Researcher specific settings."""
    report_type: str = Field("research_report", description="Type of report to generate")
    report_source: str = Field("web", description="Source for research (web, local, hybrid)")
    tone: str = Field("Objective", description="Writing tone")
    max_search_results: int = Field(5, ge=1, le=20)
    total_words: int = Field(1000, ge=100, le=10000)
    fast_llm: str = Field("gpt-5-mini")
    smart_llm: str = Field("gpt-5")


class FpfSettings(BaseModel):
    """FPF (FilePromptForge) specific settings.
    
    NOTE: prompt_template is REMOVED - generation instructions are now
    fetched from Content Library via generation_instructions_id.
    """


class EvaluationSettings(BaseModel):
    """Settings for evaluation phase."""
    enabled: bool = Field(True, description="Whether to run evaluation")
    criteria: list[str] = Field(
        default_factory=list,
        description="Evaluation criteria - REQUIRED from preset"
    )
    eval_model: str = Field("", description="Model to use for evaluation - REQUIRED from preset")


class PairwiseSettings(BaseModel):
    """Settings for pairwise comparison."""
    enabled: bool = Field(False, description="Whether to run pairwise comparisons")
    judge_model: str = Field("", description="Model to use as judge - REQUIRED from preset if enabled")


class CombineSettings(BaseModel):
    """Settings for combine phase."""
    enabled: bool = Field(False, description="Whether to run combine phase")
    strategy: str = Field("", description="Combine strategy - REQUIRED from preset if enabled")
    model: str = Field("", description="Model to use for combination - REQUIRED from preset if enabled")


# ============================================================================
# Complete Config Models (for preset persistence)
# ============================================================================

class FpfConfigComplete(BaseModel):
    """Complete FPF configuration for preset persistence.
    
    NOTE: prompt_template is REMOVED - generation instructions are now
    fetched from Content Library via generation_instructions_id.
    
    NOTE: grounding_level and use_grounding REMOVED - FPF always uses
    grounding, it's mandatory and non-configurable.
    """
    enabled: bool = True
    selected_models: list[str] = Field(default_factory=list, description="REQUIRED from preset")
    max_tokens: int = Field(32000, ge=1)
    temperature: float = Field(0.7, ge=0, le=2)
    top_p: float = Field(0.95, ge=0, le=1)
    top_k: int = Field(40, ge=1)
    frequency_penalty: float = Field(0.0, ge=-2, le=2)
    presence_penalty: float = Field(0.0, ge=-2, le=2)
    stream_response: bool = True
    include_metadata: bool = True
    save_prompt_history: bool = True


class GptrConfigComplete(BaseModel):
    """Complete GPTR configuration for preset persistence."""
    enabled: bool = True
    selected_models: list[str] = Field(default_factory=list, description="REQUIRED from preset")
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
    # Subprocess timeout and retry settings
    subprocess_timeout_minutes: int = Field(20, ge=10, le=45, description="Subprocess timeout in minutes (10-45)")
    subprocess_retries: int = Field(1, ge=0, le=3, description="Number of retries on timeout (0-3)")


class DrConfigComplete(BaseModel):
    """Complete Deep Research configuration for preset persistence."""
    enabled: bool = False
    selected_models: list[str] = Field(default_factory=list, description="REQUIRED from preset if enabled")
    breadth: int = Field(4, ge=1, le=8)
    depth: int = Field(3, ge=1, le=8)
    max_results: int = Field(10, ge=1, le=20)
    concurrency_limit: int = Field(5, ge=1, le=10)
    temperature: float = Field(0.5, ge=0, le=2)
    max_tokens: int = Field(16000, ge=1000)
    timeout: int = Field(600, ge=60, description="Request timeout in seconds - legacy, use subprocess_timeout_minutes instead")
    search_provider: str = "tavily"
    enable_caching: bool = True
    follow_links: bool = True
    extract_code: bool = True
    include_images: bool = False
    semantic_search: bool = True
    verbose_logging: bool = False
    # Subprocess timeout and retry settings
    subprocess_timeout_minutes: int = Field(20, ge=10, le=45, description="Subprocess timeout in minutes (10-45)")
    subprocess_retries: int = Field(1, ge=0, le=3, description="Number of retries on timeout (0-3)")


class MaConfigComplete(BaseModel):
    """Complete Multi-Agent configuration for preset persistence."""
    enabled: bool = False
    selected_models: list[str] = Field(default_factory=list, description="REQUIRED from preset if enabled")
    max_agents: int = Field(3, ge=1, le=10)
    communication_style: str = "sequential"
    enable_consensus: bool = True
    enable_debate: bool = False
    enable_voting: bool = False
    max_rounds: int = Field(3, ge=1, le=10)


class EvalConfigComplete(BaseModel):
    """Complete Evaluation configuration for preset persistence."""
    enabled: bool = True
    auto_run: bool = True
    iterations: int = Field(3, ge=1, le=9)
    pairwise_top_n: int = Field(5, ge=1, le=10)
    judge_models: list[str] = Field(default_factory=list, description="REQUIRED from preset")
    timeout_seconds: int = Field(600, ge=60, le=3600, description="Per-call timeout for judge LLM")
    retries: int = Field(3, ge=0, le=10, description="Retry count for transient failures")
    temperature: float = Field(0.3, ge=0.0, le=2.0, description="Temperature for judge LLM")
    max_tokens: int = Field(16384, ge=1024, le=128000, description="Max output tokens for judge LLM")
    strict_json: bool = Field(True, description="Require strict JSON output from judge LLM")
    enable_semantic_similarity: bool = True
    enable_factual_accuracy: bool = True
    enable_coherence: bool = True
    enable_relevance: bool = True
    enable_completeness: bool = True
    enable_citation: bool = False


class PairwiseConfigComplete(BaseModel):
    """Complete Pairwise configuration for preset persistence."""
    enabled: bool = False
    judge_models: list[str] = Field(default_factory=list, description="REQUIRED from preset if enabled")


class CombineConfigComplete(BaseModel):
    """Complete Combine configuration for preset persistence."""
    enabled: bool = False
    selected_models: list[str] = Field(default_factory=list, description="REQUIRED from preset if enabled")
    strategy: str = Field("", description="REQUIRED from preset if enabled")
    max_tokens: Optional[int] = Field(None, description="Max output tokens for combine phase (REQUIRED if enabled)")


class GeneralConfigComplete(BaseModel):
    """Complete General configuration for preset persistence."""
    iterations: int = Field(1, ge=1, le=10, description="Number of document generation iterations")
    eval_iterations: int = Field(1, ge=1, le=10, description="Number of evaluation iterations")
    
    # Logging
    log_level: str = Field("INFO", description="Log level: DEBUG, INFO, WARNING, ERROR")
    fpf_log_output: str = Field("file", description="FPF log output: stream, file, none")
    fpf_log_file_path: Optional[str] = Field(None, description="Path for FPF log file (required if fpf_log_output=file)")
    
    # Post-combine settings
    post_combine_top_n: Optional[int] = Field(None, ge=2, description="Optional limit for post-combine eval comparison")
    
    # Criteria exposure
    expose_criteria_to_generators: bool = Field(
        False, 
        description="If true, evaluation criteria are appended to generation instructions so generators know what they'll be judged on"
    )
    
    # Legacy fields
    output_dir: str = Field("./output", description="Deprecated")
    enable_logging: bool = Field(True, description="Deprecated")
    save_intermediate: bool = Field(True, description="Deprecated")


class ConcurrencyConfigComplete(BaseModel):
    """Complete Concurrency configuration for preset persistence."""
    # Concurrency limits
    generation_concurrency: Optional[int] = Field(5, ge=1, le=50, description="Max concurrent document generations")
    eval_concurrency: Optional[int] = Field(5, ge=1, le=50, description="Max concurrent evaluation calls")
    
    # Timeouts
    request_timeout: Optional[int] = Field(600, ge=60, le=3600, description="Request timeout in seconds")
    eval_timeout: Optional[int] = Field(600, ge=60, le=3600, description="Evaluation timeout in seconds")
    
    # FPF Retry settings (passed to FPF subprocess)
    fpf_max_retries: Optional[int] = Field(3, ge=0, le=10, description="Max retries within FPF for API errors")
    fpf_retry_delay: Optional[float] = Field(1.0, ge=0, le=120.0, description="Seconds to wait between FPF retry attempts")
    
    # Legacy fields for backward compatibility
    max_concurrent: Optional[int] = Field(5, ge=1, le=20, description="Deprecated: use generation_concurrency")
    launch_delay: Optional[float] = Field(1.0, ge=0, description="Deprecated")
    enable_rate_limiting: Optional[bool] = Field(True, description="Deprecated")


# ============================================================================
# Request Models
# ============================================================================

class RunCreate(BaseModel):
    """Request to create a new run."""
    name: str = Field(..., min_length=1, max_length=200, description="Run name")
    description: Optional[str] = Field(None, max_length=2000)
    
    # Optional preset to load config from
    preset_id: Optional[str] = Field(None, description="Preset ID to load configuration from")
    
    # What to run on
    document_ids: list[str] = Field(default_factory=list, description="Document IDs to process (optional if preset_id provided)")
    
    # Generators to use
    generators: list[GeneratorType] = Field(
        default_factory=list,
        description="Which generators to run - REQUIRED from preset"
    )
    
    # Model configurations per generator
    models: list[ModelConfig] = Field(
        default_factory=list,
        description="Models to use - REQUIRED from preset"
    )
    
    # Iterations
    iterations: int = Field(1, ge=1, le=10, description="Number of iterations per doc/model")
    
    # Log level
    log_level: Optional[str] = Field("INFO", description="Log level: ERROR, WARNING, INFO, DEBUG, VERBOSE")
    
    # Generator-specific settings
    gptr_settings: Optional[GptrSettings] = Field(default_factory=GptrSettings)
    fpf_settings: Optional[FpfSettings] = Field(default_factory=FpfSettings)
    
    # Evaluation settings
    evaluation: EvaluationSettings = Field(default_factory=EvaluationSettings)
    pairwise: PairwiseSettings = Field(default_factory=PairwiseSettings)
    combine: CombineSettings = Field(default_factory=CombineSettings)
    
    # Tags for organization
    tags: list[str] = Field(default_factory=list)


class RunUpdate(BaseModel):
    """Request to update a run (limited fields)."""
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)
    tags: Optional[list[str]] = None


class RunAction(BaseModel):
    """Request to perform an action on a run."""
    action: str = Field(..., description="Action: start, pause, resume, cancel")


# ============================================================================
# Response Models
# ============================================================================

class TaskSummary(BaseModel):
    """Summary of a single generation task."""
    id: str
    document_id: str
    document_name: str
    generator: GeneratorType
    model: str
    iteration: int
    status: TaskStatus
    score: Optional[float] = None
    cost_usd: Optional[float] = None
    duration_seconds: Optional[float] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None


class RunProgress(BaseModel):
    """Progress information for a run."""
    total_tasks: int
    completed_tasks: int
    running_tasks: int
    failed_tasks: int
    pending_tasks: int
    progress_percent: float = Field(ge=0, le=100)
    estimated_remaining_seconds: Optional[float] = None


class FpfStats(BaseModel):
    """Live FPF call statistics for a run."""
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    retries: int = 0
    current_phase: Optional[str] = None  # 'generation', 'single_eval', 'pairwise_eval'
    current_call: Optional[str] = None  # Description of current call
    last_error: Optional[str] = None


class RunSummary(BaseModel):
    """Summary view of a run (for list endpoints)."""
    id: str
    name: str
    description: Optional[str] = None
    status: RunStatus
    generators: list[GeneratorType]
    document_count: int
    model_count: int
    iterations: int
    progress: RunProgress
    fpf_stats: Optional[FpfStats] = None  # Live FPF call statistics
    total_cost_usd: float = 0.0
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    tags: list[str] = Field(default_factory=list)

    class Config:
        from_attributes = True


class GeneratedDocInfo(BaseModel):
    """Info about a generated document."""
    id: str
    model: str
    source_doc_id: str
    generator: str
    iteration: int
    cost_usd: Optional[float] = None


class PairwiseRanking(BaseModel):
    """Ranking entry from pairwise comparison."""
    doc_id: str
    wins: int
    losses: int
    elo: float


class PairwiseComparison(BaseModel):
    """A single head-to-head comparison between two documents."""
    doc_id_a: str
    doc_id_b: str
    winner: str  # doc_id of winner or 'tie'
    judge_model: str
    reason: str  # Judge's rationale for the decision
    score_a: Optional[int] = None  # Optional score for doc A (1-10 scale)
    score_b: Optional[int] = None  # Optional score for doc B (1-10 scale)


class PairwiseResults(BaseModel):
    """Results from pairwise comparisons."""
    total_comparisons: int
    winner_doc_id: Optional[str] = None
    rankings: list[PairwiseRanking] = Field(default_factory=list)
    # ACM1-style: list of all head-to-head comparisons
    comparisons: list[PairwiseComparison] = Field(default_factory=list)


# ============================================================================
# ACM1-Style Detailed Evaluation Types
# ============================================================================

class CriterionScoreInfo(BaseModel):
    """Individual criterion score from a single evaluator."""
    criterion: str
    score: int  # 1-5 scale
    reason: str  # Evaluator's rationale/explanation


class JudgeEvaluation(BaseModel):
    """A single evaluation by one judge model."""
    judge_model: str
    trial: int
    scores: list[CriterionScoreInfo]  # Score per criterion
    average_score: float


class DocumentEvalDetail(BaseModel):
    """Detailed evaluation results for a document."""
    evaluations: list[JudgeEvaluation]  # All evaluations by all judges
    overall_average: float


# ============================================================================
# ACM1-Style Timeline & Generation Events
# ============================================================================

class TimelinePhase(str, Enum):
    """Phases in the evaluation pipeline (ACM1 style)."""
    INITIALIZATION = "initialization"
    GENERATION = "generation"
    EVALUATION = "evaluation"
    PAIRWISE = "pairwise"
    COMBINATION = "combination"
    POST_COMBINE_EVAL = "post_combine_eval"
    POST_COMBINE_PAIRWISE = "post_combine_pairwise"
    COMPLETION = "completion"


class TimelineEvent(BaseModel):
    """A single event in the timeline (ACM1 style)."""
    phase: TimelinePhase
    event_type: str
    description: str
    model: Optional[str] = None
    timestamp: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    success: Optional[bool] = None
    details: Optional[dict] = None


class GenerationEvent(BaseModel):
    """Record of a document generation event."""
    doc_id: str
    generator: str  # fpf, gptr, dr
    model: str  # provider:model
    source_doc_id: str  # Input document ID
    iteration: int
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    status: str = "pending"  # pending, running, completed, failed
    error: Optional[str] = None
    token_count: Optional[int] = None
    cost_usd: Optional[float] = None


# ============================================================================
# Per-Source-Document Result Models (Multi-Doc Pipeline)
# ============================================================================

class SourceDocStatus(str, Enum):
    """Status of a source document's pipeline execution."""
    PENDING = "pending"
    GENERATING = "generating"
    SINGLE_EVAL = "single_eval"
    PAIRWISE_EVAL = "pairwise_eval"
    COMBINING = "combining"
    POST_COMBINE_EVAL = "post_combine_eval"
    COMPLETED = "completed"
    COMPLETED_WITH_ERRORS = "completed_with_errors"
    FAILED = "failed"
    CANCELLED = "cancelled"


class SourceDocResultResponse(BaseModel):
    """Results for a single source document's pipeline.
    
    Each input document runs through its own isolated pipeline:
    Generation → Single Eval → Pairwise → Combine → Post-Combine Eval
    
    Documents never compete across source doc boundaries.
    """
    source_doc_id: str
    source_doc_name: str
    status: SourceDocStatus
    
    # Generated documents for this source
    generated_docs: list[GeneratedDocInfo] = Field(default_factory=list)
    
    # Evaluation results
    single_eval_scores: dict[str, float] = Field(
        default_factory=dict,
        description="Average score per generated doc: { gen_doc_id: avg_score }"
    )
    single_eval_detailed: dict[str, DocumentEvalDetail] = Field(
        default_factory=dict,
        description="Detailed eval breakdown per generated doc"
    )
    pairwise_results: Optional[PairwiseResults] = None
    
    # Winner and combined output
    winner_doc_id: Optional[str] = None
    combined_doc: Optional[GeneratedDocInfo] = None  # Legacy: first combined doc
    combined_docs: list[GeneratedDocInfo] = Field(default_factory=list)  # All combined docs
    
    # Post-combine evaluation
    post_combine_eval_scores: dict[str, float] = Field(
        default_factory=dict,
        description="Scores for post-combine comparison"
    )
    post_combine_pairwise: Optional[PairwiseResults] = None
    
    # Timeline events for this source doc
    timeline_events: list[TimelineEvent] = Field(default_factory=list)
    
    # Per-document stats
    errors: list[str] = Field(default_factory=list)
    cost_usd: float = 0.0
    duration_seconds: float = 0.0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class RunDetail(BaseModel):
    """Detailed view of a run (single run endpoint)."""
    id: str
    name: str
    description: Optional[str] = None
    status: RunStatus
    
    # Configuration
    generators: list[GeneratorType]
    models: list[ModelConfig]
    document_ids: list[str]
    iterations: int
    log_level: str = "INFO"  # Log level: ERROR, WARNING, INFO, DEBUG, VERBOSE
    gptr_settings: Optional[GptrSettings] = None
    evaluation: EvaluationSettings
    pairwise: PairwiseSettings
    combine: Optional[CombineSettings] = None
    
    # Progress
    progress: RunProgress
    fpf_stats: Optional[FpfStats] = None  # Live FPF call statistics
    tasks: list[TaskSummary] = Field(default_factory=list)
    
    # Evaluation results - legacy format for backwards compat
    eval_scores: dict[str, dict[str, float]] = Field(default_factory=dict)
    winner: Optional[str] = None  # Winner document/model ID
    
    # New structured evaluation data for heatmaps
    generated_docs: list[GeneratedDocInfo] = Field(default_factory=list)  # List of generated docs
    pre_combine_evals: dict[str, dict[str, float]] = Field(default_factory=dict)  # { gen_doc_id: { judge_model: score } }
    post_combine_evals: dict[str, dict[str, float]] = Field(default_factory=dict)  # { combined_doc_id: { judge_model: score } }
    pairwise_results: Optional[PairwiseResults] = None  # Pairwise comparison results (pre-combine)
    post_combine_pairwise: Optional[PairwiseResults] = None  # Pairwise comparison: combined doc vs winner
    combined_doc_id: Optional[str] = None  # ID of the combined document if any (legacy, first one)
    combined_doc_ids: list[str] = Field(default_factory=list)  # All combined document IDs
    
    # ACM1-style detailed evaluation data with criteria breakdown
    pre_combine_evals_detailed: dict[str, DocumentEvalDetail] = Field(default_factory=dict)  # { gen_doc_id: DocumentEvalDetail }
    post_combine_evals_detailed: dict[str, DocumentEvalDetail] = Field(default_factory=dict)  # { combined_doc_id: DocumentEvalDetail }
    criteria_list: list[str] = Field(default_factory=list)  # All criteria used
    evaluator_list: list[str] = Field(default_factory=list)  # All evaluator model names
    
    # ACM1-style timeline and generation events
    timeline_events: list[TimelineEvent] = Field(default_factory=list)  # All timeline events
    generation_events: list[GenerationEvent] = Field(default_factory=list)  # Generation event records
    
    # === NEW: Per-source-document results (multi-doc pipeline) ===
    # Each source document has its own isolated pipeline results
    source_doc_results: dict[str, SourceDocResultResponse] = Field(
        default_factory=dict,
        description="Results organized by source document ID. Each source doc has its own winner/combined output."
    )
    
    # Costs
    total_cost_usd: float = 0.0
    cost_by_model: dict[str, float] = Field(default_factory=dict)
    cost_by_document: dict[str, float] = Field(default_factory=dict)
    
    # Timing
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    total_duration_seconds: Optional[float] = None
    
    # Organization
    tags: list[str] = Field(default_factory=list)
    
    class Config:
        from_attributes = True


class RunList(BaseModel):
    """Paginated list of runs."""
    items: list[RunSummary]
    total: int
    page: int
    page_size: int
    pages: int


# ============================================================================
# WebSocket Models
# ============================================================================

class TaskUpdate(BaseModel):
    """Real-time update for a task (sent via WebSocket)."""
    run_id: str
    task_id: str
    event: str = Field(..., description="Event type: started, progress, completed, failed")
    status: TaskStatus
    progress: Optional[float] = Field(None, ge=0, le=1, description="0-1 progress")
    message: Optional[str] = None
    score: Optional[float] = None
    cost_usd: Optional[float] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class RunUpdate(BaseModel):
    """Real-time update for a run (sent via WebSocket)."""
    run_id: str
    event: str = Field(..., description="Event type: started, paused, resumed, completed, failed")
    status: RunStatus
    progress: RunProgress
    timestamp: datetime = Field(default_factory=datetime.utcnow)
