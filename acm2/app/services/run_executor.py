"""
Run Executor Service.

Orchestrates the full run pipeline:
1. Generation Phase - Create documents using FPF/GPTR
2. Single-Doc Evaluation - Grade each doc immediately after generation (STREAMING)
3. Pairwise Evaluation - Compare docs head-to-head (BATCH, after all single evals)
4. Combine Phase - Merge winners (optional)
5. Post-Combine Evaluation (optional)
"""

import asyncio
import logging
import traceback
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
from uuid import uuid4

from ..adapters.fpf.adapter import FpfAdapter
from ..adapters.gptr.adapter import GptrAdapter
from ..adapters.combine.adapter import CombineAdapter
from ..adapters.combine.config import CombineConfig
from ..adapters.base import GenerationConfig, GenerationResult, GeneratorType, ProgressCallback, TaskStatus
from ..evaluation import (
    DocumentInput,
    EvaluationConfig,
    EvaluationInput,
    EvaluationService,
    SingleDocEvaluator,
    SingleEvalConfig,
    SingleEvalSummary,
    PairwiseEvaluator,
    PairwiseConfig,
    PairwiseSummary,
    FpfStatsTracker,
)


class RunPhase(str, Enum):
    """Current phase of run execution."""
    PENDING = "pending"
    GENERATING = "generating"
    SINGLE_EVAL = "single_eval"
    PAIRWISE_EVAL = "pairwise_eval"
    COMBINING = "combining"
    POST_COMBINE_EVAL = "post_combine_eval"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class GeneratedDocument:
    """A document produced by generation."""
    doc_id: str
    content: str
    generator: GeneratorType
    model: str
    source_doc_id: str  # The input document ID
    iteration: int
    cost_usd: float = 0.0
    duration_seconds: float = 0.0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RunConfig:
    """Configuration for a run. All fields are REQUIRED unless explicitly Optional."""
    
    # Inputs - REQUIRED (no defaults)
    document_ids: List[str]
    document_contents: Dict[str, str]  # doc_id -> content
    
    # Generators - REQUIRED (no defaults)
    generators: List[GeneratorType]
    models: List[str]  # Model names to use
    model_settings: Dict[str, Dict[str, Any]]  # REQUIRED per-model settings
    
    # Iterations - REQUIRED (no defaults)
    iterations: int
    eval_iterations: int
    
    # Concurrency settings - REQUIRED (no defaults)
    generation_concurrency: int
    eval_concurrency: int
    request_timeout: Optional[int]
    eval_timeout: Optional[int]
    max_retries: int
    retry_delay: float
    
    # Logging - REQUIRED (no defaults)
    log_level: str
    
    # Instructions - Validated based on enabled features (optional but validated in __post_init__)
    instructions: Optional[str] = None  # REQUIRED if FPF generator enabled
    
    # Evaluation - Defaults provided
    enable_single_eval: bool = True
    enable_pairwise: bool = True
    eval_judge_models: List[str] = field(default_factory=list)  # REQUIRED when eval enabled
    eval_retries: int = 0
    eval_temperature: Optional[float] = None
    eval_max_tokens: Optional[int] = None
    eval_strict_json: bool = True
    eval_enable_grounding: bool = True
    pairwise_top_n: Optional[int] = None  # Optional top-N filtering
    
    # Custom evaluation instructions (from Content Library) - Validated based on enabled features
    single_eval_instructions: Optional[str] = None  # REQUIRED if enable_single_eval
    pairwise_eval_instructions: Optional[str] = None  # REQUIRED if enable_pairwise
    eval_criteria: Optional[str] = None  # REQUIRED if any eval enabled
    
    # Combine - Validated if enabled
    enable_combine: bool = False
    combine_strategy: str = ""  # REQUIRED if combine enabled
    combine_models: List[str] = field(default_factory=list)  # REQUIRED if combine enabled
    combine_instructions: Optional[str] = None  # REQUIRED if combine enabled
    
    # FPF Logging - Defaults provided
    fpf_log_output: str = "file"  # REQUIRED: 'stream', 'file', or 'none'
    fpf_log_file_path: Optional[str] = None  # REQUIRED if fpf_log_output='file'
    
    # Post-Combine Configuration - Optional
    post_combine_top_n: Optional[int] = None  # Optional limit for post-combine eval
    
    # Callbacks
    on_progress: Optional[Callable[[str, float, str], None]] = None
    
    def __post_init__(self):
        """Validate all required fields and conditional requirements."""
        
        # Validate required numeric fields
        if self.iterations is None or self.iterations < 1:
            raise ValueError("iterations must be >= 1 and is required")
        if self.eval_iterations is None or self.eval_iterations < 1:
            raise ValueError("eval_iterations must be >= 1 and is required")
        if self.max_retries is None or not (1 <= self.max_retries <= 10):
            raise ValueError("max_retries must be 1-10 and is required")
        if self.retry_delay is None or not (0.5 <= self.retry_delay <= 30.0):
            raise ValueError("retry_delay must be 0.5-30.0 and is required")
        if self.generation_concurrency is None or not (1 <= self.generation_concurrency <= 50):
            raise ValueError("generation_concurrency must be 1-50 and is required")
        if self.eval_concurrency is None or not (1 <= self.eval_concurrency <= 50):
            raise ValueError("eval_concurrency must be 1-50 and is required")
        
        # Validate log_level
        if self.log_level not in ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'VERBOSE']:
            raise ValueError(f"log_level must be DEBUG/INFO/WARNING/ERROR/VERBOSE, got {self.log_level}")
        
        # Validate fpf_log_output
        if self.fpf_log_output not in ['stream', 'file', 'none']:
            raise ValueError(f"fpf_log_output must be 'stream', 'file', or 'none', got {self.fpf_log_output}")
        if self.fpf_log_output == 'file' and not self.fpf_log_file_path:
            raise ValueError("fpf_log_file_path required when fpf_log_output='file'")
        
        # Validate inputs
        if not self.document_ids:
            raise ValueError("document_ids is required and cannot be empty")
        if not self.document_contents:
            raise ValueError("document_contents is required and cannot be empty")
        for doc_id in self.document_ids:
            if doc_id not in self.document_contents:
                raise ValueError(f"Missing content for document_id: {doc_id}")
            if not self.document_contents[doc_id] or not self.document_contents[doc_id].strip():
                raise ValueError(f"Content for document_id {doc_id} is empty or whitespace")
        
        # Validate generators
        if not self.generators:
            raise ValueError("generators list is required and cannot be empty")
        if not self.models:
            raise ValueError("models list is required and cannot be empty")

        # Validate per-model settings
        if not self.model_settings:
            raise ValueError("model_settings is required and cannot be empty")
        for model in self.models:
            if model not in self.model_settings:
                raise ValueError(f"Missing model_settings for model: {model}")
            settings = self.model_settings[model]
            provider = settings.get("provider")
            base_model = settings.get("model") or (model.split(":", 1)[1] if ":" in model else model)
            temperature = settings.get("temperature")
            max_tokens = settings.get("max_tokens")
            if not provider:
                raise ValueError(f"provider is required for model {model} in model_settings")
            if not base_model:
                raise ValueError(f"model name is required for model {model} in model_settings")
            if temperature is None:
                raise ValueError(f"temperature is required for model {model} in model_settings")
            if max_tokens is None or max_tokens < 1:
                raise ValueError(f"max_tokens must be >= 1 for model {model} in model_settings")
            # Persist the resolved base model name back into settings for later use
            self.model_settings[model]["model"] = base_model
        
        # Validate FPF instructions
        if GeneratorType.FPF in self.generators and not self.instructions:
            raise ValueError(
                "FPF generator requires instructions. "
                "Select instructions from Content Library in preset."
            )
        
        # Validate evaluation instructions
        if self.enable_single_eval:
            if not self.eval_judge_models:
                raise ValueError("eval_judge_models required when single evaluation enabled")
            if not self.single_eval_instructions:
                raise ValueError(
                    "Single evaluation enabled but no instructions provided. "
                    "Select single_eval_instructions from Content Library in preset."
                )
            if self.eval_retries is None or self.eval_retries < 0 or self.eval_retries > 10:
                raise ValueError("eval_retries must be 0-10 and is required when single evaluation is enabled")
            if self.eval_timeout is None:
                raise ValueError("eval_timeout must be set when single evaluation is enabled")
            if self.eval_max_tokens is None or self.eval_max_tokens < 1:
                raise ValueError("eval_max_tokens must be >= 1 when single evaluation is enabled")
            if self.eval_temperature is None:
                raise ValueError("eval_temperature must be set when single evaluation is enabled")
        
        if self.enable_pairwise:
            if not self.eval_judge_models:
                raise ValueError("eval_judge_models required when pairwise evaluation enabled")
            if not self.pairwise_eval_instructions:
                raise ValueError(
                    "Pairwise evaluation enabled but no instructions provided. "
                    "Select pairwise_eval_instructions from Content Library in preset."
                )
            if self.eval_retries is None or self.eval_retries < 0 or self.eval_retries > 10:
                raise ValueError("eval_retries must be 0-10 and is required when pairwise evaluation is enabled")
            if self.eval_timeout is None:
                raise ValueError("eval_timeout must be set when pairwise evaluation is enabled")
            if self.eval_max_tokens is None or self.eval_max_tokens < 1:
                raise ValueError("eval_max_tokens must be >= 1 when pairwise evaluation is enabled")
            if self.eval_temperature is None:
                raise ValueError("eval_temperature must be set when pairwise evaluation is enabled")
        
        if (self.enable_single_eval or self.enable_pairwise) and not self.eval_criteria:
            raise ValueError(
                "Evaluation enabled but no criteria provided. "
                "Select eval_criteria from Content Library in preset."
            )
        
        # Validate combine configuration
        if self.enable_combine:
            if not self.combine_models:
                raise ValueError(
                    "Combine enabled but no models provided. "
                    "Add at least one combine model in preset."
                )
            if not self.combine_instructions:
                raise ValueError(
                    "Combine enabled but no instructions provided. "
                    "Select combine_instructions from Content Library in preset."
                )
            if not self.combine_strategy:
                raise ValueError("Combine enabled but no strategy provided")
        
        # Validate optional top-N settings
        if self.pairwise_top_n is not None and self.pairwise_top_n < 2:
            raise ValueError("pairwise_top_n must be >= 2 or None")
        if self.post_combine_top_n is not None and self.post_combine_top_n < 2:
            raise ValueError("post_combine_top_n must be >= 2 or None")


@dataclass
class RunProgress:
    """Progress tracking for a run."""
    phase: RunPhase
    total_tasks: int
    completed_tasks: int
    current_task: Optional[str] = None
    
    @property
    def progress_percent(self) -> float:
        if self.total_tasks == 0:
            return 0.0
        return (self.completed_tasks / self.total_tasks) * 100


@dataclass
class RunResult:
    """Result of a completed run."""
    run_id: str
    status: RunPhase
    
    # Generated documents
    generated_docs: List[GeneratedDocument]
    
    # Evaluation results
    single_eval_results: Optional[Dict[str, SingleEvalSummary]] = None
    pairwise_results: Optional[PairwiseSummary] = None
    
    # Final output
    winner_doc_id: Optional[str] = None
    combined_docs: List[GeneratedDocument] = field(default_factory=list)  # All combined docs
    
    # Post-combine evaluation
    post_combine_eval_results: Optional[PairwiseSummary] = None
    
    # Stats
    total_cost_usd: float = 0.0
    duration_seconds: float = 0.0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    fpf_stats: Optional[Dict[str, Any]] = None  # Live FPF call statistics
    
    # Errors
    errors: List[str] = field(default_factory=list)


class RunExecutor:
    """
    Executes a full run pipeline.
    
    Pipeline flow:
    ```
    [Input Docs] 
         │
         ▼
    ┌─────────────────────────────────────────┐
    │ GENERATION PHASE                        │
    │ For each (doc, model, iteration):       │
    │   1. Generate document                  │
    │   2. Single-eval IMMEDIATELY ◄────────┐ │  ← STREAMING
    │      (don't wait for other gens)      │ │
    └───────────────────────────────────────┘ │
                      │                       │
                      ▼ (wait for ALL)        │
    ┌─────────────────────────────────────────┐
    │ PAIRWISE PHASE (batch)                  │
    │   1. Collect all single-eval scores     │
    │   2. Filter to Top-N (optional)         │
    │   3. Run pairwise tournament            │
    │   4. Calculate Elo rankings             │
    └─────────────────────────────────────────┘
                      │
                      ▼
    [Winner Document(s)]
    ```
    """
    
    def __init__(self, ws_manager=None, run_logger: Optional[logging.Logger] = None):
        self._fpf_adapter = FpfAdapter()
        self._gptr_adapter = GptrAdapter()
        self._cancelled = False
        self._fpf_stats = FpfStatsTracker()  # Track FPF stats across the run
        # NOTE: Callback is set in execute() with run_id closure, not here
        
        # Use injected logger or fallback to module logger (legacy/test support)
        self.logger = run_logger or logging.getLogger(__name__)
        
        # Use injected WebSocket manager or try to import if not provided (legacy fallback)
        if ws_manager:
            self._run_ws_manager = ws_manager
        else:
            try:
                from ..api.websockets import run_ws_manager
                self._run_ws_manager = run_ws_manager
            except Exception:
                self._run_ws_manager = None
            
        # Debug: surface executor creation info
        try:
            self.logger.debug(
                "RunExecutor.__init__ created fpf_adapter=%r gptr_adapter=%r cancelled=%s ws_manager=%s",
                type(self._fpf_adapter).__name__,
                type(self._gptr_adapter).__name__,
                self._cancelled,
                "INJECTED" if ws_manager else ("IMPORTED" if self._run_ws_manager else "NONE")
            )
        except Exception:
            self.logger.debug("RunExecutor.__init__ debug log failed", exc_info=True)
            
    def _broadcast_stats(self, stats: FpfStatsTracker, run_id: str):
        """Broadcast updated FPF stats via WebSocket.
        
        Args:
            stats: The stats tracker with current counts
            run_id: The run ID to broadcast to (captured in closure at execute() start)
        """
        # CRITICAL DEBUG: This should appear in logs!
        self.logger.info(f"[STATS] _broadcast_stats ENTERED! run_id={run_id}")
        
        # Fix #8: Validate run_id matches current active run
        current_run = getattr(self, '_current_run_id', None)
        if current_run and current_run != run_id:
            self.logger.warning(f"[STATS] RUN ID MISMATCH! Broadcast target={run_id}, but current executor run={current_run}. Skipping stale broadcast.")
            return
            
        self.logger.info(f"[STATS] Checking ws_manager: {self._run_ws_manager is not None}")
        if not self._run_ws_manager:
            self.logger.warning(f"[STATS] Cannot broadcast for run {run_id}: WebSocket manager not initialized")
            return
        
        try:
            # Serialize stats with validation
            stats_dict = stats.to_dict()
            self.logger.info(f"[STATS] Broadcasting stats for run {run_id}: {stats_dict}")
            
            # Create stats payload
            payload = {
                "event": "fpf_stats_update",
                "stats": stats_dict
            }
            
            # Try to broadcast via event loop
            try:
                loop = asyncio.get_running_loop()
                self.logger.info(f"[STATS] Got running loop, creating task")
                task = loop.create_task(self._run_ws_manager.broadcast(run_id, payload))
                self.logger.info(f"[STATS] WebSocket broadcast task created for run {run_id}")
            except RuntimeError as e:
                self.logger.warning(f"[STATS] No running event loop for run {run_id}: {e}")
        except Exception as e:
            self.logger.error(f"[STATS] Failed to broadcast stats for run {run_id}: {e}", exc_info=True)
    
    async def _emit_timeline_event(
        self,
        run_id: str,
        phase: str,
        event_type: str,
        description: str,
        model: Optional[str] = None,
        timestamp: Optional[datetime] = None,
        completed_at: Optional[datetime] = None,
        duration_seconds: Optional[float] = None,
        success: bool = True,
        details: Optional[dict] = None,
    ) -> None:
        """Emit a timeline event to the database for progressive UI updates.
        
        This appends an event to results_summary.timeline_events so the frontend
        can show timeline progress during execution, not just at completion.
        """
        from ..infra.db.session import async_session_factory
        from ..infra.db.repositories import RunRepository
        
        event = {
            "phase": phase,
            "event_type": event_type,
            "description": description,
            "model": model,
            "timestamp": (timestamp or datetime.utcnow()).isoformat(),
            "completed_at": completed_at.isoformat() if completed_at else None,
            "duration_seconds": duration_seconds,
            "success": success,
            "details": details,
        }
        
        try:
            async with async_session_factory() as session:
                run_repo = RunRepository(session)
                await run_repo.append_timeline_event(run_id, event)
                self.logger.debug(f"Emitted timeline event: {phase}/{event_type} for run {run_id}")
        except Exception as e:
            self.logger.warning(f"Failed to emit timeline event for run {run_id}: {e}")
    
    def _get_adapter(self, generator: GeneratorType):
        """Get adapter for generator type."""
        if generator == GeneratorType.FPF:
            return self._fpf_adapter
        elif generator == GeneratorType.GPTR:
            return self._gptr_adapter
        else:
            raise ValueError(f"Unknown generator: {generator}")
    
    async def _save_generated_content(self, run_id: str, gen_doc: GeneratedDocument) -> None:
        """Save generated document content to a file. FAILS if content is empty.
        
        Files are stored in logs/{run_id}/generated/{doc_id}.md
        """
        from pathlib import Path
        import aiofiles
        
        try:
            # Validate content before saving - NO FALLBACK
            if not gen_doc.content:
                raise ValueError(f"Cannot save document {gen_doc.doc_id}: content is None or empty")
            
            if not gen_doc.content.strip():
                raise ValueError(f"Cannot save document {gen_doc.doc_id}: content is only whitespace")
            
            # Create directory structure
            gen_dir = Path("logs") / run_id / "generated"
            gen_dir.mkdir(parents=True, exist_ok=True)
            
            # Sanitize doc_id for filename (replace invalid chars)
            safe_doc_id = gen_doc.doc_id.replace(':', '_').replace('/', '_').replace('\\', '_')
            file_path = gen_dir / f"{safe_doc_id}.md"
            
            # Write content - no fallback
            async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
                await f.write(gen_doc.content)
            
            self.logger.debug(f"Saved generated content to {file_path}")
        except Exception as e:
            # Re-raise to fail the run - empty content is a critical error
            self.logger.error(f"Failed to save generated content for {gen_doc.doc_id}: {e}")
            raise RuntimeError(f"Failed to save {gen_doc.doc_id}: {e}") from e
            self.logger.exception(f"Failed to save generated content for {gen_doc.doc_id}: {e}")
    
    async def execute(self, run_id: str, config: RunConfig) -> RunResult:
        """
        Execute a full run.
        
        Args:
            run_id: Unique run identifier
            config: Run configuration
            
        Returns:
            RunResult with all outputs and stats
        """
        # CRITICAL: Set run_id FIRST before any other operations
        self._current_run_id = run_id
        self.config = config  # Store config for access in other methods
        self.logger.info(f"[STATS] Initializing executor for run {run_id}")
        
        # Fix #5: Reset stats for new run
        # Fix #3: Create closure that captures run_id to prevent stale ID issues
        self._fpf_stats = FpfStatsTracker()
        captured_run_id = run_id  # Capture in local variable for closure
        self._fpf_stats._on_update = lambda stats: self._broadcast_stats(stats, captured_run_id)
        self.logger.info(f"[STATS] FpfStatsTracker initialized with broadcast callback bound to run_id={captured_run_id}")
        
        started_at = datetime.utcnow()
        result = RunResult(
            run_id=run_id,
            status=RunPhase.GENERATING,
            generated_docs=[],
            started_at=started_at,
        )
        
        # Debug: log a concise run config summary (no secrets)
        try:
            self.logger.debug(
                "Run %s config summary: documents=%d models=%r generators=%r iterations=%d enable_single_eval=%s enable_pairwise=%s log_level=%s",
                run_id,
                len(config.document_ids or []),
                config.models,
                [g.value for g in (config.generators or [])],
                config.iterations,
                config.enable_single_eval,
                config.enable_pairwise,
                config.log_level,
            )
        except Exception:
            self.logger.debug("Failed to log run config summary", exc_info=True)

        # Emit run start timeline event
        await self._emit_timeline_event(
            run_id=run_id,
            phase="initialization",
            event_type="start",
            description="Run started",
            timestamp=started_at,
            success=True,
        )
        
        try:
            # Phase 1: Generation + Streaming Single Eval
            self.logger.info(f"Run {run_id}: Starting generation phase")
            await self._run_generation_with_eval(run_id, config, result)
            
            if self._cancelled:
                result.status = RunPhase.CANCELLED
                # Ensure stats are included even if cancelled
                try:
                    result.fpf_stats = self._fpf_stats.to_dict()
                except Exception:
                    pass
                return result
            
            # Phase 2: Pairwise Evaluation (batch, after all single evals)
            if config.enable_pairwise and len(result.generated_docs) >= 2:
                self.logger.info(f"Run {run_id}: Starting pairwise phase")
                result.status = RunPhase.PAIRWISE_EVAL
                if getattr(self, '_run_store', None):
                    try:
                        self._run_store.update(run_id, current_phase=result.status.value)
                        if getattr(self, '_run_ws_manager', None):
                            try:
                                await self._run_ws_manager.broadcast(run_id, {"event": "phase", "phase": result.status.value, "run": self._run_store.get(run_id)})
                            except Exception:
                                pass
                    except Exception:
                        pass
                await self._run_pairwise(config, result)
            
            if self._cancelled:
                result.status = RunPhase.CANCELLED
                # Ensure stats are included even if cancelled
                try:
                    result.fpf_stats = self._fpf_stats.to_dict()
                except Exception:
                    pass
                return result
            
            # If pairwise was disabled but we have single eval results, determine winner from scores
            if not result.winner_doc_id and result.single_eval_results and config.enable_combine:
                # Find doc with highest average score from single eval
                doc_scores = {}
                for doc_id, summary in result.single_eval_results.items():
                    if hasattr(summary, 'weighted_avg_score') and summary.weighted_avg_score is not None:
                        doc_scores[doc_id] = summary.weighted_avg_score
                    elif hasattr(summary, 'avg_score') and summary.avg_score is not None:
                        doc_scores[doc_id] = summary.avg_score
                
                if doc_scores:
                    result.winner_doc_id = max(doc_scores, key=doc_scores.get)
                    self.logger.info(f"Run {run_id}: Winner determined from single eval scores: {result.winner_doc_id} (score: {doc_scores[result.winner_doc_id]:.2f})")
                    if getattr(self, '_run_store', None):
                        try:
                            self._run_store.update(run_id, winner_doc_id=result.winner_doc_id)
                        except Exception:
                            pass
            
            # Phase 3: Combine (optional)
            if config.enable_combine and result.winner_doc_id:
                self.logger.info(f"Run {run_id}: Starting combine phase")
                result.status = RunPhase.COMBINING
                if getattr(self, '_run_store', None):
                    try:
                        self._run_store.update(run_id, current_phase=result.status.value)
                        if getattr(self, '_run_ws_manager', None):
                            try:
                                await self._run_ws_manager.broadcast(run_id, {"event": "phase", "phase": result.status.value, "run": self._run_store.get(run_id)})
                            except Exception:
                                pass
                    except Exception:
                        pass
                await self._run_combine(config, result)
            
            # Phase 4: Post-Combine Eval (optional)
            self.logger.debug(f"Post-combine eval check: enable_combine={config.enable_combine}, combined_docs={len(result.combined_docs)}, enable_pairwise={config.enable_pairwise}")
            if config.enable_combine and result.combined_docs and config.enable_pairwise:
                self.logger.info(f"Run {run_id}: Starting post-combine eval phase")
                result.status = RunPhase.POST_COMBINE_EVAL
                if getattr(self, '_run_store', None):
                    try:
                        self._run_store.update(run_id, current_phase=result.status.value)
                        if getattr(self, '_run_ws_manager', None):
                            try:
                                await self._run_ws_manager.broadcast(run_id, {"event": "phase", "phase": result.status.value, "run": self._run_store.get(run_id)})
                            except Exception:
                                pass
                    except Exception:
                        pass
                await self._run_post_combine_eval(config, result)

            # Done
            result.status = RunPhase.COMPLETED
            result.completed_at = datetime.utcnow()
            result.duration_seconds = (result.completed_at - started_at).total_seconds()
            
            # Include FPF stats in result
            try:
                result.fpf_stats = self._fpf_stats.to_dict()
                self.logger.info(f"[STATS] Stored final stats in result for run {run_id}: {result.fpf_stats}")
            except Exception as e:
                self.logger.error(f"[STATS] Failed to serialize stats for run {run_id}: {e}", exc_info=True)
                result.fpf_stats = None
            
            # Emit run completion timeline event
            await self._emit_timeline_event(
                run_id=run_id,
                phase="completion",
                event_type="complete",
                description="Run completed successfully",
                timestamp=result.completed_at,
                duration_seconds=result.duration_seconds,
                success=True,
            )
            
            self.logger.info(
                f"Run {run_id}: Completed | "
                f"docs={len(result.generated_docs)} "
                f"winner={result.winner_doc_id} "
                f"cost=${result.total_cost_usd:.4f}"
            )
            
        except Exception as e:
            tb = traceback.format_exc()
            self.logger.error(f"Run {run_id} failed: {e}\n{tb}")
            result.status = RunPhase.FAILED
            # Store both message and full traceback for diagnostics
            result.errors.append(str(e))
            result.errors.append(tb)
            result.completed_at = datetime.utcnow()
            
            # Include FPF stats even on failure
            try:
                result.fpf_stats = self._fpf_stats.to_dict()
                self.logger.info(f"[STATS] Stored stats from failed run {run_id}: {result.fpf_stats}")
            except Exception as stats_err:
                self.logger.error(f"[STATS] Failed to serialize stats for failed run {run_id}: {stats_err}", exc_info=True)
                result.fpf_stats = None
            
            # Emit run failure timeline event
            await self._emit_timeline_event(
                run_id=run_id,
                phase="completion",
                event_type="failed",
                description=f"Run failed: {str(e)[:100]}",
                timestamp=result.completed_at,
                success=False,
                details={"error": str(e)},
            )
        
        return result
    
    async def _run_generation_with_eval(
        self,
        run_id: str,
        config: RunConfig,
        result: RunResult,
    ) -> None:
        """
        Run generation phase with streaming single-doc evaluation.
        
        Each document is evaluated IMMEDIATELY after generation,
        not waiting for other documents to complete.
        """
        # Build task list: (doc_id, generator, model, iteration)
        tasks = []
        for doc_id in config.document_ids:
            for generator in config.generators:
                for model in config.models:
                    for iteration in range(1, config.iterations + 1):
                        tasks.append((doc_id, generator, model, iteration))

        # Initialize run_store tasks list so WebSocket clients see initial progress
        if getattr(self, '_run_store', None):
            try:
                initial_tasks = []
                for doc_id, generator, model, iteration in tasks:
                    # gen_doc_id same format used elsewhere
                    task_id = f"{doc_id}.{generator.value}.{iteration}.{model}"
                    initial_tasks.append({
                        "id": task_id,
                        "document_id": doc_id,
                        "document_name": doc_id,
                        "generator": generator.value,
                        "model": model,
                        "iteration": iteration,
                        "status": "pending",
                            "progress": 0.0,
                            "message": None,
                        "score": None,
                        "cost_usd": 0.0,
                        "duration_seconds": 0.0,
                        "started_at": None,
                        "completed_at": None,
                        "error_message": None,
                    })
                self._run_store.update(run_id, tasks=initial_tasks)
                if getattr(self, '_run_ws_manager', None):
                    try:
                        await self._run_ws_manager.broadcast(run_id, {"event": "init", "tasks": initial_tasks})
                    except Exception:
                        pass
            except Exception:
                pass
        
        total_tasks = len(tasks)
        completed = 0
        
        # Setup single-doc evaluator if enabled
        single_evaluator = None
        if config.enable_single_eval:
            # VALIDATE: single_eval_instructions MUST be provided from Content Library
            if not config.single_eval_instructions:
                raise RuntimeError(
                    "Single evaluation is enabled but no single_eval_instructions provided. "
                    "You must configure single_eval_instructions_id in your preset to point to "
                    "a Content Library item containing the evaluation prompt."
                )
            # VALIDATE: eval_judge_models MUST be provided from preset
            if not config.eval_judge_models:
                raise RuntimeError(
                    "Single evaluation is enabled but no judge models configured. "
                    "You must configure eval_config.judge_models in your preset's config_overrides."
                )
            eval_config = SingleEvalConfig(
                iterations=config.eval_iterations,
                judge_models=config.eval_judge_models,
                custom_instructions=config.single_eval_instructions,
                custom_criteria=config.eval_criteria,
                concurrent_limit=config.eval_concurrency,
                timeout_seconds=config.eval_timeout,
                temperature=config.eval_temperature,
                max_tokens=config.eval_max_tokens,
                retries=config.eval_retries,
                strict_json=config.eval_strict_json,
                enable_grounding=config.eval_enable_grounding,
            )
            self.logger.info(f"[STATS-DEBUG] Creating SingleDocEvaluator with stats_tracker={self._fpf_stats is not None}")
            single_evaluator = SingleDocEvaluator(eval_config, stats_tracker=self._fpf_stats)
            result.single_eval_results = {}
        
        # Process tasks with limited concurrency (from settings)
        semaphore = asyncio.Semaphore(config.generation_concurrency)
        
        async def process_task(task_info):
            nonlocal completed
            doc_id, generator, model, iteration = task_info
            
            async with semaphore:
                if self._cancelled:
                    return
                
                nonlocal result
                # Update run_store to set task to running
                task_id = f"{doc_id}.{generator.value}.{iteration}.{model}"
                if getattr(self, '_run_store', None):
                    run = self._run_store.get(run_id)
                    if run:
                        if 'tasks' not in run:
                            self.logger.error(f"Run {run_id} missing 'tasks' field")
                            tasks_list = []
                        else:
                            tasks_list = run['tasks']
                        for t in tasks_list:
                            if t['id'] == task_id:
                                t['status'] = 'running'
                                t['progress'] = 0.05
                                t['message'] = 'started'
                                t['started_at'] = datetime.utcnow()
                                break
                        self._run_store.update(run_id, tasks=tasks_list)
                        if getattr(self, '_run_ws_manager', None):
                            try:
                                await self._run_ws_manager.broadcast(run_id, {"event": "task_update", "task": t})
                            except Exception:
                                pass

                # Progress callback for this specific task
                async def _progress_callback(stage: str, progress: float, message: Optional[str]):
                    # Update the run_store task entry
                    if getattr(self, '_run_store', None):
                        run = self._run_store.get(run_id)
                        if run:
                            if 'tasks' not in run:
                                self.logger.warning(f"Run {run_id} missing 'tasks' field in progress callback")
                                return
                            tasks_list = run['tasks']
                            for tt in tasks_list:
                                if tt['id'] == task_id:
                                    tt['progress'] = progress
                                    tt['message'] = message
                                    break
                            self._run_store.update(run_id, tasks=tasks_list)
                            # Broadcast to run-level WS
                            if getattr(self, '_run_ws_manager', None):
                                try:
                                    await self._run_ws_manager.broadcast(run_id, {"event": "task_update", "task": tt})
                                except Exception:
                                    pass
                    # Also broadcast to task-level WS manager if available
                    try:
                        from ..api.routes.generation import ws_manager as gen_ws_manager
                        await gen_ws_manager.broadcast(task_id, {"event": "progress", "task_id": task_id, "stage": stage, "progress": progress, "message": message})
                    except Exception:
                        pass

                # 1. Generate
                gen_result = await self._generate_single(
                    doc_id=doc_id,
                    content=config.document_contents[doc_id],
                    instructions=config.instructions,
                    generator=generator,
                    model=model,
                    iteration=iteration,
                    progress_callback=_progress_callback,
                    log_level=config.log_level,
                    run_id=run_id,
                    timeout=config.request_timeout,
                )
                
                if gen_result:
                    result.generated_docs.append(gen_result)
                    result.total_cost_usd += gen_result.cost_usd
                    
                    # Save generated content to file for later retrieval
                    await self._save_generated_content(run_id, gen_result)
                    
                    # Emit generation timeline event
                    gen_completed_at = gen_result.completed_at if hasattr(gen_result, 'completed_at') and gen_result.completed_at else datetime.utcnow()
                    await self._emit_timeline_event(
                        run_id=run_id,
                        phase="generation",
                        event_type="generation",
                        description=f"Generated doc using {generator.value}",
                        model=model,
                        timestamp=gen_result.started_at if hasattr(gen_result, 'started_at') and gen_result.started_at else None,
                        completed_at=gen_completed_at,
                        duration_seconds=gen_result.duration_seconds,
                        success=True,
                        details={"doc_id": gen_result.doc_id},
                    )
                    
                    # 2. Single eval IMMEDIATELY (streaming)
                    if single_evaluator and gen_result.content:
                        try:
                            eval_input = DocumentInput(
                                doc_id=gen_result.doc_id,
                                content=gen_result.content,
                            )
                            eval_started_at = datetime.utcnow()
                            summary = await single_evaluator.evaluate_document(eval_input)
                            result.single_eval_results[gen_result.doc_id] = summary
                            eval_completed_at = datetime.utcnow()
                            
                            # Emit single eval timeline event
                            await self._emit_timeline_event(
                                run_id=run_id,
                                phase="evaluation",
                                event_type="single_eval",
                                description=f"Evaluated {gen_result.doc_id[:20]}...",
                                model=", ".join(config.eval_judge_models) if config.eval_judge_models else None,
                                timestamp=eval_started_at,
                                completed_at=eval_completed_at,
                                duration_seconds=(eval_completed_at - eval_started_at).total_seconds(),
                                success=True,
                                details={
                                    "doc_id": gen_result.doc_id,
                                    "average_score": summary.avg_score,
                                },
                            )
                            
                            # Broadcast eval score via WebSocket for live UI updates
                            if getattr(self, '_run_ws_manager', None):
                                try:
                                    await self._run_ws_manager.broadcast(run_id, {
                                        "event": "eval_complete",
                                        "doc_id": gen_result.doc_id,
                                        "average_score": summary.avg_score,
                                        "scores_by_model": {m: s.avg_score for m, s in summary.model_scores.items()} if hasattr(summary, 'model_scores') and summary.model_scores else {},
                                        "duration_seconds": (eval_completed_at - eval_started_at).total_seconds(),
                                    })
                                except Exception:
                                    pass
                            
                            self.logger.info(
                                f"Single eval complete: {gen_result.doc_id} | "
                                f"avg={summary.avg_score:.2f}"
                            )
                        except Exception as e:
                            self.logger.error(f"Single eval failed for {gen_result.doc_id}: {e}")
                            result.errors.append(f"Single eval failed: {gen_result.doc_id}")
                    # Update run_store: mark task completed
                    if getattr(self, '_run_store', None):
                        run = self._run_store.get(run_id)
                        if run:
                            if 'tasks' not in run:
                                self.logger.error(f"Run {run_id} missing 'tasks' field on completion")
                                tasks_list = []
                            else:
                                tasks_list = run['tasks']
                            for t in tasks_list:
                                if t['id'] == task_id:
                                    t['status'] = 'completed'
                                    t['progress'] = 1.0
                                    t['message'] = 'completed'
                                    t['cost_usd'] = gen_result.cost_usd or 0.0
                                    t['duration_seconds'] = gen_result.duration_seconds or 0.0
                                    t['completed_at'] = datetime.utcnow()
                                    break
                            self._run_store.update(run_id, tasks=tasks_list, total_cost_usd=result.total_cost_usd)
                            if getattr(self, '_run_ws_manager', None):
                                try:
                                    await self._run_ws_manager.broadcast(run_id, {"event": "task_update", "task": t})
                                except Exception:
                                    pass
                
                completed += 1
                if config.on_progress:
                    config.on_progress(
                        "generating",
                        completed / total_tasks,
                        f"Generated {completed}/{total_tasks}",
                    )
        
        # Run all tasks
        await asyncio.gather(*[process_task(t) for t in tasks])

    async def _generate_single(
        self,
        doc_id: str,
        content: str,
        instructions: str,
        generator: GeneratorType,
        model: str,
        iteration: int,
        progress_callback: Optional[ProgressCallback] = None,
        log_level: str = "INFO",
        run_id: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> Optional[GeneratedDocument]:
        """Generate a single document."""
        started_at = datetime.utcnow()
        
        # Track generation start in live stats
        if self._fpf_stats:
            self._fpf_stats.record_call_start("generation", f"Generating {doc_id} with {model}")
        
        try:
            adapter = self._get_adapter(generator)

            settings = (self.config.model_settings or {}).get(model)
            if not settings:
                raise ValueError(f"Missing model_settings for model {model}")
            provider = settings.get("provider")
            base_model = settings.get("model") or (model.split(":", 1)[1] if ":" in model else model)
            temperature = settings.get("temperature")
            max_tokens = settings.get("max_tokens")
            if not provider:
                raise ValueError(f"provider not set for model {model}")
            if max_tokens is None or max_tokens < 1:
                raise ValueError(f"max_tokens missing for model {model}")
            if temperature is None:
                raise ValueError(f"temperature missing for model {model}")

            # Pass explicit provider/model plus per-model settings
            gen_config = GenerationConfig(
                provider=provider,
                model=base_model,
            )
            
            # pass run-specific task id to adapter via config.extra
            task_id = f"{doc_id}.{generator.value}.{iteration}.{model}"
            if not gen_config.extra:
                gen_config.extra = {}
            gen_config.extra["task_id"] = task_id
            gen_config.extra["max_completion_tokens"] = max_tokens
            gen_config.extra["temperature"] = temperature
            if timeout:
                gen_config.extra["timeout"] = timeout

            # For FPF: query=instructions, document_content=the document
            # For GPTR: query=the document content (GPTR generates research, not processes docs)
            if generator == GeneratorType.FPF:
                # FPF instructions already validated in __post_init__ - should not be empty
                if not instructions:
                    raise ValueError(
                        "FPF requires instructions but none provided. "
                        "This should have been caught in RunConfig validation."
                    )
                
                # Use configured FPF log settings from preset
                fpf_log_output = self.config.fpf_log_output
                fpf_log_file = self.config.fpf_log_file_path
                run_log_file = None
                
                # If file output, ensure log directory exists and set paths
                if run_id and fpf_log_output == 'file':
                    from pathlib import Path
                    log_dir = Path("logs") / run_id
                    log_dir.mkdir(parents=True, exist_ok=True)
                    run_log_file = str(log_dir / "run.log")
                    if not fpf_log_file:
                        # Default file path if not specified - make unique per task to avoid file locking
                        safe_task_id = task_id.replace(":", "_")
                        fpf_log_file = str(log_dir / f"fpf_{safe_task_id}.log")
                
                gen_result = await adapter.generate(
                    query=instructions,  # No fallback - already validated
                    config=gen_config,
                    document_content=content,
                    progress_callback=progress_callback,
                    fpf_log_output=fpf_log_output,
                    fpf_log_file=fpf_log_file,
                    run_log_file=run_log_file,
                )
            else:
                # GPTR and others use query as the research topic
                gen_result = await adapter.generate(
                    query=content,
                    config=gen_config,
                    progress_callback=progress_callback,
                )
            
            completed_at = datetime.utcnow()
            # Create unique doc ID for this generation
            # Use last 8 chars of source doc UUID + 4-char random ID for shorter filenames
            short_doc_id = doc_id[-8:] if len(doc_id) >= 8 else doc_id
            file_uuid = str(uuid4())[:4]
            gen_doc_id = f"{short_doc_id}.{file_uuid}.{generator.value}.{iteration}.{model.replace(':', '_')}"
            
            # Track generation success
            if self._fpf_stats:
                self._fpf_stats.record_success()
            
            return GeneratedDocument(
                doc_id=gen_doc_id,
                content=gen_result.content,
                generator=generator,
                model=model,
                source_doc_id=doc_id,
                iteration=iteration,
                cost_usd=gen_result.cost_usd or 0.0,
                duration_seconds=gen_result.duration_seconds or (completed_at - started_at).total_seconds(),
                started_at=started_at,
                completed_at=completed_at,
            )
            
        except Exception as e:
            self.logger.exception(f"Generation failed: {doc_id} {generator} {model}: {e}")
            # Track generation failure
            if self._fpf_stats:
                self._fpf_stats.record_failure(str(e))
            return None
    
    async def _run_pairwise(
        self,
        config: RunConfig,
        result: RunResult,
    ) -> None:
        """
        Run pairwise evaluation phase.
        
        This runs AFTER all single-doc evaluations are complete.
        Uses single-eval scores for optional top-N filtering.
        """
        # VALIDATE: pairwise_eval_instructions MUST be provided from Content Library
        if not config.pairwise_eval_instructions:
            raise RuntimeError(
                "Pairwise evaluation is enabled but no pairwise_eval_instructions provided. "
                "You must configure pairwise_eval_instructions_id in your preset to point to "
                "a Content Library item containing the pairwise comparison prompt."
            )
        # VALIDATE: eval_judge_models MUST be provided from preset
        if not config.eval_judge_models:
            raise RuntimeError(
                "Pairwise evaluation is enabled but no judge models configured. "
                "You must configure eval_config.judge_models in your preset's config_overrides."
            )
        
        pairwise_config = PairwiseConfig(
            iterations=config.eval_iterations,
            judge_models=config.eval_judge_models,
            top_n=config.pairwise_top_n,
            custom_instructions=config.pairwise_eval_instructions,
            concurrent_limit=config.eval_concurrency,
        )
        evaluator = PairwiseEvaluator(pairwise_config, stats_tracker=self._fpf_stats)
        
        # Collect doc IDs and contents, filtering out empty content
        # Note: All docs in generated_docs are successful (failed generations return None and aren't added)
        valid_docs = [
            doc for doc in result.generated_docs
            if doc.content and len(doc.content.strip()) > 0
        ]
        if len(valid_docs) < len(result.generated_docs):
            failed_count = len(result.generated_docs) - len(valid_docs)
            self.logger.warning(f"Excluding {failed_count} failed/empty documents from pairwise evaluation")
        
        doc_ids = [doc.doc_id for doc in valid_docs]
        contents = {doc.doc_id: doc.content for doc in valid_docs}
        
        # Get single-eval scores for top-N filtering
        scores = None
        if result.single_eval_results and config.pairwise_top_n:
            scores = {
                doc_id: summary.weighted_avg_score
                for doc_id, summary in result.single_eval_results.items()
            }
            doc_ids = evaluator.filter_top_n(doc_ids, scores, config.pairwise_top_n)

        contents = {d: contents[d] for d in doc_ids}
        self.logger.info(f"Filtered to top {len(doc_ids)} docs for pairwise")

        # Run pairwise
        pairwise_started_at = datetime.utcnow()
        summary = await evaluator.evaluate_all_pairs(doc_ids, contents)
        pairwise_completed_at = datetime.utcnow()
        result.pairwise_results = summary
        result.winner_doc_id = summary.winner_doc_id
        
        # Emit pairwise timeline event
        await self._emit_timeline_event(
            run_id=result.run_id,
            phase="pairwise",
            event_type="pairwise_eval",
            description=f"Pairwise evaluation: {summary.total_comparisons} comparisons",
            model=", ".join(config.eval_judge_models) if config.eval_judge_models else None,
            timestamp=pairwise_started_at,
            completed_at=pairwise_completed_at,
            duration_seconds=(pairwise_completed_at - pairwise_started_at).total_seconds(),
            success=True,
            details={
                "total_comparisons": summary.total_comparisons,
                "winner_doc_id": summary.winner_doc_id,
            },
        )
        
        self.logger.info(
            f"Pairwise complete | "
            f"comparisons={summary.total_comparisons} "
            f"winner={summary.winner_doc_id}"
        )
        # Update run store with pairwise results
        if getattr(self, '_run_store', None):
            try:
                self._run_store.update(result.run_id, total_cost_usd=result.total_cost_usd, winner_doc_id=result.winner_doc_id)
                if getattr(self, '_run_ws_manager', None):
                    try:
                        await self._run_ws_manager.broadcast(result.run_id, {"event": "pairwise", "winner": result.winner_doc_id, "run": self._run_store.get(result.run_id)})
                    except Exception:
                        pass
            except Exception:
                pass
    
    async def _run_combine(
        self,
        config: RunConfig,
        result: RunResult,
    ) -> None:
        """Run combine phase with multiple combine models."""
        if not result.winner_doc_id:
            self.logger.warning("Combine skipped: No winner document found")
            return
        
        # VALIDATE: combine_models MUST be provided from preset
        if not config.combine_models:
            raise RuntimeError(
                "Combine is enabled but no combine models configured. "
                "You must configure combine_config.selected_models in your preset's config_overrides."
            )

        try:
            # Use FPF for combination by default
            combine_adapter = CombineAdapter(self._fpf_adapter)
            
            # Get top docs from pairwise results
            top_docs = []
            top_ids = []
            if result.pairwise_results and result.pairwise_results.rankings:
                # rankings returns List[Tuple[str, float]] as (doc_id, rating)
                top_ids = [doc_id for doc_id, rating in result.pairwise_results.rankings[:2]]
                top_docs = [
                    doc.content 
                    for doc in result.generated_docs 
                    if doc.doc_id in top_ids
                ]
            
            if len(top_docs) < 2:
                self.logger.warning("Combine skipped: Need at least 2 top documents")
                return

            # Combine instructions already validated in __post_init__
            combine_instructions = config.combine_instructions
            
            # Get original instructions for context - REQUIRED, no fallback
            if not result.generated_docs:
                raise RuntimeError("Cannot combine: No generated documents available")
            
            source_doc_id = result.generated_docs[0].source_doc_id
            if source_doc_id not in config.document_contents:
                raise ValueError(f"Missing original instructions for source doc: {source_doc_id}")
            
            original_instructions = config.document_contents[source_doc_id]
            if not original_instructions or not original_instructions.strip():
                raise ValueError(f"Original instructions for {source_doc_id} are empty")
            
            # Iterate through ALL combine models - each gets retry attempts
            if not config.combine_models:
                raise ValueError("No combine models configured")
            
            max_retries = config.max_retries
            all_models_failed = True
            
            for model_idx, combine_model in enumerate(config.combine_models):
                # Parse provider:model format - REQUIRED, no fallback
                if ":" not in combine_model:
                    raise ValueError(
                        f"Combine model must be in 'provider:model' format, got: {combine_model}. "
                        "Valid providers: openai, anthropic, google, groq"
                    )
                
                provider, model_name = combine_model.split(":", 1)
                if provider not in ['openai', 'anthropic', 'google', 'groq']:
                    raise ValueError(f"Unknown provider: {provider}. Valid: openai, anthropic, google, groq")
                if not model_name:
                    raise ValueError(f"Model name cannot be empty in: {combine_model}")
                
                combine_gen_config = GenerationConfig(
                    provider=provider,
                    model=model_name,
                )
                
                self.logger.info(f"Combining with model {combine_model} ({model_idx + 1}/{len(config.combine_models)})")
                model_succeeded = False
                
                # Retry logic for this specific model
                for attempt in range(1, max_retries + 1):
                    combine_started_at = datetime.utcnow()
                    try:
                        self.logger.info(f"Combine attempt {attempt}/{max_retries} for {combine_model}")
                        
                        combine_result = await combine_adapter.combine(
                            reports=top_docs,
                            instructions=combine_instructions,
                            config=combine_gen_config,
                            original_instructions=original_instructions
                        )
                        combine_completed_at = datetime.utcnow()
                        combine_duration = (combine_completed_at - combine_started_at).total_seconds()
                        
                        result.total_cost_usd += combine_result.cost_usd
                        
                        # Create unique doc_id with model info
                        safe_model_name = combine_model.replace(":", "_")
                        short_run_id = result.run_id[-8:] if len(result.run_id) >= 8 else result.run_id
                        file_uuid = str(uuid4())[:4]
                        combined_doc_id = f"combined.{short_run_id}.{file_uuid}.{safe_model_name}"
                        
                        # Create GeneratedDocument for combined content
                        combined_doc = GeneratedDocument(
                            doc_id=combined_doc_id,
                            content=combine_result.content,
                            generator=GeneratorType.FPF,
                            model=combine_model,
                            source_doc_id=result.generated_docs[0].source_doc_id if result.generated_docs else "",
                            iteration=1,
                            cost_usd=combine_result.cost_usd,
                            duration_seconds=combine_duration,
                            started_at=combine_started_at,
                            completed_at=combine_completed_at,
                        )
                        
                        # Add to list of combined docs
                        result.combined_docs.append(combined_doc)
                        
                        # Save combined content to file
                        await self._save_generated_content(result.run_id, combined_doc)
                        
                        # Emit combine timeline event
                        await self._emit_timeline_event(
                            run_id=result.run_id,
                            phase="combination",
                            event_type="combine",
                            description=f"Combined documents using {combine_model}",
                            model=combine_model,
                            timestamp=combine_started_at,
                            completed_at=combine_completed_at,
                            duration_seconds=combine_duration,
                            success=True,
                            details={"combined_doc_id": combined_doc_id, "attempt": attempt, "model_index": model_idx},
                        )
                        
                        self.logger.info(f"Combine with {combine_model} succeeded on attempt {attempt}. Cost: ${combine_result.cost_usd:.4f}")
                        model_succeeded = True
                        all_models_failed = False
                        break  # Success for this model, move to next model
                        
                    except Exception as e:
                        self.logger.error(f"Combine attempt {attempt}/{max_retries} for {combine_model} failed: {e}")
                        
                        if attempt < max_retries:
                            # Wait before retry with same model
                            await asyncio.sleep(config.retry_delay)
                        else:
                            # All retries exhausted for this model
                            error_msg = f"Combine with {combine_model} failed after {max_retries} attempts: {str(e)}"
                            result.errors.append(error_msg)
                            self.logger.warning(f"{error_msg} - will try next model if available")
                
                # Continue to next model to get multiple combined docs for comparison
                if model_succeeded:
                    self.logger.info(f"Combine with {combine_model} succeeded, continuing to next model")
            
            # Check if all models failed
            if all_models_failed:
                raise RuntimeError(f"All {len(config.combine_models)} combine models failed after {max_retries} retries each")
            
            self.logger.info(f"Combine phase complete. Total combined docs: {len(result.combined_docs)}")
            
        except Exception as e:
            self.logger.error(f"Combine failed: {e}", exc_info=True)
            result.errors.append(f"Combine failed: {str(e)}")

    async def _run_post_combine_eval(
        self,
        config: RunConfig,
        result: RunResult,
    ) -> None:
        """
        Run post-combine pairwise evaluation.
        
        Compares combined documents against the top-ranked originals that were sent to the combiner.
        This validates whether combining improved quality vs individual winners.
        """
        if not result.combined_docs:
            self.logger.warning("Post-combine eval skipped: No combined documents produced")
            return

        if not config.enable_pairwise:
            self.logger.info("Post-combine eval skipped: Pairwise evaluation disabled in config")
            return

        if config.post_combine_top_n is None:
            self.logger.info("Post-combine eval skipped: post_combine_top_n not configured")
            return

        try:
            # Create pairwise config with same settings as pre-combine
            # Use post_combine_top_n if configured, otherwise compare all
            pairwise_config = PairwiseConfig(
                iterations=config.eval_iterations,
                judge_models=config.eval_judge_models,
                top_n=config.post_combine_top_n,  # Use config value, not hardcoded None
                custom_instructions=config.pairwise_eval_instructions,
                concurrent_limit=config.eval_concurrency,
            )
            evaluator = PairwiseEvaluator(pairwise_config, stats_tracker=self._fpf_stats)
            
            # Collect documents for comparison
            all_doc_ids = []
            all_contents = {}
            
            # Get the original docs that were sent to combiner (top-ranked from pairwise)
            # FAIL FAST - post-combine eval requires pairwise rankings
            if not result.pairwise_results or not result.pairwise_results.rankings:
                raise ValueError(
                    "Post-combine evaluation requires pairwise rankings to determine which "
                    "documents were sent to combiner. Enable pairwise evaluation in preset, "
                    "or disable post-combine evaluation."
                )
            
            # Get top 2 that were used for combining
            docs_sent_to_combiner = [doc_id for doc_id, rating in result.pairwise_results.rankings[:2]]
            
            # Add original docs that went into combiner
            for doc in result.generated_docs:
                if doc.doc_id in docs_sent_to_combiner:
                    all_doc_ids.append(doc.doc_id)
                    all_contents[doc.doc_id] = doc.content
            
            # Add all combined docs
            for combined_doc in result.combined_docs:
                all_doc_ids.append(combined_doc.doc_id)
                all_contents[combined_doc.doc_id] = combined_doc.content
            
            # Validate we have enough documents
            if len(all_doc_ids) < 2:
                self.logger.error(
                    f"Post-combine eval failed: Need at least 2 documents for comparison, "
                    f"but only have {len(all_doc_ids)} (originals: {len(docs_sent_to_combiner)}, "
                    f"combined: {len(result.combined_docs)})"
                )
                return
            
            self.logger.info(
                f"Post-combine pairwise starting: {len(all_doc_ids)} documents total "
                f"({len(docs_sent_to_combiner)} originals + {len(result.combined_docs)} combined)"
            )
            
            # Run pairwise evaluation
            summary = await evaluator.evaluate_all_pairs(all_doc_ids, all_contents)
            result.post_combine_eval_results = summary
            
            self.logger.info(
                f"Post-combine pairwise complete | "
                f"winner={summary.winner_doc_id} | "
                f"comparisons={summary.total_comparisons} | "
                f"pairs={summary.total_pairs}"
            )
            
            # Broadcast results via WebSocket
            if getattr(self, '_run_store', None):
                try:
                    if getattr(self, '_run_ws_manager', None):
                        await self._run_ws_manager.broadcast(result.run_id, {
                            "event": "post_combine_eval_complete", 
                            "winner": summary.winner_doc_id,
                            "total_comparisons": summary.total_comparisons,
                        })
                except Exception as e:
                    self.logger.warning(f"Failed to broadcast post-combine eval results: {e}")

        except Exception as e:
            self.logger.error(f"Post-combine eval failed: {e}", exc_info=True)
            result.errors.append(f"Post-combine eval failed: {str(e)}")
    
    def cancel(self) -> None:
        """Cancel the running execution."""
        self._cancelled = True


# Note: RunExecutor instances are created per-run by callers to ensure
# cancellation and internal state do not leak between runs.


def get_executor() -> RunExecutor:
    """Compatibility shim: return a fresh RunExecutor instance.

    Old code imported `get_executor()` expecting a singleton; we return
    a new instance to preserve per-run isolation while keeping imports
    working for older modules.
    """
    logging.getLogger(__name__).debug("get_executor() called - returning new RunExecutor instance")
    return RunExecutor()
