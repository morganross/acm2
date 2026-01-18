"""
Source Document Pipeline.

Encapsulates the complete execution pipeline for a single source document.
Each source document runs through its own isolated pipeline:
  Generation → Single Eval → Pairwise → Combine → Post-Combine Eval

Documents NEVER compete across source doc boundaries - each produces its own winner.

This supports pipelined concurrency where multiple SourceDocPipelines can run
simultaneously, sharing a global API semaphore for rate limiting.
"""

import asyncio
import logging
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from uuid import uuid4

from ..adapters.base import GenerationConfig, GeneratorType, ProgressCallback
from ..adapters.fpf.adapter import FpfAdapter
from ..adapters.gptr.adapter import GptrAdapter
from ..adapters.dr.adapter import DrAdapter
from ..adapters.combine.adapter import CombineAdapter
from ..evaluation import (
    DocumentInput,
    SingleDocEvaluator,
    SingleEvalConfig,
    SingleEvalSummary,
    PairwiseEvaluator,
    PairwiseConfig,
    PairwiseSummary,
    FpfStatsTracker,
)
from ..evaluation.models import EvaluationCriterion
from ..evaluation.criteria import CriteriaManager
from .rate_limiter import RateLimitedRequest

from .run_executor import (
    RunConfig,
    RunPhase,
    GeneratedDocument,
    SourceDocResult,
)


class SourceDocPipeline:
    """
    Executes the full pipeline for a single source document.
    
    Each source document is completely isolated - its generated variations
    only compete against each other, never against other source documents.
    
    The pipeline phases are serial within a document:
    1. Generation + Single Eval (concurrent API calls within phase)
    2. Pairwise Evaluation (after all generation complete)
    3. Combine (merge top docs)
    4. Post-Combine Eval (optional)
    
    Multiple SourceDocPipelines can run concurrently, sharing a global API
    semaphore for rate limiting across all pipelines.
    """
    
    def __init__(
        self,
        source_doc_id: str,
        source_doc_name: str,
        content: str,
        config: RunConfig,
        run_id: str,
        shared_semaphore: asyncio.Semaphore,
        stats_tracker: Optional[FpfStatsTracker] = None,
        fpf_adapter: Optional[FpfAdapter] = None,
        gptr_adapter: Optional[GptrAdapter] = None,
        dr_adapter: Optional[DrAdapter] = None,
        logger: Optional[logging.Logger] = None,
        ws_manager: Optional[Any] = None,
        run_store: Optional[Any] = None,
        on_timeline_event: Optional[Callable] = None,
    ):
        """
        Initialize a source document pipeline.
        
        Args:
            source_doc_id: Unique ID for this source document
            source_doc_name: Human-readable name for UI display
            content: The actual document content to process
            config: Full run configuration (shared across all pipelines)
            run_id: The parent run ID
            shared_semaphore: API rate limiting semaphore (shared across all pipelines)
            stats_tracker: FPF stats tracker (shared across all pipelines)
            fpf_adapter: Shared FPF adapter instance
            gptr_adapter: Shared GPTR adapter instance
            dr_adapter: Shared DR adapter instance
            logger: Logger instance (uses module logger if not provided)
            ws_manager: WebSocket manager for live updates
            run_store: Run store for persisting progress
            on_timeline_event: Callback for timeline events
        """
        self.source_doc_id = source_doc_id
        self.source_doc_name = source_doc_name
        self.content = content
        self.config = config
        self.run_id = run_id
        self.semaphore = shared_semaphore
        self.stats = stats_tracker
        self.logger = logger or logging.getLogger(__name__)
        self.ws_manager = ws_manager
        self.run_store = run_store
        self.on_timeline_event = on_timeline_event
        
        # Adapters (shared across pipelines for efficiency)
        self._fpf_adapter = fpf_adapter or FpfAdapter()
        self._gptr_adapter = gptr_adapter or GptrAdapter()
        self._dr_adapter = dr_adapter or DrAdapter()
        
        # Cancellation flag (can be set externally)
        self._cancelled = False

    def _get_run_root(self) -> Path:
        from ..config import get_settings

        settings = get_settings()
        return settings.data_dir / f"user_{self.config.user_id}" / "runs" / self.run_id
        
    def cancel(self) -> None:
        """Cancel this pipeline."""
        self._cancelled = True
        
    def _get_adapter(self, generator: GeneratorType):
        """Get the appropriate adapter for a generator type."""
        if generator == GeneratorType.FPF:
            return self._fpf_adapter
        elif generator == GeneratorType.GPTR:
            return self._gptr_adapter
        elif generator == GeneratorType.DR:
            return self._dr_adapter
        raise ValueError(f"Unknown generator type: {generator}")
        
    async def run(self) -> SourceDocResult:
        """
        Execute the full pipeline for this source document.
        
        Returns:
            SourceDocResult containing all results for this document
        """
        started_at = datetime.utcnow()
        
        result = SourceDocResult(
            source_doc_id=self.source_doc_id,
            source_doc_name=self.source_doc_name,
            status=RunPhase.GENERATING,
            generated_docs=[],
            single_eval_results={},
            pairwise_results=None,
            winner_doc_id=None,
            combined_doc=None,
            post_combine_eval_results=None,
            timeline_events=[],
            errors=[],
            cost_usd=0.0,
            duration_seconds=0.0,
            started_at=started_at,
            completed_at=None,
        )
        
        try:
            # Phase 1: Generation with streaming single eval
            self.logger.info(f"Pipeline [{self.source_doc_name}]: Starting generation phase")
            await self._run_generation_with_eval(result)
            
            if self._cancelled:
                result.status = RunPhase.CANCELLED
                result.completed_at = datetime.utcnow()
                result.duration_seconds = (result.completed_at - started_at).total_seconds()
                return result
            
            # Check if we have any successful generations
            if not result.generated_docs:
                result.status = RunPhase.FAILED
                result.errors.append("No documents were generated successfully")
                result.completed_at = datetime.utcnow()
                result.duration_seconds = (result.completed_at - started_at).total_seconds()
                return result
            
            # Calculate deviations after all single evals complete
            if result.single_eval_results and len(result.single_eval_results) > 0:
                from ..evaluation.single_doc import SingleEvalSummary
                deviations = SingleEvalSummary.calculate_deviations(result.single_eval_results)
                # Attach deviations to each summary
                for doc_id, summary in result.single_eval_results.items():
                    summary.deviations_by_judge_criterion = deviations
                self.logger.info(f"Pipeline [{self.source_doc_name}]: Calculated deviations for {len(deviations)} judges")
            
            # Phase 2: Pairwise evaluation
            if self.config.enable_pairwise and len(result.generated_docs) >= 2:
                result.status = RunPhase.PAIRWISE_EVAL
                self.logger.info(f"Pipeline [{self.source_doc_name}]: Starting pairwise phase with {len(result.generated_docs)} docs")
                await self._run_pairwise(result)
                
                if self._cancelled:
                    result.status = RunPhase.CANCELLED
                    result.completed_at = datetime.utcnow()
                    result.duration_seconds = (result.completed_at - started_at).total_seconds()
                    return result
            
            # Determine winner from single eval if pairwise was disabled
            if not result.winner_doc_id and result.single_eval_results and self.config.enable_combine:
                doc_scores = {}
                for doc_id, summary in result.single_eval_results.items():
                    if hasattr(summary, 'avg_score') and summary.avg_score is not None:
                        doc_scores[doc_id] = summary.avg_score
                if doc_scores:
                    result.winner_doc_id = max(doc_scores, key=doc_scores.get)
                    self.logger.info(f"Pipeline [{self.source_doc_name}]: Winner from single eval: {result.winner_doc_id}")
            
            # Phase 3: Combine
            if self.config.enable_combine and result.winner_doc_id:
                result.status = RunPhase.COMBINING
                self.logger.info(f"Pipeline [{self.source_doc_name}]: Starting combine phase")
                await self._run_combine(result)
                
                if self._cancelled:
                    result.status = RunPhase.CANCELLED
                    result.completed_at = datetime.utcnow()
                    result.duration_seconds = (result.completed_at - started_at).total_seconds()
                    return result
            
            # Phase 4: Post-combine evaluation
            if self.config.enable_combine and result.combined_docs and self.config.enable_pairwise:
                result.status = RunPhase.POST_COMBINE_EVAL
                self.logger.info(f"Pipeline [{self.source_doc_name}]: Starting post-combine eval")
                await self._run_post_combine_eval(result)
            
            # Mark as complete
            result.status = RunPhase.COMPLETED
            result.completed_at = datetime.utcnow()
            result.duration_seconds = (result.completed_at - started_at).total_seconds()
            
            self.logger.info(
                f"Pipeline [{self.source_doc_name}]: Completed | "
                f"docs={len(result.generated_docs)} "
                f"winner={result.winner_doc_id} "
                f"cost=${result.cost_usd:.4f}"
            )
            
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            self.logger.error(f"Pipeline [{self.source_doc_name}] failed: {e}\n{tb}")
            result.status = RunPhase.FAILED
            result.errors.append(str(e))
            result.errors.append(tb)
            result.completed_at = datetime.utcnow()
            result.duration_seconds = (result.completed_at - started_at).total_seconds()
        
        return result
    
    async def _emit_timeline_event(
        self,
        phase: str,
        event_type: str,
        description: str,
        model: Optional[str] = None,
        timestamp: Optional[datetime] = None,
        completed_at: Optional[datetime] = None,
        duration_seconds: Optional[float] = None,
        success: bool = True,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Emit a timeline event for this source document."""
        event = {
            "source_doc_id": self.source_doc_id,
            "source_doc_name": self.source_doc_name,
            "phase": phase,
            "event_type": event_type,
            "description": description,
            "model": model,
            "timestamp": (timestamp or datetime.utcnow()).isoformat(),
            "completed_at": completed_at.isoformat() if completed_at else None,
            "duration_seconds": duration_seconds,
            "success": success,
            "details": details or {},
        }
        
        # Call the timeline event callback if provided
        if self.on_timeline_event:
            try:
                await self.on_timeline_event(self.run_id, event)
            except Exception as e:
                self.logger.warning(f"Timeline event callback failed: {e}")
    
    async def _save_generated_content(self, gen_doc: GeneratedDocument) -> None:
        """Save generated document content to a file for later retrieval.
        
        Files are stored in data/user_{user_id}/runs/{run_id}/generated/{doc_id}.md
        """
        import aiofiles
        
        try:
            # Validate content before saving
            if not gen_doc.content:
                raise ValueError(f"Cannot save document {gen_doc.doc_id}: content is None or empty")
            
            if not gen_doc.content.strip():
                raise ValueError(f"Cannot save document {gen_doc.doc_id}: content is only whitespace")
            
            # Create directory structure
            gen_dir = self._get_run_root() / "generated"
            gen_dir.mkdir(parents=True, exist_ok=True)
            
            # Sanitize doc_id for filename (replace invalid chars)
            safe_doc_id = gen_doc.doc_id.replace(':', '_').replace('/', '_').replace('\\', '_')
            file_path = gen_dir / f"{safe_doc_id}.md"
            
            # Write content
            async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
                await f.write(gen_doc.content)
            
            self.logger.debug(f"Pipeline [{self.source_doc_name}]: Saved generated content to {file_path}")
        except Exception as e:
            self.logger.error(f"Pipeline [{self.source_doc_name}]: Failed to save generated content for {gen_doc.doc_id}: {e}")
            raise RuntimeError(f"Failed to save {gen_doc.doc_id}: {e}") from e
    
    async def _run_generation_with_eval(self, result: SourceDocResult) -> None:
        """
        Generate variations for THIS source doc only, with streaming single eval.
        
        Each document is evaluated IMMEDIATELY after generation, not waiting
        for other documents to complete.
        """
        # Build task list: (generator, model, iteration)
        tasks = []
        for generator in self.config.generators:
            generator_models = self.config.get_models_for_generator(generator)
            for model in generator_models:
                for iteration in range(1, self.config.iterations + 1):
                    tasks.append((generator, model, iteration))
        
        total_tasks = len(tasks)
        completed = 0
        
        # Initialize run_store tasks list so WebSocket clients see initial progress
        if self.run_store:
            try:
                initial_tasks = []
                for generator, model, iteration in tasks:
                    task_id = f"{self.source_doc_id}.{generator.value}.{iteration}.{model}"
                    initial_tasks.append({
                        "id": task_id,
                        "document_id": self.source_doc_id,
                        "document_name": self.source_doc_name,
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
                # Append to existing tasks (multi-doc has multiple source docs)
                existing_run = self.run_store.get(self.run_id)
                if existing_run and 'tasks' in existing_run:
                    all_tasks = existing_run['tasks'] + initial_tasks
                else:
                    all_tasks = initial_tasks
                self.run_store.update(self.run_id, tasks=all_tasks)
                if self.ws_manager:
                    try:
                        await self.ws_manager.broadcast(self.run_id, {"event": "init", "tasks": all_tasks})
                    except Exception:
                        pass
            except Exception as e:
                self.logger.warning(f"Pipeline [{self.source_doc_name}]: Failed to initialize run_store tasks: {e}")
        
        # Setup single-doc evaluator if enabled
        single_evaluator = None
        if self.config.enable_single_eval:
            eval_config = SingleEvalConfig(
                iterations=self.config.eval_iterations,
                judge_models=self.config.eval_judge_models,
                custom_instructions=self.config.single_eval_instructions,
                custom_criteria=self.config.eval_criteria,
                concurrent_limit=self.config.eval_concurrency,
                timeout_seconds=self.config.eval_timeout,
                temperature=self.config.eval_temperature,
                max_tokens=self.config.eval_max_tokens,
                retries=self.config.eval_retries,
                strict_json=self.config.eval_strict_json,
            )
            single_evaluator = SingleDocEvaluator(eval_config, stats_tracker=self.stats)
        
        async def process_task(task_info):
            nonlocal completed
            generator, model, iteration = task_info
            
            async with self.semaphore:  # Shared across all pipelines
                if self._cancelled:
                    return
                
                # Create unique task ID
                task_id = f"{self.source_doc_id}.{generator.value}.{iteration}.{model}"
                
                # Update run_store: mark task as running
                if self.run_store:
                    try:
                        run = self.run_store.get(self.run_id)
                        if run and 'tasks' in run:
                            tasks_list = run['tasks']
                            for t in tasks_list:
                                if t['id'] == task_id:
                                    t['status'] = 'running'
                                    t['progress'] = 0.05
                                    t['message'] = 'started'
                                    t['started_at'] = datetime.utcnow()
                                    break
                            self.run_store.update(self.run_id, tasks=tasks_list)
                            if self.ws_manager:
                                try:
                                    await self.ws_manager.broadcast(self.run_id, {"event": "task_update", "task": t})
                                except Exception:
                                    pass
                    except Exception as e:
                        self.logger.warning(f"Failed to update run_store task status: {e}")
                
                # Create progress callback for this task
                async def _progress_callback(stage: str, progress: float, message: Optional[str]):
                    """Update task progress in run_store and broadcast via WebSocket."""
                    if self.run_store:
                        try:
                            run = self.run_store.get(self.run_id)
                            if run and 'tasks' in run:
                                tasks_list = run['tasks']
                                for tt in tasks_list:
                                    if tt['id'] == task_id:
                                        tt['progress'] = progress
                                        tt['message'] = message
                                        break
                                self.run_store.update(self.run_id, tasks=tasks_list)
                                if self.ws_manager:
                                    try:
                                        await self.ws_manager.broadcast(self.run_id, {"event": "task_update", "task": tt})
                                    except Exception:
                                        pass
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
                    generator=generator,
                    model=model,
                    iteration=iteration,
                    task_id=task_id,
                    progress_callback=_progress_callback,
                )
                
                if gen_result:
                    result.generated_docs.append(gen_result)
                    result.cost_usd += gen_result.cost_usd
                    
                    # Save generated content to file for later retrieval
                    await self._save_generated_content(gen_result)
                    
                    # Broadcast gen_complete via WebSocket for live UI updates
                    if self.ws_manager:
                        try:
                            await self.ws_manager.broadcast(self.run_id, {
                                "event": "gen_complete",
                                "doc_id": gen_result.doc_id,
                                "model": model,
                                "generator": generator.value,
                                "source_doc_id": self.source_doc_id,
                                "iteration": iteration,
                                "duration_seconds": gen_result.duration_seconds,
                            })
                        except Exception:
                            pass
                    
                    # Fire on_gen_complete callback to save generated_docs incrementally to DB
                    if self.config.on_gen_complete:
                        try:
                            self.logger.info(f"Pipeline [{self.source_doc_name}]: Calling on_gen_complete for {gen_result.doc_id}")
                            await self.config.on_gen_complete(
                                gen_result.doc_id,
                                model,
                                generator.value,
                                self.source_doc_id,  # source_doc_id
                                iteration,
                            )
                            self.logger.info(f"Pipeline [{self.source_doc_name}]: on_gen_complete succeeded for {gen_result.doc_id}")
                        except Exception as e:
                            self.logger.exception(f"Pipeline [{self.source_doc_name}]: on_gen_complete callback failed: {e}")
                    
                    # Emit generation timeline event
                    await self._emit_timeline_event(
                        phase="generation",
                        event_type="generation",
                        description=f"Generated doc using {generator.value}",
                        model=model,
                        timestamp=gen_result.started_at,
                        completed_at=gen_result.completed_at,
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
                            summary = await single_evaluator.evaluate_document(
                                eval_input,
                                on_eval_complete=self.config.on_eval_complete,
                            )
                            result.single_eval_results[gen_result.doc_id] = summary
                            eval_completed_at = datetime.utcnow()
                            
                            # Emit single eval timeline event
                            await self._emit_timeline_event(
                                phase="evaluation",
                                event_type="single_eval",
                                description=f"Evaluated {gen_result.doc_id[:20]}...",
                                model=", ".join(self.config.eval_judge_models) if self.config.eval_judge_models else None,
                                timestamp=eval_started_at,
                                completed_at=eval_completed_at,
                                duration_seconds=(eval_completed_at - eval_started_at).total_seconds(),
                                success=True,
                                details={
                                    "doc_id": gen_result.doc_id,
                                    "average_score": summary.avg_score,
                                },
                            )
                            
                            self.logger.info(
                                f"Pipeline [{self.source_doc_name}]: Single eval complete: {gen_result.doc_id} | "
                                f"avg={summary.avg_score:.2f}"
                            )
                        except Exception as e:
                            self.logger.error(f"Pipeline [{self.source_doc_name}]: Single eval failed for {gen_result.doc_id}: {e}")
                            result.errors.append(f"Single eval failed: {gen_result.doc_id}")
                    
                    # Update run_store: mark task completed
                    if self.run_store:
                        try:
                            run = self.run_store.get(self.run_id)
                            if run and 'tasks' in run:
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
                                self.run_store.update(self.run_id, tasks=tasks_list, total_cost_usd=result.cost_usd)
                                if self.ws_manager:
                                    try:
                                        await self.ws_manager.broadcast(self.run_id, {"event": "task_update", "task": t})
                                    except Exception:
                                        pass
                        except Exception as e:
                            self.logger.warning(f"Failed to update run_store task completion: {e}")
                
                completed += 1
                if self.config.on_progress:
                    self.config.on_progress(
                        "generating",
                        completed / total_tasks,
                        f"[{self.source_doc_name}] Generated {completed}/{total_tasks}",
                    )
        
        # Run all tasks - return_exceptions=True ensures one failure doesn't abort others
        task_results = await asyncio.gather(*[process_task(t) for t in tasks], return_exceptions=True)
        
        # Log any exceptions that occurred
        for i, task_result in enumerate(task_results):
            if isinstance(task_result, Exception):
                generator, model, iteration = tasks[i]
                task_id = f"{self.source_doc_id}.{generator.value}.{iteration}.{model}"
                self.logger.error(f"Pipeline [{self.source_doc_name}]: Task {task_id} failed: {task_result}")
                result.errors.append(f"Task {task_id} failed: {str(task_result)}")
    
    async def _generate_single(
        self,
        generator: GeneratorType,
        model: str,
        iteration: int,
        task_id: Optional[str] = None,
        progress_callback: Optional[Callable] = None,
    ) -> Optional[GeneratedDocument]:
        """Generate a single document for this source doc."""
        started_at = datetime.utcnow()
        
        # Track generation start in live stats
        if self.stats:
            self.stats.record_call_start("generation", f"Generating {self.source_doc_id} with {model}")
        
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
            
            # Create generation config
            gen_config = GenerationConfig(
                provider=provider,
                model=base_model,
            )
            
            # Create task ID for tracking
            task_id = f"{self.source_doc_id}.{generator.value}.{iteration}.{model}"
            if not gen_config.extra:
                gen_config.extra = {}
            gen_config.extra["task_id"] = task_id
            gen_config.extra["max_completion_tokens"] = max_tokens
            gen_config.extra["temperature"] = temperature
            if self.config.request_timeout:
                gen_config.extra["timeout"] = self.config.request_timeout
            
            # Pass FPF retry settings
            gen_config.extra["fpf_max_retries"] = self.config.fpf_max_retries
            gen_config.extra["fpf_retry_delay"] = self.config.fpf_retry_delay
            
            # Build instructions with optional criteria exposure
            instructions = self.config.instructions
            if self.config.expose_criteria_to_generators and self.config.eval_criteria:
                criteria_header = """

=== EVALUATION CRITERIA (Your output will be judged on these) ===
The following criteria will be used to evaluate your output. 
Optimize your response to score highly on each criterion:

"""
                instructions = (instructions or "") + criteria_header + self.config.eval_criteria
            
            # Generate based on adapter type
            if generator == GeneratorType.FPF:
                if not instructions:
                    raise ValueError("FPF requires instructions")
                
                # Use configured FPF log settings from preset
                fpf_log_output = self.config.fpf_log_output
                fpf_log_file = self.config.fpf_log_file_path
                run_log_file = None
                
                # If file output, ensure log directory exists and set paths
                if self.run_id and fpf_log_output == 'file':
                    log_dir = self._get_run_root() / "logs"
                    log_dir.mkdir(parents=True, exist_ok=True)
                    run_log_file = str(log_dir / "run.log")
                    if not fpf_log_file:
                        raise ValueError("fpf_log_file_path required when fpf_log_output='file'")
                
                # Apply provider-level rate limiting
                async with RateLimitedRequest(provider):
                    gen_result = await adapter.generate(
                        query=instructions,
                        config=gen_config,
                        document_content=self.content,
                        progress_callback=progress_callback,
                        fpf_log_output=fpf_log_output,
                        fpf_log_file=fpf_log_file,
                        run_log_file=run_log_file,
                    )
            else:
                # GPTR and others use query as the research topic
                query_parts = []
                if instructions:
                    query_parts.append(instructions)
                query_parts.append(self.content)
                full_query = "\n\n".join(query_parts)
                
                async with RateLimitedRequest(provider):
                    gen_result = await adapter.generate(
                        query=full_query,
                        config=gen_config,
                        progress_callback=progress_callback,
                    )
            
            completed_at = datetime.utcnow()
            
            # Create unique doc ID
            short_doc_id = self.source_doc_id[-8:] if len(self.source_doc_id) >= 8 else self.source_doc_id
            file_uuid = str(uuid4())[:4]
            gen_doc_id = f"{short_doc_id}.{file_uuid}.{generator.value}.{iteration}.{model.replace(':', '_')}"
            
            # Track generation success
            if self.stats:
                self.stats.record_success()
            
            return GeneratedDocument(
                doc_id=gen_doc_id,
                content=gen_result.content,
                generator=generator,
                model=model,
                source_doc_id=self.source_doc_id,
                iteration=iteration,
                cost_usd=gen_result.cost_usd or 0.0,
                duration_seconds=gen_result.duration_seconds or (completed_at - started_at).total_seconds(),
                started_at=started_at,
                completed_at=completed_at,
            )
            
        except Exception as e:
            self.logger.exception(f"Pipeline [{self.source_doc_name}]: Generation failed: {generator} {model}: {e}")
            if self.stats:
                self.stats.record_failure(str(e))
            return None
    
    async def _run_pairwise(self, result: SourceDocResult) -> None:
        """
        Run pairwise evaluation for THIS source doc's variations only.
        
        Only compares documents generated from this source document.
        """
        import yaml
        
        pairwise_config = PairwiseConfig(
            iterations=self.config.eval_iterations,
            judge_models=self.config.eval_judge_models,
            top_n=self.config.pairwise_top_n,
            custom_instructions=self.config.pairwise_eval_instructions,
            concurrent_limit=self.config.eval_concurrency,
        )
        
        # Create CriteriaManager with criteria from Content Library
        criteria_manager = CriteriaManager()
        if self.config.eval_criteria:
            try:
                data = yaml.safe_load(self.config.eval_criteria)
                if data and "criteria" in data:
                    parsed_criteria = []
                    for item in data["criteria"]:
                        if isinstance(item, str):
                            parsed_criteria.append(EvaluationCriterion(
                                name=item,
                                description=f"Evaluate the {item} of the document.",
                            ))
                        elif isinstance(item, dict) and "name" in item:
                            parsed_criteria.append(EvaluationCriterion(
                                name=item["name"],
                                description=item.get("description", f"Evaluate the {item['name']}."),
                            ))
                    if parsed_criteria:
                        criteria_manager.set_criteria(parsed_criteria)
            except Exception as e:
                self.logger.error(f"Pipeline [{self.source_doc_name}]: Failed to parse eval_criteria YAML: {e}")
        
        evaluator = PairwiseEvaluator(pairwise_config, criteria_manager=criteria_manager, stats_tracker=self.stats)
        
        # Filter out empty content
        valid_docs = [
            doc for doc in result.generated_docs
            if doc.content and len(doc.content.strip()) > 0
        ]
        
        if len(valid_docs) < 2:
            self.logger.warning(f"Pipeline [{self.source_doc_name}]: Skipping pairwise - need at least 2 valid docs, have {len(valid_docs)}")
            return
        
        doc_ids = [doc.doc_id for doc in valid_docs]
        contents = {doc.doc_id: doc.content for doc in valid_docs}
        
        # Get single-eval scores for top-N filtering
        if result.single_eval_results and self.config.pairwise_top_n:
            scores = {
                doc_id: summary.avg_score
                for doc_id, summary in result.single_eval_results.items()
                if summary.avg_score is not None
            }
            if scores:
                doc_ids = evaluator.filter_top_n(doc_ids, scores, self.config.pairwise_top_n)
                contents = {d: contents[d] for d in doc_ids}
                self.logger.info(f"Pipeline [{self.source_doc_name}]: Filtered to top {len(doc_ids)} docs for pairwise")
        
        # Run pairwise
        pairwise_started_at = datetime.utcnow()
        summary = await evaluator.evaluate_all_pairs(doc_ids, contents)
        pairwise_completed_at = datetime.utcnow()
        
        # Calculate pairwise deviations
        if summary.results:
            from app.evaluation.pairwise import PairwiseSummary
            summary.deviations_by_judge = PairwiseSummary.calculate_deviations(summary.results)
            self.logger.info(
                f"Pipeline [{self.source_doc_name}]: Calculated pairwise deviations for "
                f"{len(summary.deviations_by_judge)} judges"
            )
        
        result.pairwise_results = summary
        result.winner_doc_id = summary.winner_doc_id
        
        # Emit pairwise timeline event
        await self._emit_timeline_event(
            phase="pairwise",
            event_type="pairwise_eval",
            description=f"Pairwise evaluation: {summary.total_comparisons} comparisons",
            model=", ".join(self.config.eval_judge_models) if self.config.eval_judge_models else None,
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
            f"Pipeline [{self.source_doc_name}]: Pairwise complete | "
            f"comparisons={summary.total_comparisons} "
            f"winner={summary.winner_doc_id}"
        )
    
    async def _run_combine(self, result: SourceDocResult) -> None:
        """Run combine phase for THIS source doc."""
        if not result.winner_doc_id:
            self.logger.warning(f"Pipeline [{self.source_doc_name}]: Combine skipped - no winner")
            return
        
        if not self.config.combine_models:
            self.logger.warning(f"Pipeline [{self.source_doc_name}]: Combine skipped - no models configured")
            return
        
        try:
            combine_adapter = CombineAdapter(self._fpf_adapter)
            
            # Get top docs from pairwise results
            top_docs = []
            if result.pairwise_results and result.pairwise_results.rankings:
                top_ids = [doc_id for doc_id, rating in result.pairwise_results.rankings[:2]]
                top_docs = [
                    doc.content
                    for doc in result.generated_docs
                    if doc.doc_id in top_ids
                ]
            
            if len(top_docs) < 2:
                self.logger.warning(f"Pipeline [{self.source_doc_name}]: Combine skipped - need at least 2 top docs")
                return
            
            combine_instructions = self.config.combine_instructions
            original_instructions = self.content  # The source document content
            
            # Try each combine model
            for model_idx, combine_model in enumerate(self.config.combine_models):
                if ":" not in combine_model:
                    self.logger.error(f"Pipeline [{self.source_doc_name}]: Invalid combine model format: {combine_model}")
                    continue
                
                provider, model_name = combine_model.split(":", 1)
                
                safe_model_name = combine_model.replace(":", "_")
                combine_task_id = f"{self.source_doc_id[-8:]}.combine.{model_idx}.{safe_model_name}"
                
                combine_gen_config = GenerationConfig(
                    provider=provider,
                    model=model_name,
                    extra={
                        "task_id": combine_task_id,
                        "max_completion_tokens": self.config.combine_max_tokens,
                    },
                )
                
                combine_started_at = datetime.utcnow()
                try:
                    self.logger.info(f"Pipeline [{self.source_doc_name}]: Combining with {combine_model}")
                    
                    combine_result = await combine_adapter.combine(
                        reports=top_docs,
                        instructions=combine_instructions,
                        config=combine_gen_config,
                        original_instructions=original_instructions,
                    )
                    combine_completed_at = datetime.utcnow()
                    combine_duration = (combine_completed_at - combine_started_at).total_seconds()
                    
                    result.cost_usd += combine_result.cost_usd
                    
                    # Create unique doc_id
                    short_source_id = self.source_doc_id[-8:] if len(self.source_doc_id) >= 8 else self.source_doc_id
                    file_uuid = str(uuid4())[:4]
                    combined_doc_id = f"combined.{short_source_id}.{file_uuid}.{safe_model_name}"
                    
                    # Create GeneratedDocument for combined content
                    combined_doc = GeneratedDocument(
                        doc_id=combined_doc_id,
                        content=combine_result.content,
                        generator=GeneratorType.FPF,
                        model=combine_model,
                        source_doc_id=self.source_doc_id,
                        iteration=1,
                        cost_usd=combine_result.cost_usd,
                        duration_seconds=combine_duration,
                        started_at=combine_started_at,
                        completed_at=combine_completed_at,
                    )
                    
                    result.combined_doc = combined_doc
                    result.combined_docs.append(combined_doc)  # Add to list of all combined docs
                    
                    # Save combined content to file
                    await self._save_generated_content(combined_doc)
                    
                    # Emit combine timeline event
                    await self._emit_timeline_event(
                        phase="combination",
                        event_type="combine",
                        description=f"Combined documents using {combine_model}",
                        model=combine_model,
                        timestamp=combine_started_at,
                        completed_at=combine_completed_at,
                        duration_seconds=combine_duration,
                        success=True,
                        details={"combined_doc_id": combined_doc_id},
                    )
                    
                    self.logger.info(f"Pipeline [{self.source_doc_name}]: Combine with {combine_model} succeeded")
                    # Continue to next model - don't break, process all combine models
                    
                except Exception as e:
                    self.logger.error(f"Pipeline [{self.source_doc_name}]: Combine with {combine_model} failed: {e}")
                    result.errors.append(f"Combine with {combine_model} failed: {str(e)}")
            
            if not result.combined_docs:
                result.errors.append(f"All {len(self.config.combine_models)} combine models failed")
                
        except Exception as e:
            self.logger.error(f"Pipeline [{self.source_doc_name}]: Combine failed: {e}")
            result.errors.append(f"Combine failed: {str(e)}")
    
    async def _run_post_combine_eval(self, result: SourceDocResult) -> None:
        """Run post-combine pairwise evaluation for THIS source doc."""
        if not result.combined_docs:
            self.logger.warning(f"Pipeline [{self.source_doc_name}]: Post-combine eval skipped - no combined docs")
            return
        
        if not result.pairwise_results or not result.pairwise_results.rankings:
            self.logger.warning(f"Pipeline [{self.source_doc_name}]: Post-combine eval skipped - no pairwise rankings")
            return
        
        try:
            import yaml
            
            pairwise_config = PairwiseConfig(
                iterations=self.config.eval_iterations,
                judge_models=self.config.eval_judge_models,
                top_n=None,  # Compare all docs
                custom_instructions=self.config.pairwise_eval_instructions,
                concurrent_limit=self.config.eval_concurrency,
            )
            
            # Create CriteriaManager with criteria from Content Library (same as pre-combine)
            criteria_manager = CriteriaManager()
            if self.config.eval_criteria:
                try:
                    data = yaml.safe_load(self.config.eval_criteria)
                    if data and "criteria" in data:
                        parsed_criteria = []
                        for item in data["criteria"]:
                            if isinstance(item, str):
                                parsed_criteria.append(EvaluationCriterion(
                                    name=item,
                                    description=f"Evaluate the {item} of the document.",
                                ))
                            elif isinstance(item, dict) and "name" in item:
                                parsed_criteria.append(EvaluationCriterion(
                                    name=item["name"],
                                    description=item.get("description", f"Evaluate the {item['name']}."),
                                ))
                        if parsed_criteria:
                            criteria_manager.set_criteria(parsed_criteria)
                except Exception as e:
                    self.logger.error(f"Pipeline [{self.source_doc_name}]: Failed to parse eval_criteria YAML for post-combine: {e}")
            
            evaluator = PairwiseEvaluator(pairwise_config, criteria_manager=criteria_manager, stats_tracker=self.stats)
            
            # Collect documents for comparison
            all_doc_ids = []
            all_contents = {}
            
            # Get top docs that were sent to combiner
            docs_sent_to_combiner = [doc_id for doc_id, rating in result.pairwise_results.rankings[:2]]
            
            for doc in result.generated_docs:
                if doc.doc_id in docs_sent_to_combiner:
                    all_doc_ids.append(doc.doc_id)
                    all_contents[doc.doc_id] = doc.content
            
            # Add all combined docs to comparison
            for combined_doc in result.combined_docs:
                all_doc_ids.append(combined_doc.doc_id)
                all_contents[combined_doc.doc_id] = combined_doc.content
            
            if len(all_doc_ids) < 2:
                self.logger.warning(f"Pipeline [{self.source_doc_name}]: Post-combine eval skipped - not enough docs")
                return
            
            # Run pairwise
            post_combine_start = datetime.utcnow()
            summary = await evaluator.evaluate_all_pairs(all_doc_ids, all_contents)
            post_combine_end = datetime.utcnow()
            post_combine_duration = (post_combine_end - post_combine_start).total_seconds()
            
            result.post_combine_eval_results = summary
            
            # Emit timeline event
            await self._emit_timeline_event(
                phase="post_combine_pairwise",
                event_type="pairwise_eval",
                description=f"Post-combine pairwise: {summary.total_comparisons} comparisons",
                model=", ".join(self.config.eval_judge_models),
                timestamp=post_combine_start,
                completed_at=post_combine_end,
                duration_seconds=post_combine_duration,
                success=True,
                details={
                    "total_comparisons": summary.total_comparisons,
                    "winner_doc_id": summary.winner_doc_id,
                },
            )
            
            self.logger.info(
                f"Pipeline [{self.source_doc_name}]: Post-combine eval complete | "
                f"winner={summary.winner_doc_id}"
            )
            
        except Exception as e:
            self.logger.error(f"Pipeline [{self.source_doc_name}]: Post-combine eval failed: {e}")
            result.errors.append(f"Post-combine eval failed: {str(e)}")
